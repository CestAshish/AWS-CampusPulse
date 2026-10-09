# CampusPulse — Deployment Guide

Everything below runs in **eu-north-1 (Stockholm)**. Infrastructure is Terraform in `backend/infra/`, deployed by GitHub Actions on every merge to `main`.

## 1. One-time prerequisites (created outside Terraform)

These existed before the Terraform code and are looked up, not created:

| Resource | Name / tag | Notes |
|---|---|---|
| S3 bucket for Terraform state | `campuspulse-tfstate-2026` | Versioning on, public access blocked |
| VPC | tag `Name = CampusPulse-VPC`, `10.0.0.0/16` | `private-subnet` `10.0.2.0/24` (eu-north-1a); `public-subnet` `10.0.1.0/24` unused; no NAT or internet gateway. Terraform adds `private-subnet-b` `10.0.3.0/24` (eu-north-1b) so the Lambdas span two zones |
| DynamoDB gateway endpoint | `com.amazonaws.eu-north-1.dynamodb` | Must be attached to the private subnets' route table(s). Terraform checks this and refuses to deploy otherwise. Set `manage_dynamodb_endpoint = true` to let Terraform create it. |
| Cognito user pool | `campuspulse-user-pool` | Email sign-in, public app client (no secret), `USER_PASSWORD_AUTH` enabled for the simulator |
| GitHub secrets | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Deployment IAM user |

Create the roles (idempotent) and assign users:

```bash
cd backend/scripts
export COGNITO_USER_POOL_ID=eu-north-1_hVIR8C6l5
python setup_roles.py                                         # creates Admin, Staff, Sensor
python setup_roles.py --user admin@campuspulse.com --group Admin
python setup_roles.py --user staff@campuspulse.com --group Staff
python setup_roles.py --user sensor@campuspulse.com --group Sensor
```

| Role | Can do |
|---|---|
| **Admin** | Dashboard, all read endpoints, `POST /events`, in-browser simulator |
| **Staff** | Dashboard and `GET /stats`, `/events`, `/alerts` (read-only) |
| **Sensor** | `POST /events` only (IoT devices / simulator) |

Roles are enforced by the Lambdas from the `cognito:groups` claim of the verified JWT, not only in the UI.

## 2. Backend and infrastructure

Normal path: open a PR → CI runs unit tests, frontend build and `terraform plan` → merge → CI runs `terraform apply`.

Manual path:

```bash
cd backend/infra
terraform init
terraform plan
terraform apply
```

Outputs: `api_url` (API stage URL) and `dashboard_url` (CloudWatch dashboard). Confirm the SNS subscription email after the first apply.

Variables (`-var` or `terraform.tfvars`): `alert_email`, `monthly_budget_usd` (default 5), `lambda_in_vpc` (default true), `manage_dynamodb_endpoint` (default false).

## 3. Frontend

```bash
cd frontend
npm ci
npm run dev        # local, http://localhost:5173
npm run build      # static bundle in dist/
```

The bundle is static and is deployed by the hosting provider's GitHub integration. The API URL and Cognito IDs are in `src/App.jsx` and `src/amplify-config.js`; they are public identifiers, not secrets.

## 4. Simulated campus data

From a laptop, the simplest way is the runner, which asks for the sensor login once and saves it in a git-ignored file:

```bash
cd backend
uv run python scripts/run_sensors.py                            # one reading per building per second
uv run python scripts/run_sensors.py --rounds 40 --interval 0   # burst test, 200 events
uv run python scripts/run_sensors.py --setup                    # change the saved login
```

Or call the simulator directly with environment variables:

```bash
cd backend/src
export COGNITO_CLIENT_ID=... COGNITO_USERNAME=sensor@campuspulse.com COGNITO_PASSWORD=...
python simulator.py                                  # 5 events/second, forever
ROUNDS=40 INTERVAL_SECONDS=0 python simulator.py     # burst test, 200 events
```

Admins can also start the simulator from the dashboard (15 events every 3 s).

## 5. Tests

```bash
cd backend
uv run pytest -v                 # unit tests (moto-mocked DynamoDB and Cognito)
python scripts/smoke_test.py     # end-to-end tests against the deployed API + latency sample
```

The smoke test checks 401 without a token, 400 on invalid payloads, 201 on ingestion, 200 on every read endpoint, and (with `STAFF_USERNAME`/`STAFF_PASSWORD`) that Staff gets 403 on `POST /events`.

## 6. API

All routes require `Authorization: <Cognito ID token>`.

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/events` | Admin, Sensor | Validate, detect anomalies, store an event |
| GET | `/stats` | Admin, Staff | Campus overview: per-building latest values, energy ranking, overloaded buildings |
| GET | `/stats?building_id=X` | Admin, Staff | Per-type avg/min/max/latest/anomalies + last 60 events |
| GET | `/events?building_id=&event_type=&limit=` | Admin, Staff | Recent events, newest first |
| GET | `/alerts?limit=` | Admin, Staff | Recent anomalies (sparse `AlertIndex`) |
| POST | Cognito `InitiateAuth` | everyone | Login (handled by Cognito, not a Lambda) |

Event payload:

```json
{ "building_id": "LIBRARY", "event_type": "temperature", "temperature_c": 23.4, "timestamp": "2026-08-20T10:15:00Z" }
```

`event_type` ∈ `temperature` (`temperature_c`, −30–60), `occupancy` (`occupancy_count`, 0–1000), `energy` (`energy_kwh`, 0–1000). The server adds `event_id`, `unit`, `severity`, `alert` and a 30-day TTL. Anomaly thresholds: temperature > 28 °C, occupancy > 150, energy > 120 kWh.

## 7. Disaster recovery runbook

| Item | Value |
|---|---|
| Backup | DynamoDB point-in-time recovery (continuous, 35 days) |
| RPO | ≈ 5 minutes (PITR restores to any second up to ~5 minutes ago) |
| RTO | ≈ 30 minutes: restore table (minutes for this data size) + one Terraform apply |
| Infrastructure | Fully re-creatable from Git with `terraform apply` (~5 min) |
| Not covered by Terraform | Cognito user pool and users: recreate with the console and `setup_roles.py` |

Restore procedure:

```bash
aws dynamodb restore-table-to-point-in-time \
  --source-table-name CampusPulseEvents \
  --target-table-name CampusPulseEvents-restored \
  --restore-date-time 2026-08-20T10:00:00Z
aws dynamodb wait table-exists --table-name CampusPulseEvents-restored
```

Switch traffic to the restored table (this is the RTO-critical step):

```bash
for fn in CampusPulse-Ingest CampusPulse-Stats; do
  aws lambda update-function-configuration --function-name $fn \
    --environment "Variables={TABLE_NAME=CampusPulseEvents-restored}"
done
```

Verify with `scripts/smoke_test.py`. To make it permanent, change `name` in `dynamodb.tf` to the restored table, `terraform state rm aws_dynamodb_table.events`, `terraform import aws_dynamodb_table.events CampusPulseEvents-restored`, and apply (re-enables PITR and TTL, which restores do not copy).

## 8. Cost (Free Tier)

| Service | Free Tier allowance | Expected prototype usage | Est. cost / month |
|---|---|---|---|
| Lambda | 1M requests, 400k GB-s (always free) | < 300k invocations × 256 MB | $0 |
| API Gateway (REST) | 1M calls / month (first 12 months) | dashboard 7 calls / 5 s while open + simulator | $0 |
| DynamoDB on-demand | 25 GB storage | < 1 GB; writes billed per request (~$1.25 per million) | < $0.50 |
| DynamoDB PITR | — | < 1 GB | < $0.20 |
| CloudWatch | 10 custom metrics, 10 alarms, 3 dashboards, 5 GB logs | 4 metrics, 8 alarms, 1 dashboard, 14-day retention | $0 |
| Cognito | 10k MAU | < 10 users | $0 |
| SNS email | 1,000 emails | alarm emails only | $0 |
| VPC + gateway endpoint | free | 1 endpoint, no NAT gateway | $0 |
| AWS Budgets | free without actions | 1 budget, 80% actual / 100% forecast emails | $0 |
| **Total** | | | **< $1** |

Cost decisions: no NAT gateway (≈ $35/month) thanks to the free DynamoDB gateway endpoint and log-based metrics; on-demand DynamoDB with a 30-day TTL; 14-day log retention; API throttling at 50 req/s (burst 100).
