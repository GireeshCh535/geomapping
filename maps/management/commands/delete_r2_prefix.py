import os
import time
from typing import Iterable, List

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand, CommandError

# R2 occasionally returns 500-class errors on bulk DeleteObjects; retry these.
_DELETE_RETRYABLE_CODES = frozenset(
    {"InternalError", "SlowDown", "ServiceUnavailable", "RequestTimeout"}
)


def delete_objects_with_retry(client, bucket: str, keys: List[str], max_attempts: int = 10):
    payload = {"Objects": [{"Key": key} for key in keys], "Quiet": True}
    delay = 1.0
    for attempt in range(max_attempts):
        try:
            return client.delete_objects(Bucket=bucket, Delete=payload)
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if code in _DELETE_RETRYABLE_CODES and attempt + 1 < max_attempts:
                time.sleep(min(delay, 60.0))
                delay = min(delay * 2, 60.0)
                continue
            raise


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


class Command(BaseCommand):
    help = (
        "Delete all objects in a Cloudflare R2 prefix. "
        "Defaults to prefix '30/' for your requested folder deletion."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bucket",
            type=str,
            default=os.environ.get("CLOUDFLARE_R2_BUCKET_NAME", ""),
            help="R2 bucket name. Defaults to CLOUDFLARE_R2_BUCKET_NAME.",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            default="30/",
            help="Prefix/folder to delete (default: 30/).",
        )
        parser.add_argument(
            "--endpoint-url",
            type=str,
            default=os.environ.get("CLOUDFLARE_R2_ENDPOINT_URL", ""),
            help="R2 S3 endpoint URL. Defaults to CLOUDFLARE_R2_ENDPOINT_URL.",
        )
        parser.add_argument(
            "--access-key-id",
            type=str,
            default=os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID", ""),
            help="R2 access key. Defaults to CLOUDFLARE_R2_ACCESS_KEY_ID.",
        )
        parser.add_argument(
            "--secret-access-key",
            type=str,
            default=os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY", ""),
            help="R2 secret key. Defaults to CLOUDFLARE_R2_SECRET_ACCESS_KEY.",
        )
        parser.add_argument(
            "--region-name",
            type=str,
            default=os.environ.get("CLOUDFLARE_R2_REGION_NAME", "auto") or "auto",
            help="R2 region (default: auto).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list matching keys without deleting.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation for destructive delete.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Keys per DeleteObjects call (max 1000). Lower if R2 returns InternalError.",
        )

    def handle(self, *args, **options):
        bucket = (options["bucket"] or "").strip()
        prefix = (options["prefix"] or "").strip()
        endpoint_url = (options["endpoint_url"] or "").strip()
        access_key_id = (options["access_key_id"] or "").strip()
        secret_access_key = (options["secret_access_key"] or "").strip()
        region_name = (options["region_name"] or "auto").strip() or "auto"
        dry_run = bool(options["dry_run"])
        skip_confirmation = bool(options["yes"])
        batch_size = int(options["batch_size"] or 500)
        if batch_size < 1 or batch_size > 1000:
            raise CommandError("--batch-size must be between 1 and 1000 (S3 API limit).")

        if not bucket:
            raise CommandError(
                "Bucket name is required. Pass --bucket or set CLOUDFLARE_R2_BUCKET_NAME."
            )
        if not prefix:
            raise CommandError("Prefix is required. Example: --prefix 30/")
        if not endpoint_url:
            raise CommandError(
                "Endpoint URL is required. Pass --endpoint-url or set CLOUDFLARE_R2_ENDPOINT_URL."
            )
        if not access_key_id or not secret_access_key:
            raise CommandError(
                "R2 credentials are required. Pass --access-key-id/--secret-access-key "
                "or set CLOUDFLARE_R2_ACCESS_KEY_ID/CLOUDFLARE_R2_SECRET_ACCESS_KEY."
            )

        if not prefix.endswith("/"):
            prefix = f"{prefix}/"

        self.stdout.write(
            self.style.WARNING(f"Scanning bucket='{bucket}' for prefix='{prefix}'...")
        )

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=Config(signature_version="s3v4"),
        )

        keys: List[str] = []
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                kwargs["ContinuationToken"] = token

            response = client.list_objects_v2(**kwargs)
            contents = response.get("Contents", [])
            keys.extend(obj["Key"] for obj in contents if "Key" in obj)

            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")

        if not keys:
            self.stdout.write(
                self.style.WARNING("No objects found for this prefix. Nothing to delete.")
            )
            return

        self.stdout.write(self.style.WARNING(f"Found {len(keys)} objects under '{prefix}'"))

        if dry_run:
            preview = keys[:20]
            for key in preview:
                self.stdout.write(f" - {key}")
            if len(keys) > len(preview):
                self.stdout.write(f"... and {len(keys) - len(preview)} more")
            self.stdout.write(self.style.SUCCESS("Dry run complete. No objects deleted."))
            return

        if not skip_confirmation:
            confirm = input(
                f"Type 'DELETE {prefix}' to permanently remove {len(keys)} objects from {bucket}: "
            ).strip()
            if confirm != f"DELETE {prefix}":
                self.stdout.write(self.style.ERROR("Confirmation did not match. Aborted."))
                return

        deleted = 0
        for batch in chunked(keys, batch_size):
            response = delete_objects_with_retry(client, bucket, batch)
            errors = response.get("Errors", [])
            if errors:
                raise CommandError(f"Delete failed for some keys: {errors[:3]}")
            # With Quiet=True the API may omit Deleted entries; count the batch as removed.
            deleted += len(batch)
            time.sleep(0.05)

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} objects from prefix '{prefix}'"))