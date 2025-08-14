import boto3
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geomapping.settings')
django.setup()

from django.conf import settings

# Get AWS credentials from Django settings
aws_access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
aws_secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal-layers')

print(f"AWS Access Key: {'Set' if aws_access_key else 'Not set'}")
print(f"AWS Secret Key: {'Set' if aws_secret_key else 'Not set'}")
print(f"Region: {region}")
print(f"Bucket: {bucket}")

# Create S3 client
s3 = boto3.client(
    's3',
    region_name=region,
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key
)

# Check the specific file
key = 'tiles/karnataka/bengaluru/bengaluru_master_plan_2015/10/732/474.png'
print(f"\nChecking: s3://{bucket}/{key}")

try:
    response = s3.head_object(Bucket=bucket, Key=key)
    print(f"✅ File exists! Size: {response['ContentLength']} bytes")
    print(f"Content-Type: {response.get('ContentType', 'Not set')}")
except Exception as e:
    print(f"❌ Error: {e}")

# List some files in the directory to see what's there
print(f"\nListing files in: tiles/karnataka/bengaluru/bengaluru_master_plan_2015/10/")
try:
    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix='tiles/karnataka/bengaluru/bengaluru_master_plan_2015/10/',
        MaxKeys=10
    )
    
    if 'Contents' in response:
        print(f"Found {len(response['Contents'])} files:")
        for obj in response['Contents'][:5]:  # Show first 5
            print(f"  - {obj['Key']} ({obj['Size']} bytes)")
    else:
        print("No files found in this directory")
        
except Exception as e:
    print(f"❌ Error listing files: {e}")
