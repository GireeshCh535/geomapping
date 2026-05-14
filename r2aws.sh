# r2aws: AWS CLI wrapper that talks to Cloudflare R2 instead of AWS S3.
#
# Reads R2_* env vars from .r2.env. Source both before use:
#   source .r2.env
#   source r2aws.sh
#
# Then run aws-style commands against R2:
#   r2aws s3 ls s3://$R2_BUCKET/
#   r2aws s3 sync ./tiles/ s3://$R2_BUCKET/path/ --exclude ".DS_Store"
#
# Requires the aws CLI v2 (`brew install awscli`).

r2aws() {
  if [ -z "${R2_ACCOUNT_ID:-}" ] || [ -z "${R2_ACCESS_KEY_ID:-}" ] || [ -z "${R2_SECRET_ACCESS_KEY:-}" ]; then
    echo "r2aws: R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY not set. Run: source .r2.env" >&2
    return 2
  fi
  AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
  AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
  AWS_SESSION_TOKEN="" \
  AWS_DEFAULT_REGION="${R2_REGION:-auto}" \
  AWS_REGION="${R2_REGION:-auto}" \
  AWS_EC2_METADATA_DISABLED=true \
  AWS_REQUEST_CHECKSUM_CALCULATION=when_required \
  AWS_RESPONSE_CHECKSUM_VALIDATION=when_required \
  aws --endpoint-url "${R2_ENDPOINT_URL:-https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com}" "$@"
}
