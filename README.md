# geomapping

GIS layers API and tile serving (Django + PostGIS + Redis + Cloudflare R2).

## Branches

| Branch   | Deploy |
|----------|--------|
| **master** | Auto deploy to ECS via GitHub Actions |
| **main**   | Development; use workflow_dispatch to deploy if needed |

## Local development

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

- App: http://localhost:8001
- Admin: http://localhost:8001/admin/

## Production deploy (ECS)

See **[docs/deployment.md](docs/deployment.md)** for:

- AWS / ECS / ECR / S3 env file setup
- GitHub Actions secrets
- CI deploy flow (no docker-compose on server)

Workflow: `.github/workflows/deploy-workflow.yml`
