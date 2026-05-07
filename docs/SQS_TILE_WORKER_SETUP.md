# SQS tile worker – local server setup

The **Layers** Django app receives webhooks and **pushes jobs to SQS**. A **tile worker** runs on a machine that **polls SQS**, generates tiles (TIF or land/plot MVT), **uploads objects to Cloudflare R2** (S3-compatible API), and POSTs results to the callback URL.

Tile bytes are then served from your **public CDN** (`PUBLIC_TILE_CDN_HOST`, e.g. `tiles.citylands.in`), not from AWS S3.

---

## Quick start (e.g. `ssh gamyam@10.10.10.12`)

1. **Clone/pull** the geomapping repo and install deps: `pip install -r requirements.txt`
2. **Configure** the same DB as Layers, **R2** credentials (tile uploads), and **AWS IAM** only if the queue is **AWS SQS** (receive/delete messages). Set env vars below.
3. **Run:** `python manage.py poll_sqs_tile_worker --wait 20`  
   Or run as a systemd service (see below).

The worker must have **network access** to the same PostgreSQL as the Layers app, to the **R2 API endpoint** (`*.r2.cloudflarestorage.com`), and to the callback URL (e.g. `https://layers.citylands.in`).

---

## Required environment (tiles → R2)

These must match the Layers Django app (same bucket and keys as production):

| Variable | Purpose |
|----------|---------|
| `CLOUDFLARE_R2_ENDPOINT_URL` | R2 S3 API base, e.g. `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `CLOUDFLARE_R2_ACCESS_KEY_ID` | R2 API token access key |
| `CLOUDFLARE_R2_SECRET_ACCESS_KEY` | R2 API token secret |
| `CLOUDFLARE_R2_BUCKET_NAME` | R2 bucket name (e.g. `gis-portal-layers`) |
| `PUBLIC_TILE_CDN_HOST` | Hostname Django uses **only server-side** to fetch tile bytes (e.g. `tiles.citylands.in`); **do not** put this in front-end tile URLs |
| `TILE_PROXY_PUBLIC_BASE_URL` | Optional: `https://layers.citylands.in` so API JSON returns absolute `/api/tiles/...` links on your app domain (not the CDN) |

Optional: `CLOUDFLARE_R2_REGION_NAME` (default `auto`), `PUBLIC_TILE_CDN_PATH_PREFIX` if the CDN uses a path prefix.

**AWS S3 is not used** for tile storage in this codebase.

---

## AWS credentials (SQS only)

If `TILE_SQS_QUEUE_URL` points at **Amazon SQS**, the worker still uses **boto3** for `ReceiveMessage` / `DeleteMessage`. Provide:

- `AWS_DEFAULT_REGION` (e.g. `ap-south-1`)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, **or** an EC2 instance profile / IAM role with `sqs:ReceiveMessage`, `sqs:DeleteMessage` on that queue.

You do **not** need `s3:PutObject` on AWS for tiles; uploads go to **R2** with the variables above.

Optional: if you still use **AWS CloudFront invalidation** from code, set `CLOUDFRONT_DISTRIBUTION_ID` and the same AWS keys for the CloudFront API (otherwise omit).

---

## Architecture

- **1acre-be** → **Layers (Django)** webhook → **SQS**
- **Worker machine** → **polls SQS** → runs tile gen → **R2** (object keys unchanged) + callback POST

No Lambda; no inbound connection to the worker.

---

## Option A: Run worker on the same host as Django (e.g. EC2)

If the worker runs on the **same server** as Gunicorn:

1. Use the **same `.env`** (or systemd `EnvironmentFile`) as the web app so **R2** and **DB** match.
2. For SQS on AWS, either attach an IAM role with SQS permissions or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env`.

### Run the worker (foreground)

```bash
cd /path/to/geomapping
source venv/bin/activate   # if applicable
python manage.py poll_sqs_tile_worker --wait 20
```

- `--wait 20`: long-poll SQS for up to 20 seconds (fewer empty receives).
- Exits on Ctrl+C.

### Run as a systemd service (recommended)

```bash
sudo nano /etc/systemd/system/geomapping-tile-worker.service
```

Example:

```ini
[Unit]
Description=Geomapping SQS tile worker (R2 uploads)
After=network.target

[Service]
Type=simple
User=gamyam
WorkingDirectory=/home/gamyam/geomapping
Environment="PATH=/home/gamyam/geomapping/venv/bin"
EnvironmentFile=/home/gamyam/geomapping/.env
ExecStart=/home/gamyam/geomapping/venv/bin/python manage.py poll_sqs_tile_worker --wait 20
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable geomapping-tile-worker
sudo systemctl start geomapping-tile-worker
sudo systemctl status geomapping-tile-worker
```

Logs: `journalctl -u geomapping-tile-worker -f`

---

## Option B: Run worker on a different machine

That machine must:

1. Have the **geomapping** codebase (same version as Layers).
2. Reach the **same PostgreSQL** as Layers.
3. Have **R2** env vars (`CLOUDFLARE_R2_*`, `PUBLIC_TILE_CDN_HOST`) identical to production.
4. If using **AWS SQS**, have **AWS** credentials (or role) for the queue only.

Example `.env` excerpts:

```bash
# Database (same as Layers)
export DJANGO_DB_HOST=...
export DJANGO_DB_NAME=...
export DJANGO_DB_USER=...
export DJANGO_DB_PASSWORD=...

# R2 (tile uploads — required)
export CLOUDFLARE_R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
export CLOUDFLARE_R2_BUCKET_NAME=gis-portal-layers
export CLOUDFLARE_R2_ACCESS_KEY_ID=...
export CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
export PUBLIC_TILE_CDN_HOST=tiles.citylands.in

# SQS + callback (if queue is on AWS)
export TILE_SQS_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/471112704924/geomapping-tile-gen-queue
export TILE_CALLBACK_BASE_URL=https://layers.citylands.in
export TILE_CALLBACK_SECRET=<same-secret-as-layers-app>
export AWS_DEFAULT_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

Run migrations once, then:

```bash
python manage.py poll_sqs_tile_worker --wait 20
```

---

## One-off / cron (process one batch and exit)

```bash
python manage.py poll_sqs_tile_worker --once --wait 5
```

---

## Verify

1. Trigger a webhook (developer listing TIF or land/plot update).
2. Layers logs: tile job sent to SQS.
3. Worker logs: `[SQS] Processing job_type=tif` or `land_plot_mvt`, generation, uploads (R2), callback POST.
4. **WebhookEvent** / land-plot event: `processed=True`, `tiles_generated` set.

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| Worker not receiving messages | `TILE_SQS_QUEUE_URL`; AWS credentials / IAM for **SQS** only |
| Callback POST fails | Worker can reach `TILE_CALLBACK_BASE_URL`; `TILE_CALLBACK_SECRET` matches Layers |
| TIF / listing job fails | Same DB as Layers; `DeveloperListing` / media rows exist |
| Land/plot job fails | Same DB; `SyncedLand` / `SyncedPlot`; coordinates in payload |
| **R2 upload fails** | `CLOUDFLARE_R2_ENDPOINT_URL`, keys, bucket name; outbound HTTPS to `*.r2.cloudflarestorage.com` |
| Tiles 404 on CDN | Objects exist in R2 under expected keys; CDN / custom domain points at that bucket |
