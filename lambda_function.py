import json
import boto3
import time
from urllib.parse import unquote_plus
from datetime import datetime
from collections import defaultdict

cloudfront = boto3.client('cloudfront')

# Configuration - Update these values directly
DISTRIBUTION_ID = 'E3VZOEKNMYD012'  # Your CloudFront distribution ID
MAX_INVALIDATIONS = 15  # Maximum paths per invalidation batch
MAX_FILES_PER_BATCH = 100  # Maximum files to process in one Lambda execution (reduced for massive uploads)
MAX_INVALIDATIONS_PER_DAY = 1000  # CloudFront daily limit

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

# Tile-specific rules for large tile uploads
TILE_PATTERNS = {
    'tiles': 'batch_invalidate',  # For tile directories, use batch invalidation
    'viewer.html': 'self_only',   # Viewer files
    'tilejson.json': 'self_only', # TileJSON files
    'style.json': 'self_only'     # Style files
}

# For massive uploads (100M+ files), we need to be extremely conservative
MASSIVE_UPLOAD_THRESHOLD = 10000  # If more than 10k files in one batch, use minimal invalidation

def get_invalidation_paths(key):
    """Determine which paths to invalidate based on the file"""
    
    # Ensure key starts with /
    if not key.startswith('/'):
        key = '/' + key
    
    # Check skip patterns first
    for pattern, action in INVALIDATION_RULES.items():
        if pattern in key.lower() and action == 'skip':
            return []
    
    # Check specific file rules
    filename = key.split('/')[-1].lower()
    if filename in INVALIDATION_RULES:
        paths = INVALIDATION_RULES[filename]
        if isinstance(paths, list):
            return paths
        elif paths == 'invalidate_all':
            return ['/*']
        elif paths == 'self_only':
            return [key]
        elif paths == 'skip':
            return []
    
    # Check tile-specific patterns for large tile uploads
    for pattern, rule in TILE_PATTERNS.items():
        if pattern in key.lower():
            if rule == 'batch_invalidate':
                # For tile uploads, invalidate the parent directory instead of individual files
                path_parts = key.split('/')
                if len(path_parts) >= 4:  # e.g., /karnataka/bengaluru/bengaluru_strr/18/187799/121307.png
                    # Invalidate the layer directory (e.g., /karnataka/bengaluru/bengaluru_strr/*)
                    layer_path = '/'.join(path_parts[:4]) + '/*'
                    return [layer_path]
            elif rule == 'self_only':
                return [key]
    
    # Check extension rules
    if '.' in key:
        ext = '.' + key.split('.')[-1].lower()
        if ext in INVALIDATION_RULES:
            action = INVALIDATION_RULES[ext]
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
    """Main Lambda handler - Optimized for massive file uploads (100M+ files)"""
    
    print(f"Processing {len(event['Records'])} S3 events")
    
    # For massive uploads, we need to be extremely conservative
    tile_files = []
    critical_files = []
    other_files = []
    
    # Categorize files by importance
    for record in event['Records']:
        event_name = record['eventName']
        
        # Only process object creation/update events
        if not event_name.startswith('ObjectCreated:'):
            continue
        
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        
        # Categorize files
        if any(pattern in key.lower() for pattern in ['tiles', '.png', '.jpg', '.jpeg']):
            tile_files.append(key)
        elif any(pattern in key.lower() for pattern in ['viewer.html', 'tilejson.json', 'style.json', 'index.html']):
            critical_files.append(key)
        else:
            other_files.append(key)
    
    total_files = len(tile_files) + len(critical_files) + len(other_files)
    print(f"File breakdown: {len(tile_files)} tiles, {len(critical_files)} critical, {len(other_files)} other")
    
    # For massive uploads, use minimal invalidation strategy
    if total_files > MASSIVE_UPLOAD_THRESHOLD:
        print(f"MASSIVE UPLOAD DETECTED: {total_files} files")
        print("Using minimal invalidation strategy to avoid rate limits")
        
        # Only invalidate critical files and use wildcard for tiles
        invalidation_paths = []
        
        # Always invalidate critical files
        for file_path in critical_files:
            invalidation_paths.extend(get_invalidation_paths(file_path))
        
        # For tiles, use a single wildcard invalidation for the entire bucket
        if tile_files:
            # Extract the top-level directory structure
            # e.g., /karnataka/bengaluru/bengaluru_strr/* for all STRR tiles
            tile_dirs = set()
            for tile_file in tile_files:
                parts = tile_file.split('/')
                if len(parts) >= 4:
                    # Get the layer directory (e.g., /karnataka/bengaluru/bengaluru_strr)
                    layer_dir = '/'.join(parts[:4])
                    tile_dirs.add(layer_dir + '/*')
            
            invalidation_paths.extend(list(tile_dirs))
        
        # Remove duplicates
        invalidation_paths = list(set(invalidation_paths))
        
        if invalidation_paths:
            print(f"Creating {len(invalidation_paths)} strategic invalidations for {total_files} files")
            result = create_invalidation(invalidation_paths)
            
            if result['success']:
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': f'Strategic invalidation created for {total_files} files',
                        'invalidationId': result['invalidationId'],
                        'paths': result['paths'],
                        'total_files': total_files,
                        'strategy': 'massive_upload_optimized'
                    })
                }
            else:
                return {
                    'statusCode': 202,
                    'body': json.dumps({
                        'message': 'Invalidation delayed due to rate limits',
                        'error': result.get('error'),
                        'total_files': total_files,
                        'strategy': 'massive_upload_optimized'
                    })
                }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No invalidation needed for massive upload',
                    'total_files': total_files,
                    'strategy': 'massive_upload_optimized'
                })
            }
    
    # For smaller uploads, use the original logic
    else:
        print(f"Standard upload: {total_files} files")
        
        # Group files by directory to optimize invalidations
        directory_groups = defaultdict(list)
        processed_files = []
        
        # Process all files
        all_files = tile_files + critical_files + other_files
        for key in all_files:
            paths = get_invalidation_paths(key)
            
            if paths:
                # Group by directory for batch processing
                for path in paths:
                    if path.endswith('/*'):
                        # This is already a directory wildcard
                        directory_groups[path].append(key)
                    else:
                        # Group individual files by their parent directory
                        dir_path = '/'.join(path.split('/')[:-1]) + '/*'
                        directory_groups[dir_path].append(key)
                
                processed_files.append(key)
        
        if not directory_groups:
            print("No paths require invalidation")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No invalidation needed',
                    'processed_files': len(processed_files)
                })
            }
        
        # Limit the number of files processed to avoid timeout
        total_grouped_files = sum(len(files) for files in directory_groups.values())
        if total_grouped_files > MAX_FILES_PER_BATCH:
            print(f"Too many files ({total_grouped_files}), processing only first {MAX_FILES_PER_BATCH}")
            # Take the largest directories first
            sorted_groups = sorted(directory_groups.items(), key=lambda x: len(x[1]), reverse=True)
            directory_groups = {}
            file_count = 0
            for dir_path, files in sorted_groups:
                if file_count + len(files) <= MAX_FILES_PER_BATCH:
                    directory_groups[dir_path] = files
                    file_count += len(files)
                else:
                    # Take partial files from this directory
                    remaining = MAX_FILES_PER_BATCH - file_count
                    directory_groups[dir_path] = files[:remaining]
                    break
        
        # Create invalidations for each directory group
        results = []
        for dir_path, files in directory_groups.items():
            print(f"Creating invalidation for {dir_path} ({len(files)} files)")
            result = create_invalidation([dir_path])
            results.append(result)
            
            # Add small delay between invalidations to avoid rate limits
            if len(results) > 1:
                time.sleep(0.5)
        
        # Check results
        successful_invalidations = [r for r in results if r['success']]
        failed_invalidations = [r for r in results if not r['success']]
        
        if successful_invalidations:
            print(f"Successfully created {len(successful_invalidations)} invalidations")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Created {len(successful_invalidations)} invalidations successfully',
                    'successful_invalidations': len(successful_invalidations),
                    'failed_invalidations': len(failed_invalidations),
                    'processed_files': len(processed_files),
                    'total_files': total_files,
                    'strategy': 'standard_batch'
                })
            }
        else:
            # All invalidations failed
            print(f"All {len(failed_invalidations)} invalidations failed")
            return {
                'statusCode': 202,
                'body': json.dumps({
                    'message': 'All invalidations delayed due to rate limits',
                    'failed_invalidations': len(failed_invalidations),
                    'processed_files': len(processed_files),
                    'total_files': total_files,
                    'strategy': 'standard_batch'
                })
            }
