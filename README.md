# Kaggle Agent on AWS — Architecture, Trade‑offs, Concurrency, and Implementation Guide

---

## High‑Level Architecture
<img width="1078" height="669" alt="kaggle_agent_solver drawio" src="https://github.com/user-attachments/assets/1cf224b3-0904-4d00-8f18-fa56c7fa0a1f" />




### Entities
- **API Gateway (HTTP)**: Single endpoint `POST /run?url=...&email=...`.
- **Lambda StartRun**: Validates inputs, persists a new `run_id` in DynamoDB, kicks off Step Functions.
- **Step Functions**: Orchestrates Plan → RunTraining (ECS) → ValidateOutput → MarkSucceeded.
- **ECS Fargate Runner**: Pulls the dataset (Kaggle CLI), calls OpenAI for codegen, executes training, and uploads artifacts.
- **S3**: Stores `submission.csv` and logs.
- **DynamoDB**: Tracks `run_id`, url, email, status, s3 keys, timestamps.
- **SES**: Sends final email with pre‑signed S3 link.
- **CloudWatch**: Centralized logs (Lambda & ECS) and metrics/alarms.

---

## Design Goals & Non‑Goals

**Goals**
- One‑click (curl) runs per Kaggle URL.
- Scalable
- Concurrent and isolation
- Extensible
- Security (these are defaults from IAM and API Gateway)

---

## Key Trade‑offs & Reasoning

### Serverless vs. Always‑On Compute
- **Choice**: Serverless + ECS Fargate.
- **Why**: Cold starts are acceptable for batch workflows; zero idle cost; simple ops.
- **Trade‑off**: Longer latency for first request vs. running EC2 24/7.

### Terraform State & Drift Control (took 7 hrs to fix this, horrible)
- Keep TF state **out of repo** (e.g., S3 backend) to avoid secret leakage and drift.
- Use ECS **`track_latest = true`** with image tags **tied to Terraform var** to reduce mismatches.
- Controlled ECR tagging scheme to make rollbacks obvious.

---

## End‑to‑End Flow

1. **Client** calls:  
   ```bash
   curl -X POST "https://<api-id>.execute-api.<region>.amazonaws.com/prod/run?url=<kaggle_competition_url>&email=<you@example.com>"
   ```
2. **StartRun** creates a `run_id`, writes `Queued` status to DynamoDB, then `StartExecution` of the state machine.
3. **Plan** Lambda calls OpenAI to reason about the dataset (only light metadata), prepares a “plan”. Writes `Planned`.
4. **RunTraining** runs ECS task with env: `RUN_ID`, `URL`, `EMAIL`, S3/DDB from task definition; the runner downloads data, generates **train_code.py**, executes it, uploads `submission.csv` and logs.
5. **ValidateOutput** confirms `submission.csv` exists and is well‑formed; writes `Validated`.
6. **MarkSucceeded** pre‑signs S3 URL and emails via SES; marks `Succeeded` (or `Failed`).

---

## Concurrency Model & Throttling

- **API Gateway**: Accepts bursty traffic. Configure throttling (e.g., 100 RPS, 200 burst) if needed.
- **Lambda StartRun**: Quick, lightweight; concurrency limit default is fine.
- **Step Functions**: Each run has its own execution; defaults suffice.
- **ECS Fargate**: Primary cost/compute bottleneck. Control with:
  - **DDB‑backed admission control** (optional): if >N running, return `429 Try later`.
- **OpenAI/Kaggle Rate Limits**: Retries with exponential backoff; jitter; capped attempts.
- **Idempotency**: `run_id` is the partition key; starting the same `run_id` again is a no‑op.

---

## Implementation Walkthrough (see the video)

### API Gateway & Lambda **StartRun**
- **Input**: `url` (Kaggle comp URL), `email`.
- **Validations**: URL domain, email shape.
- **Writes**: `Runs` table with initial status `QUEUED`, timestamps.
- **Starts**: `states:StartExecution` with input `{run_id, url, email}`.

**IAM**
- `dynamodb:PutItem` on `Runs`.
- `states:StartExecution` on the state machine.
- CloudWatch Logs: create/put.

### Lambda **Plan**
- Extracts **slug** and hints (problem type, target if obvious).
- Calls OpenAI for a **small, bounded reasoning** step (no big code blobs).
- Persists `"plan"` to DynamoDB and returns input for the next state.

**IAM**
- `dynamodb:UpdateItem`
- CloudWatch Logs.

### ECS Fargate Task: **Runner**
- **Image**: pushed to ECR; tagged `:N` (monotonic integer). TF variable `runner_image_tag=N` feeds task def.
- **CPU/Memory**: 1024/2048 (tunable).
- **Env**: `S3_BUCKET`, `DDB_TABLE`; **Secrets from SSM**: `KAGGLE_USERNAME`, `KAGGLE_KEY`, `OPENAI_API_KEY`.
- **Code Path**:
  1. Download data: Kaggle CLI; if rules not accepted → emit actionable error.
  2. Generate training code via OpenAI **(only model body)**; glue code is static scaffold for stability.
  3. Run `train_code.py`; collect stdout/stderr → `/work/logs.txt`.
  4. Upload `submission.csv`, `logs.txt`, `gpt_code_trace.txt` to `s3://<bucket>/<run_id>/`.
  5. Update DDB status.

**CloudWatch Logs**
- Log group `/aws/ecs/<project-name>` with stream prefix `runner`.

### Lambda **ValidateOutput**
- Checks `s3://.../submission.csv` exists and has at least 1 row and 2 columns.
- Updates DDB: status `VALIDATED` or `FAILED` with reason.

### Lambda **MarkSucceeded** (SES Email)
- Builds a pre‑signed URL (time‑limited) for `submission.csv`.
- Sends email via SES (verified sender in region).
- Updates DDB final status.

### State Machine
- Type: Standard.
- Steps: `Plan` → `RunTraining (ecs:runTask.sync)` → `ValidateOutput` → `MarkSucceeded`.
- **Parameters** for ECS include network config (default VPC subnets) and env overrides for `RUN_ID`, `URL`, `EMAIL`.

### Data Stores: DynamoDB & S3
- **DynamoDB (Runs)**: PK = `run_id`, attributes: `url`, `email`, `status`, `s3_key`, `timestamps`, `errors`.
- **S3 (artifacts)**: `kagent-artifacts/<run_id>/submission.csv`, `/logs.txt`, `/gpt_code_trace.txt`.

### Images, ECR & Docker Tags

**Build & Push (linux/arm64)**  
> Your Fargate platform is `X86_64` by default; this is the **builder** architecture only. Multi‑arch images ensure the manifest has both amd64 and arm64.
```bash
# login once
aws ecr get-login-password --region us-west-2 \
| docker login --username AWS --password-stdin 958923398556.dkr.ecr.us-west-2.amazonaws.com

# multi-arch build (arm64 + amd64) and push tag N
docker buildx create --use --name kagent || true
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t 958923398556.dkr.ecr.us-west-2.amazonaws.com/kaggle-runner:14 \
  -t 958923398556.dkr.ecr.us-west-2.amazonaws.com/kaggle-runner:latest \
  --push .
```

**Wire tag → Task Definition**
- Terraform var `runner_image_tag` controls the exact tag the task definition uses.
- Set `track_latest = true` in the ECS task definition to make `:latest` follow automatically (optional; many teams prefer immutable tags only).

**Verify Running Image**
```bash
aws ecs describe-task-definition --task-definition kaggle-agent-runner:13 \
  --query 'taskDefinition.containerDefinitions[0].image'

aws ecs list-tasks --cluster kaggle-agent-cluster --desired-status RUNNING
aws ecs describe-tasks --cluster kaggle-agent-cluster --tasks <taskArns> \
  --query 'tasks[].containers[].image'
```

---

## Observability & Runbook

**CloudWatch Logs Groups**
- `/aws/lambda/<project>` for all lambdas.
- `/aws/ecs/<project>` for runner.

---

## Deployment

**Terraform**
```bash
cd terraform
# Provide vars (no secrets in VCS!)
terraform apply -auto-approve -var="runner_image_tag=14" -var="ses_from_email=you@domain.com"
```

**Outputs**
- `api_base_url`, `state_machine_arn`, `ecs_task_definition_arn`, `ecr_repository_url`.

**Invoke**
```bash
curl -X POST "$API_BASE/run?url=https://www.kaggle.com/competitions/titanic&email=you@domain.com"
```

---

## Testing & Troubleshooting

**Quick Status Peek**
- DynamoDB `Runs` table by `run_id` to see `status` (`QUEUED`, `PLANNED`, `RUNNING`, `VALIDATED`, `SUCCEEDED`, `FAILED`).

**Frequent Issues**
- **Image manifest doesn’t contain platform**: use `buildx` with multi‑arch push.
- **ECS task pulls old image**: ensure TF uses the new tag; confirm `describe-task-definition` shows the intended tag; new runs will pull the new revision.
- **OpenAI code block fences**: codegen scrubber removes ``` fences; scaffold guards ensure runnable.
- **Titanic NaN or feature mismatch**: scaffold forces numeric only, aligns columns; impute NaNs; keep `PassengerId` out of features.

---

## Cost Notes

- **ECS Fargate**: pay per vCPU/GB per second; 1vCPU/2GB for ~5–10 min per run is low cost.
- **Lambda**: negligible for lightweight steps.
- **Step Functions**: per‑state transition pricing; low for this workflow.
- **S3/DDB**: pennies unless retaining many artifacts.
- **SES**: near‑free for low volume (verify region limits).

---

able scaffolding around a small code‑generated core, clear IAM isolation, multi‑arch images, and bulletproof orchestration. Treat accuracy as incremental improvement; stability first.
