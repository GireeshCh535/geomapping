# Lambda-based tile generation – what you need to do

Django is ready: when **TILE_USE_LAMBDA=true** and **TILE_GENERATION_LAMBDA_ARN** is set, the developer-listing-media webhook invokes your Lambda instead of running tile generation in-process. Lambda (or any external worker) should run the tile job and then **callback** to Django to store results and logs.

---

## 1. Apply the migration

On the Django server (or in CI):

```bash
cd /opt/geomapping   # or your project root
docker-compose exec web python manage.py migrate
```

This adds the `tile_generation_logs` field to `WebhookEvent`.

---

## 2. Set environment variables (Django)

Configure these where your Django app runs (e.g. `docker-compose.yml` or server env):

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `TILE_USE_LAMBDA` | Yes (to enable Lambda) | `true` | Set to `true` to invoke Lambda; otherwise the existing in-process thread is used. |
| `TILE_GENERATION_LAMBDA_ARN` | Yes (if using Lambda) | `arn:aws:lambda:ap-south-1:471112704924:function:geomapping-tile-gen` | Full ARN of your Lambda function. |
| `TILE_CALLBACK_SECRET` | Yes (recommended) | `your-random-secret-string` | Secret used to secure the callback. Lambda must send this in the `X-Tile-Callback-Secret` header. |
| `TILE_CALLBACK_BASE_URL` | No | `https://layers.1acre.in` | If set, callback URL is built from this + path. Otherwise Django uses the request’s host (e.g. behind proxy). |

**Example in docker-compose.yml (web service):**

```yaml
environment:
  - TILE_USE_LAMBDA=true
  - TILE_GENERATION_LAMBDA_ARN=arn:aws:lambda:ap-south-1:471112704924:function:geomapping-tile-gen
  - TILE_CALLBACK_SECRET=your-secret-here
  # Optional if behind proxy:
  - TILE_CALLBACK_BASE_URL=https://layers.1acre.in
```

Generate a strong secret, e.g.:

```bash
openssl rand -hex 32
```

Use the same value for **TILE_CALLBACK_SECRET** in Django and in Lambda (header `X-Tile-Callback-Secret`).

---

## 3. Callback endpoint (Django – already implemented)

Lambda must **POST** to:

- **URL:** `https://<your-domain>/api/webhooks/tile-generation-result/`
- **Header:** `X-Tile-Callback-Secret: <TILE_CALLBACK_SECRET>`
- **Content-Type:** `application/json`
- **Body:**

```json
{
  "webhook_event_id": 123,
  "success": true,
  "tiles_generated": 150,
  "tif_files_processed": 1,
  "processing_result": { "file_results": [...], "total_tiles_generated": 150 },
  "processing_error": "",
  "logs": [
    { "ts": "2025-02-27T10:00:01Z", "level": "info", "msg": "[TILE_GEN] Starting listing=developerland id=70 tif_files=1" },
    { "ts": "2025-02-27T10:00:02Z", "level": "info", "msg": "[TIF_PROCESS] Processing map.tif" },
    { "ts": "2025-02-27T10:01:30Z", "level": "info", "msg": "[TIF_PROCESS] Tiles generated: 150" }
  ]
}
```

Django will:

- Update `WebhookEvent` (processed, processed_at, tiles_generated, tif_files_processed, processing_result, processing_error).
- Store `logs` in `WebhookEvent.tile_generation_logs` (same format as current in-app logging).

---

## 4. Lambda code (in this repo)

The Lambda handler code lives in **`lambda_tile_gen/`** in this repo:

- **`lambda_tile_gen/lambda_function.py`** – handler: receives Django payload, downloads TIFs, generates tiles, uploads to S3, callbacks to Django with results and logs.
- **`lambda_tile_gen/requirements.txt`** – Python deps: boto3, requests, rasterio, mercantile, Pillow, numpy.
- **`lambda_tile_gen/README.md`** – deploy instructions and your Lambda ARN.

**Handler:** `lambda_function.lambda_handler`  
**ARN:** `arn:aws:lambda:ap-south-1:471112704924:function:geomapping-tile-gen`

Package the contents (dependencies + `lambda_function.py`) into a zip and upload to that function, or use a Lambda layer for rasterio and package the rest. See `lambda_tile_gen/README.md` for build/deploy steps.

---

## 5. Create and configure the Lambda function (AWS)

### 5.1 Create the function (AWS Console or CLI)

- **Runtime:** Python 3.11 (or 3.12).
- **Timeout:** 15 minutes (max for Lambda); if your jobs are longer, use Step Functions or ECS and have that worker call the same callback.
- **Memory:** 2048 MB or more (tile generation can be memory-heavy).
- **Environment variables:** Pass the same S3/CloudFront config your Django app uses (bucket, region, CloudFront domain, etc.), plus:
  - `CALLBACK_SECRET` = same value as Django’s `TILE_CALLBACK_SECRET`.

### 5.2 IAM role for Lambda

The Lambda execution role needs at least:

- **S3:** GetObject, PutObject, DeleteObject (and ListBucket if you use it) on your tile bucket.
- **CloudFront:** CreateInvalidation if you invalidate from Lambda.
- **Network:** If the callback URL is public HTTPS, no VPC needed. If it’s in a VPC, ensure the Lambda can reach Django (security group + route).

### 5.3 Lambda input (what Django sends)

Django invokes Lambda with **InvocationType='Event'** (async) and a JSON payload like:

```json
{
  "webhook_event_id": 123,
  "callback_url": "https://layers.1acre.in/api/webhooks/tile-generation-result/",
  "callback_secret": "<TILE_CALLBACK_SECRET>",
  "listing_type": "developerland",
  "listing_id": 70,
  "tif_files": [
    { "id": 1, "file_name": "map.tif", "url": "https://...", "s3_tile_path": "developer_data/land/70/map.tif" }
  ],
  "s3_tile_base_path": "developer_data/land/70",
  "event_type": "developer_listing_media_uploaded",
  "action": "media_uploaded",
  "data_snapshot": { ... full webhook payload ... }
}
```

Your Lambda can either:

- Reuse the same logic as `DeveloperListingTileService.process_webhook()` (port the code and dependencies to Lambda), or
- Call a small helper that downloads TIF from `tif_files[].url`, generates tiles, uploads to S3, then POSTs to `callback_url` with the body from section 3.

### 5.4 Lambda: collect logs and callback

- While running, collect every log line (e.g. `[TILE_GEN]`, `[TIF_PROCESS]`, etc.) into a list of `{"ts": "<iso>", "level": "info|warning|error", "msg": "..."}`.
- On success or failure, **POST** to `callback_url` with:
  - `webhook_event_id`, `success`, `tiles_generated`, `tif_files_processed`, `processing_result`, `processing_error`, and the `logs` list.

Example (Python in Lambda):

```python
import urllib.request
import json
from datetime import datetime, timezone

logs = []

def log(level, msg):
    logs.append({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg})

# ... run tile generation, call log("info", "[TILE_GEN] Starting ...") etc. ...

payload = {
    "webhook_event_id": event["webhook_event_id"],
    "success": True,
    "tiles_generated": total_tiles,
    "tif_files_processed": len(tif_files),
    "processing_result": result_dict,
    "processing_error": "",
    "logs": logs,
}
req = urllib.request.Request(
    event["callback_url"],
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "X-Tile-Callback-Secret": event["callback_secret"],
    },
    method="POST",
)
urllib.request.urlopen(req)
```

---

## 6. Give Django permission to invoke Lambda

The machine/role that runs Django (e.g. EC2 instance profile or IAM user) must be allowed to call your Lambda:

- **Action:** `lambda:InvokeFunction`
- **Resource:** your Lambda function ARN

Example policy (attach to Django’s role):

```json
{
  "Effect": "Allow",
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:ap-south-1:YOUR_ACCOUNT:function:geomapping-tile-gen"
}
```

---

## 7. Checklist

- [ ] Migration applied (`tile_generation_logs` on `WebhookEvent`).
- [ ] Django env: `TILE_USE_LAMBDA=true`, `TILE_GENERATION_LAMBDA_ARN`, `TILE_CALLBACK_SECRET`; optionally `TILE_CALLBACK_BASE_URL`.
- [ ] Lambda created (Python 3.11+, timeout 15 min, enough memory).
- [ ] Lambda role: S3 (and CloudFront if needed), outbound HTTPS to Django.
- [ ] Lambda code: same tile logic as today, collect logs, POST to callback with `X-Tile-Callback-Secret` and the JSON body from section 3.
- [ ] Django role: `lambda:InvokeFunction` on the Lambda ARN.
- [ ] Test: send a developer-listing-media webhook with a TIF → Lambda runs → callback updates WebhookEvent and `tile_generation_logs`; check in Django admin or `/api/webhook-events/`.

---

## 8. Optional: SQS instead of direct invoke

To decouple further and retry on failure:

1. Create an SQS queue and trigger Lambda from that queue.
2. In Django, instead of `lambda.invoke`, send a message to SQS with the same payload.
3. Lambda consumes from SQS and runs the job, then callbacks to Django as above.

Django code can be extended later to support an optional `TILE_SQS_QUEUE_URL` and publish there when set; until then, direct Lambda invoke is implemented.

---

## 9. Viewing logs in Django

- **Admin:** Open a **Webhook event** → expand **Tile generation logs (Lambda callback)** to see the stored log lines.
- **API:** `GET /api/webhook-events/?processed=true`; each event includes `tile_generation_logs` in the response (see `WebhookEventSerializer`).
