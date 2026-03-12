# SQS tile worker – local server setup

The **Layers** Django app (on EC2 or your server) receives webhooks and **pushes jobs to SQS**. A **tile worker** runs on a machine that **polls SQS**, generates tiles (TIF or land/plot MVT), uploads to S3, and POSTs results to the callback URL.

---

## Quick start (e.g. `ssh gamyam@10.10.10.12`)

1. **Clone/pull** the geomapping repo and install deps: `pip install -r requirements.txt`
2. **Configure** the same DB as Layers + AWS credentials (for SQS receive/delete and S3 upload). Set `TILE_SQS_QUEUE_URL`, `TILE_CALLBACK_BASE_URL`, `TILE_CALLBACK_SECRET`, and S3 bucket.
3. **Run:** `python manage.py poll_sqs_tile_worker --wait 20`  
   Or run as a systemd service (see below).

The worker must have **network access** to the same PostgreSQL as the Layers app and to the callback URL (e.g. `https://layers.1acre.in`). IAM (or AWS keys) must allow **SQS ReceiveMessage + DeleteMessage** and **S3 PutObject** (and any delete/list you use).

---

## Architecture

- **1acre-be** → **Layers (Django)** webhook → **SQS**
- **Local server** (this machine) → **polls SQS** → runs tile gen → **S3** + callback POST

No Lambda; no inbound connection to the local server.

---

## Option A: Run worker on the same EC2 as Django (GEO_MAPS1)

If the worker runs on **GEO_MAPS1** (3.108.10.59), it already has the IAM instance profile `geomapping-ec2-role`, so it can receive from SQS and upload to S3 without extra credentials.

### 1. SSH into the server

```bash
# If GEO_MAPS1 is the Layers server (e.g. 3.108.10.59)
ssh gamyam@3.108.10.59
# or your actual user@host
```

### 2. Go to the app directory and activate env (if you use one)

```bash
cd /path/to/geomapping   # wherever the Django app lives
source venv/bin/activate   # if you use a virtualenv
```

### 3. Set environment (if not already set)

Ensure these are set (same as the Django app):

- `TILE_SQS_QUEUE_URL` – e.g. `https://sqs.ap-south-1.amazonaws.com/471112704924/geomapping-tile-gen-queue`
- `TILE_CALLBACK_BASE_URL` – e.g. `https://layers.1acre.in`
- `TILE_CALLBACK_SECRET` – same secret the app uses
- DB and AWS are already configured for the app (EC2 role or env vars)

### 4. Run the worker (foreground)

```bash
python manage.py poll_sqs_tile_worker --wait 20
```

- `--wait 20`: long-poll SQS for 20 seconds (reduces empty receives).
- Exits on Ctrl+C.

### 5. Run as a systemd service (recommended)

Create a service so the worker restarts on reboot and runs in the background.

```bash
sudo nano /etc/systemd/system/geomapping-tile-worker.service
```

Paste (adjust `User`, `WorkingDirectory`, and `ExecStart` to your paths):

```ini
[Unit]
Description=Geomapping SQS tile worker
After=network.target

[Service]
Type=simple
User=gamyam
WorkingDirectory=/home/gamyam/geomapping
Environment="PATH=/home/gamyam/geomapping/venv/bin"
ExecStart=/home/gamyam/geomapping/venv/bin/python manage.py poll_sqs_tile_worker --wait 20
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

If you use env vars from a file:

```ini
EnvironmentFile=/home/gamyam/geomapping/.env
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable geomapping-tile-worker
sudo systemctl start geomapping-tile-worker
sudo systemctl status geomapping-tile-worker
```

Logs:

```bash
journalctl -u geomapping-tile-worker -f
```

---

## Option B: Run worker on a different machine (e.g. 10.10.10.12)

If the worker runs on **another server** (e.g. `gamyam@10.10.10.12`), that machine must:

1. Have the **geomapping codebase** (same repo).
2. Be able to connect to the **same database** as the Layers Django app (VPN/firewall so it can reach the DB).
3. Have **AWS credentials** that can **ReceiveMessage** / **DeleteMessage** on the SQS queue and **PutObject** (and list/delete if needed) on the S3 bucket.

### 1. SSH into the local server

```bash
ssh gamyam@10.10.10.12
```

### 2. Clone/copy the project and install dependencies

```bash
cd ~
git clone <your-repo> geomapping
cd geomapping
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables

Create `.env` or export:

```bash
# Database (same as Layers app so worker sees SyncedLand/SyncedPlot and DeveloperListing)
export DJANGO_DB_HOST=...
export DJANGO_DB_NAME=...
export DJANGO_DB_USER=...
export DJANGO_DB_PASSWORD=...

# SQS and callback
export TILE_SQS_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/471112704924/geomapping-tile-gen-queue
export TILE_CALLBACK_BASE_URL=https://layers.1acre.in
export TILE_CALLBACK_SECRET=<same-secret-as-layers-app>

# AWS (for SQS receive + S3 upload)
export AWS_DEFAULT_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# S3 bucket (same as Layers)
export AWS_STORAGE_BUCKET_NAME=gis-portal
```

If the callback URL is only reachable from inside the VPN, ensure this machine can reach `https://layers.1acre.in` (or the internal URL you use).

### 4. Run migrations (once)

```bash
python manage.py migrate
```

### 5. Run the worker

Foreground:

```bash
python manage.py poll_sqs_tile_worker --wait 20
```

Or install the same systemd unit as in Option A (paths and `EnvironmentFile`/env vars adjusted for this host).

---

## One-off / cron (process one batch and exit)

```bash
python manage.py poll_sqs_tile_worker --once --wait 5
```

Useful for a cron job that runs every minute.

---

## Verify

1. Trigger a webhook from 1acre-be (e.g. create/update a developer listing with a TIF, or land/plot create/update).
2. On the Layers server, a message should be sent to SQS (check logs for `[WEBHOOK_BACKGROUND] Tile job sent to SQS` or `[LAND_PLOT_WORKER]`).
3. On the worker machine, you should see logs like `[SQS] Processing job_type=tif` or `land_plot_mvt`, then tile gen and callback POST.
4. In Django admin, the corresponding **WebhookEvent** (or Land/Plot event) should show `processed=True`, `tiles_generated` set, and optional `tile_generation_logs` if the callback included logs.

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| Worker not receiving messages | `TILE_SQS_QUEUE_URL` correct? AWS credentials (or IAM role) allow `sqs:ReceiveMessage`, `sqs:DeleteMessage` on that queue? |
| Callback POST fails | Can the worker reach `TILE_CALLBACK_BASE_URL`? Is `TILE_CALLBACK_SECRET` the same as in Django settings? |
| TIF job fails (e.g. “Listing not found”) | Worker must use the **same DB** as the web app so `DeveloperListing` / media exist. |
| Land/plot job fails | Same: DB must have `SyncedLand` / `SyncedPlot` for the listing. |
| S3 upload fails | AWS credentials (or role) need `s3:PutObject` (and any list/delete you use) on the bucket. |
