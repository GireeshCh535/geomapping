# CloudFront Auto-Invalidation Lambda Setup Guide

## Overview
This guide sets up an automated CloudFront invalidation system that triggers when files are uploaded to your S3 bucket `gis-portal-layers`.

## Prerequisites
- AWS Account with admin permissions
- S3 bucket: `gis-portal-layers`
- CloudFront distribution ID: `E3VZOEKNMYD012`
- AWS CLI configured

## Step 1: Create IAM Role for Lambda

### 1.1 Create Trust Policy
Go to IAM Console → Roles → Create Role
- Select trusted entity: **Lambda**
- Click "Next"

### 1.2 Create Custom Policy
Click "Create Policy" and use this JSON:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateInvalidation",
                "cloudfront:GetInvalidation",
                "cloudfront:ListInvalidations"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::gis-portal-layers",
                "arn:aws:s3:::gis-portal-layers/*"
            ]
        }
    ]
}
```

- Name: `CloudFrontInvalidationLambdaPolicy`
- Create policy

### 1.3 Attach Policies to Role
- Attach: `CloudFrontInvalidationLambdaPolicy`
- Attach: `AWSLambdaBasicExecutionRole` (for CloudWatch logs)
- Role name: `CloudFrontInvalidationLambdaRole`
- Create role

## Step 2: Create Lambda Function

### 2.1 Create Function
Go to Lambda Console → Create Function
- Function name: `auto-cloudfront-invalidation`
- Runtime: **Python 3.11**
- Architecture: **x86_64**
- Execution role: **Use existing role** → `CloudFrontInvalidationLambdaRole`
- Create function

### 2.2 Upload Code
- Delete the default code
- Copy and paste the code from `lambda_function.py` (created in your project directory)
- Click "Deploy"

### 2.3 Configure Environment Variables
Go to Configuration → Environment Variables → Edit
Add:
- `DISTRIBUTION_ID`: `E3VZOEKNMYD012`
- `MAX_INVALIDATIONS_PER_BATCH`: `15`

### 2.4 Configure Function Settings
- Timeout: **1 minute**
- Memory: **128 MB**
- Save

## Step 3: Configure S3 Bucket Event Trigger

### 3.1 Create Event Notification
Go to S3 Console → `gis-portal-layers` bucket → Properties → Event notifications
Click "Create event notification"

### 3.2 Configure Event
- Event name: `cloudfront-invalidation-trigger`
- Prefix: (leave blank to monitor all files)
- Suffix: (leave blank)
- Event types: Check ✅ **All object create events**

### 3.3 Set Destination
- Destination: **Lambda function**
- Lambda function: `auto-cloudfront-invalidation`
- Save changes

## Step 4: Test the Setup

### 4.1 Upload Test File
```bash
echo "test" > test.html
aws s3 cp test.html s3://gis-portal-layers/test.html
```

### 4.2 Check Lambda Logs
Go to CloudWatch → Log groups → `/aws/lambda/auto-cloudfront-invalidation`
Look for recent log stream and verify the function executed

### 4.3 Check CloudFront Invalidations
Go to CloudFront → Distribution `E3VZOEKNMYD012` → Invalidations
You should see a new invalidation in progress

## Step 5: Monitor and Optimize

### 5.1 CloudWatch Dashboard
Create dashboard: `cloudfront-invalidations`
Add widgets for:
- Lambda invocations
- Lambda errors
- Lambda duration
- Custom metrics

### 5.2 Cost Monitoring
- Set up billing alerts for CloudFront invalidations
- Monitor monthly invalidation count (first 1000 are free)
- Review invalidation patterns

## Smart Invalidation Rules

The Lambda function uses intelligent rules:

### Critical Files (Invalidate All)
- `index.html` → Invalidates `/` and `/index.html`
- `.css` files → Invalidates `/*` (affects entire site)
- `.js` files → Invalidates `/*` (affects entire site)

### Media Files (Self Only)
- `.png`, `.jpg`, `.gif`, `.svg` → Invalidates only the specific file
- `.mp4`, `.webm` → Invalidates only the specific file

### Documents (Self Only)
- `.pdf`, `.doc`, `.docx` → Invalidates only the specific file

### Skipped Files
- `.git`, `.DS_Store`, `.log` → No invalidation

## Cost Optimization

### Batch Processing
- Waits for multiple uploads before invalidating
- Uses wildcard `/*` if too many specific paths
- Maximum 15 paths per invalidation batch

### Smart Path Selection
- Uses directory invalidation for multiple files
- Prevents duplicate invalidations
- Optimizes for CloudFront limits

## Troubleshooting

### Lambda Not Triggering
1. Check S3 event configuration
2. Verify Lambda has permission to be invoked by S3
3. Check CloudWatch logs for errors

### Invalidations Not Working
1. Verify CloudFront distribution ID is correct
2. Check Lambda IAM role has CloudFront permissions
3. Ensure distribution is deployed

### Too Many Invalidations Error
1. CloudFront allows max 3 concurrent invalidations
2. Reduce `MAX_INVALIDATIONS_PER_BATCH` if needed
3. Implement queuing with SQS for high-volume scenarios

## Files Created
- `lambda_function.py` - Main Lambda function code
- `lambda-deployment.zip` - Deployment package
- `test-event.json` - Test event for Lambda
- `lambda-trust-policy.json` - IAM trust policy
- `lambda-permissions-policy.json` - IAM permissions policy

## Next Steps
1. Deploy the Lambda function using the AWS Console
2. Configure S3 event notifications
3. Test with a sample file upload
4. Monitor CloudWatch logs and CloudFront invalidations
5. Set up cost monitoring and alerts

## Support
If you encounter issues:
1. Check CloudWatch logs for detailed error messages
2. Verify all IAM permissions are correctly configured
3. Ensure the CloudFront distribution ID is correct
4. Test with a simple file upload first
