# maps/management/commands/poll_sqs_tile_worker.py
"""
Poll SQS for tile jobs (TIF and land/plot MVT) and process them.
Uploads go to Cloudflare R2 (S3TileUploadService / tile_storage); tiles are served from PUBLIC_TILE_CDN_HOST.

Only the job type from the message is run: developer-listing webhook -> job_type=tif only;
land-plot webhook -> job_type=land_plot_mvt only. No cross-triggering.

Usage:
  python manage.py poll_sqs_tile_worker
  python manage.py poll_sqs_tile_worker --wait 20   # long-poll 20s

Requires: CLOUDFLARE_R2_* and PUBLIC_TILE_CDN_HOST (same as Django app). TILE_SQS_QUEUE_URL if using SQS.
For AWS SQS only: AWS credentials or EC2 instance profile (sqs:ReceiveMessage, sqs:DeleteMessage).
"""

import json
import logging
import time
from datetime import datetime, timezone

import boto3
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from maps.tile_debug import tile_debug_always

logger = logging.getLogger(__name__)


class _TileLogCapture(logging.Handler):
    """Capture log records during tile job run for callback tile_generation_logs."""

    def __init__(self, log_list):
        super().__init__()
        self.log_list = log_list

    def emit(self, record):
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            level = (record.levelname or "info").lower()
            msg = self.format(record) if self.formatter else (record.getMessage() or "")
            self.log_list.append({"ts": ts, "level": level, "msg": str(msg)[:2000]})
        except Exception:
            pass


class Command(BaseCommand):
    help = "Poll SQS for tile jobs (tif / land_plot_mvt), run tile gen, upload to R2, POST callback."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wait",
            type=int,
            default=20,
            help="Long-poll wait time in seconds (default 20).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one batch and exit (for cron).",
        )

    def handle(self, *args, **options):
        queue_url = getattr(settings, "TILE_SQS_QUEUE_URL", "").strip()
        if not queue_url:
            self.stderr.write("TILE_SQS_QUEUE_URL not set. Exiting.")
            return
        region = getattr(settings, "AWS_DEFAULT_REGION", "ap-south-1")
        wait = max(1, min(options["wait"], 20))
        once = options["once"]

        self.stdout.write(f"Starting SQS tile worker queue={queue_url} wait={wait}s once={once}")
        sqs = boto3.client("sqs", region_name=region)

        while True:
            try:
                resp = sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=wait,
                    VisibilityTimeout=300,
                )
                messages = resp.get("Messages") or []
                if not messages:
                    if once:
                        self.stdout.write("No messages, exiting (--once).")
                        return
                    logger.debug("Poll: 0 messages (queue empty or in-flight)")
                    continue
                self.stdout.write(f"Poll: received {len(messages)} message(s)")
                for msg in messages:
                    self._process_message(sqs, queue_url, msg)
                if once:
                    return
            except Exception as e:
                logger.exception("SQS receive failed: %s", e)
                time.sleep(5)

    def _process_message(self, sqs, queue_url, msg):
        receipt_handle = msg.get("ReceiptHandle")
        body = msg.get("Body", "{}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON body: %s", e)
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
            return
        event = payload.get("event")
        job_type = payload.get("job_type")
        data = payload.get("data") or {}
        msg_id = msg.get("MessageId", "?")
        self.stdout.write(f"Processing message_id={msg_id} job_type={job_type} event={event}")
        tile_debug_always(
            f"SQS job start msg_id={msg_id} job_type={job_type} event={event} listing_id={data.get('listing_id')}"
        )
        if job_type not in ("tif", "land_plot_mvt"):
            tile_debug_always(f"SQS unknown job_type={job_type} msg_id={msg_id}, deleting")
            logger.warning("Unknown job_type=%s, deleting message", job_type)
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
            return
        try:
            # Pool may hand out a connection closed by PG during SQS long-poll idle; refresh before ORM.
            close_old_connections()
            # Only run the handler for this job type (no cross-trigger: TIF vs land_plot_mvt)
            if job_type == "tif":
                self._process_tif_job(data)
            elif job_type == "land_plot_mvt":
                self._process_land_plot_mvt_job(data)
            else:
                logger.warning("Unhandled job_type=%s", job_type)
        except Exception as e:
            tile_debug_always(f"SQS job FAIL msg_id={msg_id} job_type={job_type} err={e}")
            logger.exception("Job failed job_type=%s: %s", job_type, e)
            # Do not delete so message can retry after visibility timeout
            return
        tile_debug_always(f"SQS job OK msg_id={msg_id} job_type={job_type}, deleting message")
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    def _process_tif_job(self, data):
        from maps.developer_listing_tile_service import DeveloperListingTileService

        self.stdout.write("Starting TIF tile generation (developer-listing webhook only)...")
        captured = []
        maps_logger = logging.getLogger("maps")
        handler = _TileLogCapture(captured)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.setLevel(logging.DEBUG)
        maps_logger.addHandler(handler)
        try:
            webhook_data = {
                "event_type": data.get("event_type", ""),
                "action": data.get("action", ""),
                "listing_type": data.get("listing_type", ""),
                "listing_id": data.get("listing_id"),
                "tif_files": data.get("tif_files", []),
                "s3_tile_base_path": data.get("s3_tile_base_path", ""),
            }
            service = DeveloperListingTileService()
            result = service.process_webhook(webhook_data)
            self._post_callback(
                data,
                tiles_generated=result.get("total_tiles_generated", 0),
                tif_files_processed=result.get("tif_files_processed", 0),
                processing_result=result,
                processing_error=result.get("error", ""),
                logs=captured,
            )
        finally:
            maps_logger.removeHandler(handler)

    def _process_land_plot_mvt_job(self, data):
        from maps.land_plot_tile_refresh import (
            get_affected_land_plot_tile_keys,
            refresh_tiles_for_listing,
        )

        self.stdout.write("Starting land/plot MVT tile refresh (land-plot webhook only)...")
        captured = []
        maps_logger = logging.getLogger("maps")
        handler = _TileLogCapture(captured)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.setLevel(logging.DEBUG)
        maps_logger.addHandler(handler)
        try:
            lat = data.get("lat")
            lng = data.get("lng")
            if lat is None or lng is None:
                logger.warning("land_plot_mvt job missing lat/lng")
                self._post_callback(data, tiles_generated=0, processing_error="Missing lat/lng", logs=captured)
                return
            affected = get_affected_land_plot_tile_keys(lng, lat)
            refresh_tiles_for_listing(lat, lng)
            self._post_callback(
                data,
                tiles_generated=len(affected),
                tif_files_processed=0,
                processing_result={"tiles_refreshed": len(affected)},
                logs=captured,
            )
        finally:
            maps_logger.removeHandler(handler)

    def _post_callback(
        self,
        data,
        tiles_generated=0,
        tif_files_processed=0,
        processing_result=None,
        processing_error="",
        logs=None,
    ):
        callback_url = (data or {}).get("callback_url")
        if not callback_url:
            logger.warning("No callback_url in job data, skipping POST")
            return
        secret = (data or {}).get("callback_secret", "")
        normalized_logs = []
        if isinstance(logs, list):
            for item in logs[:10000]:
                if isinstance(item, dict):
                    normalized_logs.append({
                        "ts": str(item.get("ts", "")),
                        "level": str(item.get("level", "info")),
                        "msg": str(item.get("msg", "")),
                    })
        body = {
            "webhook_event_id": data.get("webhook_event_id"),
            "tiles_generated": tiles_generated,
            "tif_files_processed": tif_files_processed,
            "processing_result": processing_result or {},
            "processing_error": str(processing_error)[:65535],
            "logs": normalized_logs,
        }
        try:
            r = requests.post(
                callback_url,
                json=body,
                headers={"X-Tile-Callback-Secret": secret, "Content-Type": "application/json"},
                timeout=30,
            )
            if r.status_code != 200:
                logger.warning("Callback POST %s status=%s body=%s", callback_url, r.status_code, r.text[:200])
            else:
                logger.info("Callback POST %s ok", callback_url)
        except Exception as e:
            logger.exception("Callback POST failed: %s", e)