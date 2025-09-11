import json
import boto3
import time
from urllib.parse import unquote_plus
from datetime import datetime

cloudfront = boto3.client('cloudfront')

# Configuration - Update these values directly
DISTRIBUTION_ID = 'E3VZOEKNMYD012'  # Your CloudFront distribution ID
MAX_INVALIDATIONS = 15  # Maximum paths per invalidation batch

# Smart invalidation rules
INVALIDATION_RULES = {
    # Critical files - always invalidate root when these change
    'index.html': ['/', '/index.html'],
    'error.html': ['/error.html', '/404.html'],
    
    # Asset patterns
    '.css': 'invalidate_all',  # CSS changes affect entire site
    '.js': 'invalidate_all',   # JS changes affect entire site
    '.json': 'self_only',      # JSON files only affect themselves
    '.xml': 'self_only',       # XML files only affect themselves
    
    # Media files - only invalidate themselves
    '.jpg': 'self_only',
    '.jpeg': 'self_only',
    '.png': 'self_only',
    '.gif': 'self_only',
    '.svg': 'self_only',
    '.webp': 'self_only',
    '.mp4': 'self_only',
    '.webm': 'self_only',
    
    # Documents
    '.pdf': 'self_only',
    '.doc': 'self_only',
    '.docx': 'self_only',
    
    # Skip these entirely
    '.git': 'skip',
    '.DS_Store': 'skip',
    'thumbs.db': 'skip',
    '.log': 'skip'
}

def get_invalidation_paths(key):
    """Determine which paths to invalidate based on the file"""
    
    # Ensure key starts with /
    if not key.startswith('/'):
        key = '/' + key
    
    # Check skip patterns
    for pattern, action in INVALIDATION_RULES.items():
        if pattern in key.lower() and action == 'skip':
            return []
    
    # Check specific file rules
    filename = key.split('/')[-1]
    if filename in INVALIDATION_RULES:
        paths = INVALIDATION_RULES[filename]
        if isinstance(paths, list):
            return paths
    
    # Check extension rules
    for pattern, action in INVALIDATION_RULES.items():
        if pattern in key.lower():
            if action == 'invalidate_all':
                return ['/*']
            elif action == 'self_only':
                return [key]
            elif action == 'skip':
                return []
    
    # Default: invalidate the specific file and check if it's index
    paths = [key]
    
    # If it's an index file in a subdirectory, also invalidate the directory
    if 'index.html' in key:
        dir_path = key.rsplit('/index.html', 1)[0]
        if dir_path:
            paths.extend([dir_path, dir_path + '/'])
    
    return paths

def create_invalidation(paths):
    """Create CloudFront invalidation"""
    
    # Remove duplicates and sort
    paths = sorted(list(set(paths)))
    
    # If we're invalidating too many specific paths, use wildcard
    if len(paths) > MAX_INVALIDATIONS:
        print(f"Too many paths ({len(paths)}), using wildcard invalidation")
        paths = ['/*']
    
    print(f"Creating invalidation for paths: {paths}")
    
    try:
        response = cloudfront.create_invalidation(
            DistributionId=DISTRIBUTION_ID,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths
                },
                'CallerReference': f"auto-{datetime.now().isoformat()}-{time.time()}"
            }
        )
        
        return {
            'success': True,
            'invalidationId': response['Invalidation']['Id'],
            'status': response['Invalidation']['Status'],
            'paths': paths
        }
        
    except cloudfront.exceptions.TooManyInvalidationsInProgress:
        print("Too many invalidations in progress, will retry later")
        return {
            'success': False,
            'error': 'TooManyInvalidationsInProgress',
            'message': 'Maximum concurrent invalidations reached, will retry later'
        }
    
    except Exception as e:
        print(f"Error creating invalidation: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def lambda_handler(event, context):
    """Main Lambda handler"""
    
    print(f"Processing {len(event['Records'])} S3 events")
    
    all_paths = []
    processed_files = []
    
    # Process each S3 event
    for record in event['Records']:
        event_name = record['eventName']
        
        # Only process object creation/update events
        if not event_name.startswith('ObjectCreated:'):
            continue
        
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        
        print(f"Processing: {event_name} for {key} in {bucket}")
        
        # Get invalidation paths for this file
        paths = get_invalidation_paths(key)
        
        if paths:
            all_paths.extend(paths)
            processed_files.append(key)
    
    if not all_paths:
        print("No paths require invalidation")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No invalidation needed',
                'processed_files': processed_files
            })
        }
    
    # Check if we should invalidate everything
    if '/*' in all_paths:
        all_paths = ['/*']
    else:
        # Remove duplicates
        all_paths = list(set(all_paths))
    
    # Create the invalidation
    result = create_invalidation(all_paths)
    
    if result['success']:
        print(f"Successfully created invalidation: {result['invalidationId']}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Invalidation created successfully',
                'invalidationId': result['invalidationId'],
                'paths': result['paths'],
                'processed_files': processed_files
            })
        }
    else:
        # Don't fail the Lambda, just log the issue
        print(f"Failed to create invalidation: {result.get('error')}")
        return {
            'statusCode': 202,
            'body': json.dumps({
                'message': 'Invalidation delayed',
                'error': result.get('error'),
                'processed_files': processed_files
            })
        }
