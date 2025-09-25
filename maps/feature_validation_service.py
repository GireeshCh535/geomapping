# maps/feature_validation_service.py
# Service for validating features and tracking rendering issues

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from django.db import models
from django.contrib.gis.geos import GEOSGeometry
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

class FeatureValidationService:
    """
    Service to validate GEOJSON features and track rendering issues.
    Ensures all features are properly processed and provides detailed error reports.
    """
    
    def __init__(self):
        self.validation_errors = []
        self.validation_warnings = []
        self.feature_stats = defaultdict(int)
        self.missing_data_report = []
    
    def validate_geojson_data(self, geojson_data: Dict, city_slug: str) -> Tuple[bool, Dict]:
        """
        Validate GEOJSON data and return validation results.
        
        Returns:
            Tuple of (is_valid, validation_report)
        """
        self.reset_validation()
        
        # Check basic structure
        if not self._validate_structure(geojson_data):
            return False, self._generate_report()
        
        # Process features
        features = geojson_data.get('features', [])
        total_features = len(features)
        valid_features = 0
        
        for idx, feature in enumerate(features):
            if self._validate_feature(feature, idx, city_slug):
                valid_features += 1
        
        # Generate statistics
        self.feature_stats['total_features'] = total_features
        self.feature_stats['valid_features'] = valid_features
        self.feature_stats['invalid_features'] = total_features - valid_features
        
        is_valid = len(self.validation_errors) == 0
        return is_valid, self._generate_report()
    
    def _validate_structure(self, geojson_data: Dict) -> bool:
        """Validate basic GEOJSON structure"""
        if not isinstance(geojson_data, dict):
            self.validation_errors.append("Data is not a dictionary")
            return False
        
        if geojson_data.get('type') != 'FeatureCollection':
            self.validation_errors.append(f"Invalid type: {geojson_data.get('type')}")
            return False
        
        if 'features' not in geojson_data:
            self.validation_errors.append("Missing 'features' array")
            return False
        
        if not isinstance(geojson_data['features'], list):
            self.validation_errors.append("'features' is not an array")
            return False
        
        return True
    
    def _validate_feature(self, feature: Dict, idx: int, city_slug: str) -> bool:
        """Validate individual feature"""
        is_valid = True
        
        # Check feature type
        if feature.get('type') != 'Feature':
            self.validation_errors.append(f"Feature {idx}: Invalid type '{feature.get('type')}'")
            is_valid = False
        
        # Validate geometry
        geometry = feature.get('geometry')
        if not geometry:
            self.validation_errors.append(f"Feature {idx}: Missing geometry")
            is_valid = False
        else:
            geom_validation = self._validate_geometry(geometry, idx)
            if not geom_validation:
                is_valid = False
        
        # Validate properties based on city
        properties = feature.get('properties', {})
        prop_validation = self._validate_properties(properties, idx, city_slug)
        if not prop_validation:
            is_valid = False
        
        return is_valid
    
    def _validate_geometry(self, geometry: Dict, feature_idx: int) -> bool:
        """Validate geometry object"""
        if not isinstance(geometry, dict):
            self.validation_errors.append(f"Feature {feature_idx}: Geometry is not a dictionary")
            return False
        
        geom_type = geometry.get('type')
        if not geom_type:
            self.validation_errors.append(f"Feature {feature_idx}: Missing geometry type")
            return False
        
        valid_types = ['Point', 'LineString', 'Polygon', 'MultiPoint', 
                      'MultiLineString', 'MultiPolygon']
        if geom_type not in valid_types:
            self.validation_errors.append(f"Feature {feature_idx}: Invalid geometry type '{geom_type}'")
            return False
        
        coordinates = geometry.get('coordinates')
        if not coordinates:
            self.validation_errors.append(f"Feature {feature_idx}: Missing coordinates")
            return False
        
        # Validate coordinate structure based on type
        if geom_type == 'Polygon':
            if not self._validate_polygon_coords(coordinates, feature_idx):
                return False
        elif geom_type == 'MultiPolygon':
            for poly_idx, polygon in enumerate(coordinates):
                if not self._validate_polygon_coords(polygon, feature_idx, poly_idx):
                    return False
        
        # Try to create GEOS geometry to validate
        try:
            geom_json = json.dumps(geometry)
            geos_geom = GEOSGeometry(geom_json)
            
            # Check validity
            if not geos_geom.valid:
                self.validation_warnings.append(
                    f"Feature {feature_idx}: Geometry is not topologically valid - {geos_geom.valid_reason}"
                )
                
                # Try to fix
                try:
                    fixed_geom = geos_geom.buffer(0)
                    if fixed_geom.valid:
                        self.validation_warnings.append(
                            f"Feature {feature_idx}: Geometry can be fixed with buffer(0)"
                        )
                except:
                    pass
        except Exception as e:
            self.validation_errors.append(f"Feature {feature_idx}: Cannot create geometry - {str(e)}")
            return False
        
        return True
    
    def _validate_polygon_coords(self, coords: List, feature_idx: int, 
                                 poly_idx: Optional[int] = None) -> bool:
        """Validate polygon coordinates"""
        poly_ref = f"Feature {feature_idx}" + (f", Polygon {poly_idx}" if poly_idx is not None else "")
        
        if not coords or len(coords) == 0:
            self.validation_errors.append(f"{poly_ref}: Empty polygon coordinates")
            return False
        
        # Check exterior ring
        exterior = coords[0]
        if len(exterior) < 4:
            self.validation_errors.append(f"{poly_ref}: Exterior ring has less than 4 points")
            return False
        
        # Check if first and last points are the same (closed ring)
        if exterior[0] != exterior[-1]:
            self.validation_warnings.append(f"{poly_ref}: Ring is not closed")
        
        return True
    
    def _validate_properties(self, properties: Dict, feature_idx: int, city_slug: str) -> bool:
        """Validate properties based on city requirements"""
        required_fields = self._get_required_fields(city_slug)
        missing_fields = []
        
        for field in required_fields:
            if field not in properties or properties[field] in [None, '', ' ']:
                missing_fields.append(field)
        
        if missing_fields:
            self.missing_data_report.append({
                'feature_idx': feature_idx,
                'missing_fields': missing_fields,
                'available_fields': list(properties.keys())
            })
            self.validation_warnings.append(
                f"Feature {feature_idx}: Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Track zone/category information
        zone_field = self._get_zone_field(city_slug)
        if zone_field and zone_field in properties:
            zone_value = properties[zone_field]
            self.feature_stats[f'zone_{zone_value}'] = self.feature_stats.get(f'zone_{zone_value}', 0) + 1
        
        return True
    
    def _get_required_fields(self, city_slug: str) -> List[str]:
        """Get required fields for each city"""
        required_by_city = {
            'warangal': ['PLU', 'PLU_NAME'],
            'visakhapatnam': ['Category'],
            'amaravati': ['symbology', 'plot_categ'],
            'bengaluru': ['PLU']
        }
        return required_by_city.get(city_slug, [])
    
    def _get_zone_field(self, city_slug: str) -> str:
        """Get the main zone/category field for each city"""
        zone_fields = {
            'warangal': 'PLU_NAME',
            'visakhapatnam': 'Category',
            'amaravati': 'symbology',
            'bengaluru': 'PLU'
        }
        return zone_fields.get(city_slug)
    
    def reset_validation(self):
        """Reset validation state"""
        self.validation_errors = []
        self.validation_warnings = []
        self.feature_stats = defaultdict(int)
        self.missing_data_report = []
    
    def _generate_report(self) -> Dict:
        """Generate comprehensive validation report"""
        return {
            'timestamp': datetime.now().isoformat(),
            'is_valid': len(self.validation_errors) == 0,
            'statistics': dict(self.feature_stats),
            'errors': self.validation_errors,
            'warnings': self.validation_warnings,
            'missing_data': self.missing_data_report,
            'summary': {
                'total_errors': len(self.validation_errors),
                'total_warnings': len(self.validation_warnings),
                'features_with_missing_data': len(self.missing_data_report)
            }
        }
    
    def validate_tile_generation(self, layer, generated_tiles: int, 
                                expected_tiles: int) -> Dict:
        """Validate tile generation results"""
        validation = {
            'layer': layer.name,
            'city': layer.city.name,
            'generated_tiles': generated_tiles,
            'expected_tiles': expected_tiles,
            'success_rate': (generated_tiles / expected_tiles * 100) if expected_tiles > 0 else 0,
            'status': 'SUCCESS' if generated_tiles == expected_tiles else 'PARTIAL',
            'missing_tiles': expected_tiles - generated_tiles
        }
        
        if validation['success_rate'] < 95:
            validation['status'] = 'FAILED'
            validation['recommendation'] = 'Review geometry validation and retry tile generation'
        
        return validation
    
    def generate_html_report(self, validation_results: List[Dict]) -> str:
        """Generate HTML report for validation results"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Feature Validation Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .success { color: green; }
                .warning { color: orange; }
                .error { color: red; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .stats { background-color: #f9f9f9; padding: 10px; margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1>Feature Validation Report</h1>
        """
        
        for result in validation_results:
            status_class = 'success' if result['is_valid'] else 'error'
            html += f"""
            <h2 class="{status_class}">Validation: {'PASSED' if result['is_valid'] else 'FAILED'}</h2>
            <div class="stats">
                <h3>Statistics</h3>
                <ul>
            """
            
            for key, value in result['statistics'].items():
                html += f"<li><strong>{key}:</strong> {value}</li>"
            
            html += """
                </ul>
            </div>
            """
            
            if result['errors']:
                html += """
                <div class="error">
                    <h3>Errors</h3>
                    <ul>
                """
                for error in result['errors']:
                    html += f"<li>{error}</li>"
                html += """
                    </ul>
                </div>
                """
            
            if result['warnings']:
                html += """
                <div class="warning">
                    <h3>Warnings</h3>
                    <ul>
                """
                for warning in result['warnings']:
                    html += f"<li>{warning}</li>"
                html += """
                    </ul>
                </div>
                """
            
            if result['missing_data']:
                html += """
                <h3>Missing Data Report</h3>
                <table>
                    <tr>
                        <th>Feature Index</th>
                        <th>Missing Fields</th>
                        <th>Available Fields</th>
                    </tr>
                """
                for item in result['missing_data'][:20]:  # Show first 20
                    html += f"""
                    <tr>
                        <td>{item['feature_idx']}</td>
                        <td>{', '.join(item['missing_fields'])}</td>
                        <td>{', '.join(item['available_fields'][:5])}</td>
                    </tr>
                    """
                html += "</table>"
                
                if len(result['missing_data']) > 20:
                    html += f"<p>... and {len(result['missing_data']) - 20} more features with missing data</p>"
        
        html += """
        </body>
        </html>
        """
        
        return html


# Validation model to store results
class ValidationLog(models.Model):
    """Store validation results for tracking and auditing"""
    
    city = models.ForeignKey('City', on_delete=models.CASCADE, related_name='validation_logs')
    layer = models.ForeignKey('DataLayer', on_delete=models.CASCADE, null=True, blank=True)
    
    validation_type = models.CharField(max_length=50)  # 'geojson', 'tile_generation', etc.
    is_valid = models.BooleanField()
    
    # Statistics
    total_features = models.IntegerField(default=0)
    valid_features = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    
    # Detailed results (JSON)
    validation_report = models.JSONField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'validation_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'validation_type']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.validation_type} - {'Valid' if self.is_valid else 'Invalid'}"