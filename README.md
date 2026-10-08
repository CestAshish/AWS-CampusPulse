# AWS-CampusPulse: Serverless IoT Monitoring Infrastructure

## 📖 Project Overview
CampusPulse is a cloud-native, serverless IoT data ingestion and monitoring platform built on AWS for the fictional NorthBridge University. It collects, validates, stores and analyses real-time telemetry (temperature, building occupancy and energy usage) from simulated sensors in five campus buildings, and gives operations staff a role-protected dashboard.

It answers the operations team's questions directly:
* **Which buildings are overloaded?** `GET /stats` flags buildings above the 150-person capacity.
* **Which buildings consume the most energy?** `GET /stats` ranks buildings by average kWh.
* **Are there unusual temperature or equipment events?** Every event is checked server-side; anomalies go to `GET /alerts`, CloudWatch alarms and an SNS email.

## 🎯 The Problem
1. **Unpredictable traffic spikes:** sensors surge when classes end and go quiet at night.
2. **Real-time alerting:** facility managers need immediate notice of fire-code occupancy breaches, temperature anomalies and power surges.
3. **Data silos and security:** one secure, scalable backend must consolidate all sensor events without exposing compute or data to the internet.

## 🏗️ Architecture
100% serverless, deployed with Terraform from GitHub Actions, in `eu-north-1`. The architecture diagram is in the project docs.

* **Amazon API Gateway (REST):** `POST /events`, `GET /stats`, `GET /events`, `GET /alerts`; Cognito authorizer on every route, CORS, stage throttling (50 req/s, burst 100).
* **Amazon Cognito:** user pool with three groups — **Admin** (full access), **Staff** (read-only), **Sensor** (ingest only). Roles are enforced in the Lambdas from the verified JWT.
* **AWS Lambda (Python 3.12), in private VPC subnets:**
  * `CampusPulse-Ingest` — validates the payload, detects anomalies server-side, stores the event, emits metrics.
  * `CampusPulse-Stats` — read API: per-building aggregates (avg/min/max/latest/anomalies), campus overview, recent events, alerts.
* **VPC networking:** Lambdas run in private subnets with a dedicated security group (no inbound, HTTPS out to DynamoDB only). DynamoDB is reached through the free VPC gateway endpoint — no NAT gateway, no internet path.
* **Amazon DynamoDB:** `CampusPulseEvents`, PK `building_id`, SK `timestamp`; `EventTypeIndex` GSI and sparse `AlertIndex` GSI; point-in-time recovery; 30-day TTL; encrypted at rest.
* **Amazon CloudWatch + SNS:** custom metrics via Embedded Metric Format (`Temperature`, `OccupancyCount`, `EnergyUsage`, `AnomalyCount`), the `CampusPulse-Monitoring` dashboard, 8 alarms (API 5xx, Lambda errors/throttles, sensor thresholds) → email; 14-day log retention.
* **AWS Budgets:** monthly cost budget with 80% actual / 100% forecast email alerts.
* **Frontend:** React (Vite) dashboard with Amplify Auth and Recharts.

## ⚖️ Trade-offs & Design Decisions
1. **Serverless (Lambda) vs. containers** — no servers to patch, multi-AZ by default, scale to zero at night; we accept occasional cold starts.
2. **DynamoDB on-demand vs. provisioned** — campus traffic is spiky; on-demand avoids throttling at class changes without auto-scaling rules.
3. **Two Lambdas instead of one** — a bug in the read path can never stop sensor ingestion.
4. **NoSQL vs. RDS** — no joins needed; key design gives ordered per-building queries and fast writes, with no RDS instance to pay for.
5. **Gateway endpoint + log-based metrics vs. NAT gateway** — keeps the Lambdas private for $0 instead of ≈ $35/month.
6. **Server-side anomaly detection** — sensors cannot hide or fake alerts; thresholds live in one place (`backend/src/common.py`).

## ⚙️ Repository Layout
* `backend/infra/` — Terraform: `main.tf` (provider, VPC lookups, Lambda security group, DynamoDB endpoint), `dynamodb.tf`, `iam.tf`, `lambda.tf`, `api_gateway.tf`, `auth.tf`, `cloudwatch.tf`, `budget.tf`.
* `backend/src/` — `common.py` (schema, thresholds, roles), `ingest_handler.py`, `stats_handler.py`, `simulator.py` + `auth.py` (run locally, excluded from the Lambda zip).
* `backend/tests/` — unit tests with moto-mocked DynamoDB and Cognito.
* `backend/scripts/` — `setup_roles.py` (Cognito groups), `smoke_test.py` (end-to-end API test).
* `frontend/` — React dashboard.
* `.github/workflows/deploy.yml` — tests + build + `terraform plan` on PRs; `terraform apply` on merge to `main`.

## 🚀 Deployment
See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for prerequisites, roles, deployment, the simulator, tests, the API reference, the disaster-recovery runbook and the cost table.

```bash
cd backend/infra
terraform init
terraform plan
terraform apply
```
