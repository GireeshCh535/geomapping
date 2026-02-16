# maps/services/s3_upload_service.py
import boto3
import os
from pathlib import Path
from django.conf import settings
from botocore.exceptions import ClientError, NoCredentialsError
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class S3TileUploadService:
    """Service for uploading generated tiles to S3"""
    
    def __init__(self):
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal')
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        
    def upload_file(self, local_file_path, s3_key):
        """Upload a single file to S3 (Fixed - No ACL)"""
        try:
            # Determine content type
            content_type, _ = mimetypes.guess_type(local_file_path)
            if not content_type:
                content_type = 'application/octet-stream'
            
            # No caching - always serve fresh content
            extra_args = {
                'ContentType': content_type,
                'CacheControl': 'no-cache, no-store, must-revalidate',  # No caching
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            
            self.s3_client.upload_file(
                local_file_path, 
                self.bucket_name, 
                s3_key, 
                ExtraArgs=extra_args
            )
            
            return {
                'success': True,
                'url': f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}",
                's3_key': s3_key,
                'size': os.path.getsize(local_file_path)
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload {s3_key}: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error uploading {s3_key}: {e}")
            return {'success': False, 'error': str(e)}
    
    def upload_city_tiles(self, city_slug, tile_type='png'):
        """Upload all tiles for a specific city"""
        
        if tile_type == 'png':
            local_base_dir = Path('static/tiles_png') / city_slug
            file_pattern = '*.png'
        else:  # mvt
            local_base_dir = Path('media/tiles') / city_slug  
            file_pattern = '*.mvt'
        
        if not local_base_dir.exists():
            return {
                'success': False, 
                'error': f"Local tile directory not found: {local_base_dir}"
            }
        
        # Find all tile files
        tile_files = list(local_base_dir.rglob(file_pattern))
        
        if not tile_files:
            return {
                'success': False,
                'error': f"No {tile_type} files found in {local_base_dir}"
            }
        
        # Upload files with progress tracking
        uploaded_count = 0
        failed_count = 0
        total_size = 0
        
        # Use ThreadPoolExecutor for concurrent uploads
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all upload tasks
            future_to_file = {}
            for tile_file in tile_files:
                # Create S3 key: city/layer/filename
                relative_path = tile_file.relative_to(local_base_dir)
                s3_key = f"{city_slug}/{relative_path}"
                
                future = executor.submit(self.upload_file, str(tile_file), s3_key)
                future_to_file[future] = tile_file
            
            # Process completed uploads
            for future in as_completed(future_to_file):
                tile_file = future_to_file[future]
                try:
                    result = future.result()
                    if result['success']:
                        uploaded_count += 1
                        total_size += result['size']
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    failed_count += 1
        
        # Summary
        success_rate = (uploaded_count / len(tile_files)) * 100
        total_size_mb = total_size / (1024 * 1024)
        
        return {
            'success': failed_count == 0,
            'uploaded': uploaded_count,
            'failed': failed_count,
            'total': len(tile_files),
            'success_rate': f"{success_rate:.1f}%",
            'total_size_mb': f"{total_size_mb:.1f}",
            'cloudfront_url': f"https://your-cloudfront-domain.cloudfront.net/{city_slug}/"
        }
    
    def upload_real_estate_tiles(self, data_type='combined', tile_format='png'):
        """Upload real estate tiles (plots/lands)"""
        
        if tile_format == 'png':
            if data_type == 'combined':
                local_dir = Path('static/real_estate_tiles_png/combined')
            else:
                local_dir = Path('static/real_estate_tiles_png') / data_type
            file_pattern = '*.png'
        else:  # mvt
            local_dir = Path('media/real_estate_tiles') / data_type
            file_pattern = '*.mvt'
        
        if not local_dir.exists():
            return {'success': False, 'error': f"Directory not found: {local_dir}"}
        
        tile_files = list(local_dir.rglob(file_pattern))
        
        if not tile_files:
            return {'success': False, 'error': f"No {tile_format} files found"}
        
        uploaded_count = 0
        failed_count = 0
        
        for tile_file in tile_files:
            # S3 key: real_estate/type/filename
            s3_key = f"real_estate/{data_type}/{tile_file.name}"
            
            result = self.upload_file(str(tile_file), s3_key)
            
            if result['success']:
                uploaded_count += 1
            else:
                failed_count += 1
        
        return {
            'success': failed_count == 0,
            'uploaded': uploaded_count,
            'failed': failed_count,
            'total': len(tile_files),
            's3_path': f"s3://{self.bucket_name}/real_estate/{data_type}/"
        }
    
    def test_connection(self):
        """Test S3 connection and bucket access"""
        try:
            # Try to list objects in bucket
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            
            return {
                'success': True,
                'bucket': self.bucket_name,
                'region': self.region,
                'object_count': response.get('KeyCount', 0)
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                return {'success': False, 'error': f"Bucket '{self.bucket_name}' does not exist"}
            elif error_code == 'AccessDenied':
                return {'success': False, 'error': "Access denied - check AWS credentials"}
            else:
                return {'success': False, 'error': f"AWS Error: {error_code}"}
                
        except NoCredentialsError:
            return {'success': False, 'error': "AWS credentials not found"}
        except Exception as e:
            return {'success': False, 'error': str(e)}