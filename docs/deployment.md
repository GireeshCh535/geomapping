# Deployment (ECS + ECR)

Production deploys run through **GitHub Actions** — no `docker-compose.yml` or Ansible on the server.

| Environment | Branch (auto deploy) | Local dev |
|-------------|----------------------|-----------|
| Production  | `master`             | `docker-compose.dev.yml` |
| Staging     | manual `workflow_dispatch` (optional) | same |

---

## 1. One-time AWS setup

You should already have:

- ECR repository (e.g. `geomapping-staging-web`)
- ECS Fargate cluster (e.g. `layers-staging-cluster`)
- ECS service + ALB target group (port `8000`, health check `/health/`)
- RDS PostgreSQL + ElastiCache Redis
- ACM certificate on ALB
- S3 env file for container variables (see below)
- CloudWatch log group `/ecs/geomapping-staging`

**Task definition** must:

- Container name: `web`
- Image: `<account>.dkr.ecr.<region>.amazonaws.com/<repo>:latest`
- `environmentFiles` → S3 ARN of your env file
- Command: `gunicorn geo_mapping.wsgi:application -c gunicorn_config.py`

Reference template: `ecs/taskdef.json` (replace placeholders when creating the first revision in AWS).

**Execution role** needs: ECR pull, CloudWatch logs, `s3:GetObject` on the env file bucket.

---

## 2. Container env file (S3)

1. Copy `ecs/container.env.example` → `container.env` and fill secrets.
2. Upload:

```bash
aws s3 cp container.env s3://YOUR-BUCKET/geomapping/production.env --region ap-south-1
```

3. Use ARN in the task definition:

```text
arn:aws:s3:::YOUR-BUCKET/geomapping/production.env
```

ECS loads these at task start. **Updating S3 does not reload running tasks** — redeploy to pick up changes.

---

## 3. Local development

```bash
cp .env.example .env
# edit .env (DB password, R2 keys, etc.)

docker compose -f docker-compose.dev.yml up --build
```

App: http://localhost:8001  
Admin: http://localhost:8001/admin/

---

## 4. GitHub Actions — secrets and variables

Repository (or organization) → **Settings → Secrets and variables → Actions**.

Use the **`GEOMAPPING_`** prefix so each repo can define its own ECS deploy variables without clashing with other projects.

### Secrets (credentials only)

| Secret | Example / notes |
|--------|------------------|
| `AWS_ACCESS_KEY_ID` | IAM user for deploy |
| `AWS_SECRET_ACCESS_KEY` | |

### Variables (non-sensitive, per-repo or org)

| Variable | Example / notes |
|----------|------------------|
| `GEOMAPPING_AWS_REGION` | `ap-south-1` |
| `GEOMAPPING_ECR_REPOSITORY` | `geomapping-staging-web` |
| `GEOMAPPING_ECS_CLUSTER` | `layers-staging-cluster` |
| `GEOMAPPING_ECS_SERVICE` | `geomapping-staging-service` |
| `GEOMAPPING_ECS_TASK_DEFINITION` | `geomapping-staging-web` (family name or `family:revision`) |
| `GEOMAPPING_ECS_SUBNET_1` | Private subnet ID |
| `GEOMAPPING_ECS_SUBNET_2` | Private subnet ID |
| `GEOMAPPING_ECS_SECURITY_GROUP` | `ecs-layers-tasks-sg` ID |
| `GEOMAPPING_ECS_ASSIGN_PUBLIC_IP` | `DISABLED` (private subnets + NAT) or `ENABLED` |

Other repos can use their own prefix (e.g. `OTHERAPP_ECS_CLUSTER`) in that repo’s workflow.

Workflow file: `.github/workflows/deploy-workflow.yml`

**Triggers:**

- Push to `master` → build, migrate, deploy
- **Actions → Build and Deploy to ECS → Run workflow** (optional branch)

---

## 5. Deploy flow (what CI does)

1. Build Docker image (`Dockerfile` — includes `collectstatic` + WhiteNoise for admin CSS)
2. Push to ECR as `:latest` and `:<git-sha>`
3. Run one-off ECS task: `python manage.py migrate --noinput`
4. `aws ecs update-service --force-new-deployment`
5. Wait until service is stable

---

## 6. Verify

- Target group health: `healthy` on `/health/`
- `https://layers-staging.citylands.in/health/` → `{"status":"ok"}`
- `https://layers-staging.citylands.in/admin/` (styled)
- CloudWatch: `/ecs/geomapping-staging`

---

## 7. Removed (legacy)

These are no longer used for deploy:

- `docker-compose.yml` (EC2 + nginx compose)
- `deploy.yml` / `run_play.sh` (Ansible)
- `scripts/deploy_ecs.sh` (replaced by GitHub Actions)

Keep **`docker-compose.dev.yml`** for local work only.
