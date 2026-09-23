# AWS-CampusPulse: Serverless IoT Monitoring Infrastructure

## 📖 Project Overview
CampusPulse is a cloud-native, serverless IoT data ingestion and monitoring platform built on AWS. It allows campus administrators to collect, store, securely access, and analyze real-time telemetry data (such as temperature, building occupancy, and energy usage) from IoT sensors distributed across multiple campus buildings.

## 🎯 The Problem
Modern university campuses consist of dozens of buildings, each with complex heating, electrical, and security needs. Tracking this data manually or through fragmented legacy systems is highly inefficient. 

**The core challenges solved by this project include:**
1. **Unpredictable Traffic Spikes:** IoT sensors generate massive traffic surges (e.g., when classes end and thousands of students trigger occupancy sensors), followed by long periods of silence at night.
2. **Real-time Alerting Needs:** Facility managers require immediate, automated notifications if a building exceeds safe fire-code occupancy limits, experiences severe temperature anomalies, or shows signs of an electrical surge.
3. **Data Silos & Security:** A unified, scalable, and highly secure backend is required to consolidate diverse sensor events into a single database without exposing the endpoints to the public internet.

## 🏗️ Architecture & Design
The infrastructure is 100% Serverless, deployed via Infrastructure as Code (Terraform), and adheres to AWS well-architected best practices for security and reliability.

### Core AWS Components:
* **Amazon API Gateway (The Front Door):** Exposes RESTful endpoints (`POST /events` for sensor ingestion, `GET /stats` for dashboard retrieval) with robust CORS policies mapped for browser compatibility.
* **Amazon Cognito (Security):** Secures the API via a User Pool Authorizer, ensuring only authenticated administrative devices and verified sensors can interact with the system.
* **AWS Lambda (Compute Layer):** Provides the business logic via Python 3.12 in two isolated microservices:
  * `CampusPulse-Ingest`: Validates and processes incoming IoT payloads.
  * `CampusPulse-Stats`: Handles heavy read operations and data aggregation for frontend dashboards.
* **Amazon DynamoDB (Storage):** Serves as the primary NoSQL data store.
  * *Primary Key:* `building_id` (Partition) and `timestamp` (Sort) for rapid, chronologically sorted queries per building.
  * *Global Secondary Index (GSI):* Indexed on `event_type` to allow fleet-wide querying of specific anomalies (e.g., fetching all "High Temperature" events across the entire campus instantly).
  * *Data Protection:* Point-In-Time-Recovery (PITR) is enabled for 35-day continuous backups.
* **Amazon CloudWatch & SNS (Monitoring & Alerting):** Aggregates custom business metrics (`OccupancyCount`, `EnergyUsage`, `Temperature`) pushed by Lambda. Triggers automated SNS email alerts to administrators if predefined safety thresholds are breached.

## ⚖️ Trade-offs & Design Decisions

1. **Serverless (Lambda) vs. Containers (ECS/EKS)**
   * *Decision:* Serverless was chosen over container orchestration.
   * *Trade-off:* We accept occasional minor "cold start" latency in exchange for **zero server maintenance**, built-in high availability across availability zones, and **scale-to-zero pricing** (crucial for cost-savings during quiet campus nights).
2. **DynamoDB On-Demand vs. Provisioned Capacity**
   * *Decision:* The database utilizes `PAY_PER_REQUEST` (On-Demand billing).
   * *Trade-off:* While Provisioned Capacity might offer a lower baseline cost for highly predictable traffic, campus IoT data is extremely spiky. On-Demand pricing prevents API throttling during peak class changes and eliminates the need to manage complex auto-scaling rules.
3. **Microservices vs. Monolithic Lambda**
   * *Decision:* The Ingest and Stats logic are split into two completely separate Lambda functions.
   * *Trade-off:* This slightly increases the Terraform deployment footprint. However, it ensures strict separation of concerns—if a bug is introduced into the dashboard analytics function (`Stats`), it will never bring down or interrupt critical sensor data ingestion (`Ingest`).
4. **NoSQL vs. Relational Database (RDS)**
   * *Decision:* DynamoDB (NoSQL) was selected over a relational database like PostgreSQL.
   * *Trade-off:* We sacrifice complex SQL `JOIN` capabilities. In return, we gain sub-millisecond write performance and a flexible, schemaless structure capable of absorbing diverse, rapidly evolving IoT JSON payloads without requiring tedious database migrations.

## ⚙️ Implementation Details

### Project Organization
The repository is organized strictly separating Infrastructure as Code (IaC) from Application Code:

* `backend/infra/`: Contains all Terraform definitions to provision the AWS cloud environment.
  * `main.tf`: Provider setup and VPC/Network existing data lookups.
  * `dynamodb.tf`: Table schema, GSI, and automated backup configuration.
  * `iam.tf`: Least-privilege IAM roles and access policies for Lambda execution.
  * `lambda.tf`: Automated zipping and deployment of the Python compute layer.
  * `api_gateway.tf`: API Routes, Lambda Integrations, CORS fallbacks, and production deployment stages.
  * `auth.tf`: Integration with existing Cognito User Pools to secure the API.
  * `cloudwatch.tf`: Custom metric alarms and automated SNS topic email subscriptions.
* `src/`: Contains the application business logic.
  * `ingest_handler.py`: Python logic for processing `POST /events`.
  * `stats_handler.py`: Python logic for processing `GET /stats`.

### Deployment Instructions
1. Ensure you have Terraform `~> 5.0` and the AWS CLI installed and configured.
2. Navigate to the infrastructure directory:
   ```bash
   cd backend/infra
   ```
3. Initialize the Terraform backend (configured for remote S3 state locking in `eu-north-1`):
   ```bash
   terraform init
   ```
4. Review the infrastructure plan to verify resources:
   ```bash
   terraform plan
   ```
5. Deploy to AWS:
   ```bash
   terraform apply
   ```