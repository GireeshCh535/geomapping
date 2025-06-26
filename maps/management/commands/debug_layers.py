#!/usr/bin/env python
"""
Debug management command to check layer status and test tile generation
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from maps.models import City, DataLayer, GeoFeature
from maps.services import VectorTileService
import requests

class Command(BaseCommand):
    help = 'Debug layers and test tile generation'

    def add_arguments(self, parser):
        parser.add_argument('--city', type=str, help='City slug to debug')
        parser.add_argument('--layer', type=str, help='Layer slug to debug')
        parser.add_argument('--test-tiles', action='store_true', help='Test tile generation')
        parser.add_argument('--check-data', action='store_true', help='Check data integrity')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🐛 Starting Debug Analysis'))
        
        if options['city']:
            self.debug_city(options['city'])
        elif options['check_data']:
            self.check_all_data()
        else:
            self.debug_overview()
        
        if options['test_tiles']:
            self.test_tile_generation(options.get('city'), options.get('layer'))

    def debug_overview(self):
        """Debug overview of all cities and layers"""
        self.stdout.write('\n📊 SYSTEM OVERVIEW')
        self.stdout.write('=' * 50)
        
        cities = City.objects.all()
        for city in cities:
            layers = DataLayer.objects.filter(city=city)
            features = GeoFeature.objects.filter(layer__city=city)
            
            self.stdout.write(f'\n🏙️  City: {city.name} ({city.slug})')
            self.stdout.write(f'   State: {city.state}')
            self.stdout.write(f'   Active: {city.is_active}')
            self.stdout.write(f'   Layers: {layers.count()}')
            self.stdout.write(f'   Features: {features.count()}')
            
            # Layer breakdown
            processed_layers = layers.filter(is_processed=True)
            layers_with_tiles = layers.filter(tiles_generated=True)
            
            self.stdout.write(f'   Processed Layers: {processed_layers.count()}/{layers.count()}')
            self.stdout.write(f'   Layers with Tiles: {layers_with_tiles.count()}/{layers.count()}')
            
            if processed_layers.count() == 0:
                self.stdout.write(self.style.WARNING('   ⚠️  No processed layers found!'))

    def debug_city(self, city_slug):
        """Debug specific city"""
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ City not found: {city_slug}'))
            return
        
        self.stdout.write(f'\n🏙️  DEBUGGING CITY: {city.name}')
        self.stdout.write('=' * 50)
        
        layers = DataLayer.objects.filter(city=city)
        
        self.stdout.write(f'City Info:')
        self.stdout.write(f'  Name: {city.name}')
        self.stdout.write(f'  Slug: {city.slug}')
        self.stdout.write(f'  State: {city.state}')
        self.stdout.write(f'  Center: [{city.center_lat}, {city.center_lng}]')
        self.stdout.write(f'  Active: {city.is_active}')
        
        self.stdout.write(f'\nLayers ({layers.count()}):')
        
        for layer in layers:
            features = GeoFeature.objects.filter(layer=layer)
            
            status_icon = '✅' if layer.is_processed else '⚠️'
            tiles_icon = '🗺️' if layer.tiles_generated else '❌'
            
            self.stdout.write(f'  {status_icon} {tiles_icon} {layer.name}')
            self.stdout.write(f'     Slug: {layer.slug}')
            self.stdout.write(f'     Category: {layer.category.name} ({layer.category.code})')
            self.stdout.write(f'     Features: {features.count()}/{layer.feature_count}')
            self.stdout.write(f'     Format: {layer.file_format}')
            self.stdout.write(f'     Processed: {layer.is_processed}')
            self.stdout.write(f'     Tiles: {layer.tiles_generated}')
            
            if layer.processing_errors:
                self.stdout.write(self.style.WARNING(f'     Errors: {layer.processing_errors[:100]}...'))
            
            # Check for features
            if features.count() == 0 and layer.is_processed:
                self.stdout.write(self.style.WARNING('     ⚠️  No features found for processed layer!'))
            
            # Sample feature check
            if features.exists():
                sample_feature = features.first()
                self.stdout.write(f'     Sample Feature: {sample_feature.get_display_name()}')
                self.stdout.write(f'     Sample Geometry: {sample_feature.geometry.geom_type}')
                if hasattr(sample_feature, 'plu_primary_code') and sample_feature.plu_primary_code:
                    self.stdout.write(f'     Sample PLU: {sample_feature.plu_primary_code}')

    def test_tile_generation(self, city_slug=None, layer_slug=None):
        """Test tile generation"""
        self.stdout.write('\n🗺️  TESTING TILE GENERATION')
        self.stdout.write('=' * 50)
        
        if city_slug and layer_slug:
            try:
                layer = DataLayer.objects.get(city__slug=city_slug, slug=layer_slug)
                self.test_layer_tiles(layer)
            except DataLayer.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Layer not found: {city_slug}/{layer_slug}'))
        else:
            # Test a few sample layers
            test_cases = [
                ('bangalore', 'power_water_garbagefacility_treatmentplant'),
                ('bangalore', 'defense'),
                ('bangalore', 'drains'),
            ]
            
            for city_slug, layer_slug in test_cases:
                try:
                    layer = DataLayer.objects.get(city__slug=city_slug, slug=layer_slug)
                    self.test_layer_tiles(layer)
                except DataLayer.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'⚠️  Layer not found: {city_slug}/{layer_slug}'))

    def test_layer_tiles(self, layer):
        """Test tile generation for a specific layer"""
        self.stdout.write(f'\n🧪 Testing tiles for: {layer.city.slug}/{layer.slug}')
        
        # Test coordinates for Bangalore area
        test_coords = [
            (10, 500, 500),
            (11, 1000, 1000),
            (12, 2000, 2000),
        ]
        
        tile_service = VectorTileService()
        
        for z, x, y in test_coords:
            try:
                # Test MVT generation
                mvt_data = tile_service.generate_tile(layer, z, x, y)
                
                if mvt_data:
                    self.stdout.write(f'  ✅ MVT tile {z}/{x}/{y}: {len(mvt_data)} bytes')
                else:
                    self.stdout.write(f'  ⚠️  MVT tile {z}/{x}/{y}: No data')
                
                # Test via HTTP (if server is running)
                self.test_tile_http(layer.city.slug, layer.slug, z, x, y)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ MVT tile {z}/{x}/{y}: {str(e)}'))

    def test_tile_http(self, city_slug, layer_slug, z, x, y):
        """Test tile via HTTP request"""
        try:
            # Test both PNG and MVT endpoints
            urls = [
                f'http://localhost:8000/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.png',
                f'http://localhost:8000/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt',
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', 'unknown')
                        size = len(response.content)
                        self.stdout.write(f'  ✅ HTTP {url.split(".")[-1].upper()}: {response.status_code}, {size} bytes, {content_type}')
                    else:
                        self.stdout.write(f'  ❌ HTTP {url.split(".")[-1].upper()}: {response.status_code}')
                except requests.exceptions.RequestException as e:
                    self.stdout.write(f'  ⚠️  HTTP {url.split(".")[-1].upper()}: Connection failed ({str(e)[:50]})')
                    
        except Exception as e:
            self.stdout.write(f'  ❌ HTTP test failed: {str(e)}')

    def check_all_data(self):
        """Check data integrity across all cities"""
        self.stdout.write('\n🔍 DATA INTEGRITY CHECK')
        self.stdout.write('=' * 50)
        
        # Check for common issues
        issues = []
        
        # 1. Layers without features
        empty_layers = DataLayer.objects.filter(is_processed=True, feature_count=0)
        if empty_layers.exists():
            issues.append(f'❌ {empty_layers.count()} processed layers have no features')
            for layer in empty_layers[:5]:  # Show first 5
                issues.append(f'   - {layer.city.slug}/{layer.slug}')
        
        # 2. Features without valid geometry
        invalid_features = GeoFeature.objects.filter(is_valid=False)
        if invalid_features.exists():
            issues.append(f'❌ {invalid_features.count()} features have invalid geometry')
        
        # 3. Layers without bounding boxes
        layers_no_bbox = DataLayer.objects.filter(
            is_processed=True, 
            bbox_xmin__isnull=True
        )
        if layers_no_bbox.exists():
            issues.append(f'❌ {layers_no_bbox.count()} layers missing bounding boxes')
        
        # 4. Check PLU data (Bangalore specific)
        bangalore_features = GeoFeature.objects.filter(layer__city__slug='bangalore')
        plu_features = bangalore_features.exclude(plu_primary_code='')
        if bangalore_features.exists():
            plu_percentage = (plu_features.count() / bangalore_features.count()) * 100
            if plu_percentage < 50:
                issues.append(f'⚠️  Only {plu_percentage:.1f}% of Bangalore features have PLU codes')
        
        if issues:
            self.stdout.write('Issues found:')
            for issue in issues:
                self.stdout.write(f'  {issue}')
        else:
            self.stdout.write('✅ No major data integrity issues found!')
        
        # Summary statistics
        self.stdout.write('\n📊 SUMMARY STATISTICS')
        self.stdout.write(f'Cities: {City.objects.count()}')
        self.stdout.write(f'Total Layers: {DataLayer.objects.count()}')
        self.stdout.write(f'Processed Layers: {DataLayer.objects.filter(is_processed=True).count()}')
        self.stdout.write(f'Layers with Tiles: {DataLayer.objects.filter(tiles_generated=True).count()}')
        self.stdout.write(f'Total Features: {GeoFeature.objects.count()}')
        self.stdout.write(f'Valid Features: {GeoFeature.objects.filter(is_valid=True).count()}')