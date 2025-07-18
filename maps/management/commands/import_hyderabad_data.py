from django.core.management.base import BaseCommand
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from django.utils.text import slugify
from maps.models import City, State, LayerGroup, DataLayer, GeoFeature, LayerCategory
import json
import os

class Command(BaseCommand):
    help = 'Import Hyderabad GIS data'

    def list_data_files(self):
        """List available data files"""
        self.stdout.write("Checking data files...")
        for root, dirs, files in os.walk('data'):
            for file in files:
                if file.endswith(('.geojson', '.shp')):
                    self.stdout.write(f"Found: {os.path.join(root, file)}")

    def handle(self, *args, **options):
        # First, list available data files
        self.list_data_files()

        # Ensure Telangana state exists
        state, _ = State.objects.get_or_create(
            name='Telangana',
            defaults={
                'code': 'TS',
                'slug': 'telangana',
                'is_active': True
            }
        )

        # Create or get Hyderabad city
        city, _ = City.objects.get_or_create(
            name='Hyderabad',
            defaults={
                'slug': 'hyderabad',
                'state_ref': state,
                'center_lat': 17.385044,
                'center_lng': 78.486671,
                'is_active': True
            }
        )

        # Get or create layer categories with unique codes
        transport_category = LayerCategory.objects.filter(name='Transport').first()
        if not transport_category:
            transport_category = LayerCategory.objects.create(
                name='Transport',
                code='HYD_TRANSPORT'
            )
        
        boundaries_category = LayerCategory.objects.filter(name='Boundaries').first()
        if not boundaries_category:
            boundaries_category = LayerCategory.objects.create(
                name='Boundaries',
                code='HYD_BOUNDARIES'
            )
        
        economic_category = LayerCategory.objects.filter(name='Economic').first()
        if not economic_category:
            economic_category = LayerCategory.objects.create(
                name='Economic',
                code='HYD_ECONOMIC'
            )

        # Create layer groups with categories and slugs
        transport_group, _ = LayerGroup.objects.get_or_create(
            name='Transport',
            city=city,
            category=transport_category,
            defaults={
                'slug': 'hyderabad-transport'
            }
        )

        boundaries_group, _ = LayerGroup.objects.get_or_create(
            name='Boundaries',
            city=city,
            category=boundaries_category,
            defaults={
                'slug': 'hyderabad-boundaries'
            }
        )

        economic_group, _ = LayerGroup.objects.get_or_create(
            name='Economic Zones',
            city=city,
            category=economic_category,
            defaults={
                'slug': 'hyderabad-economic-zones'
            }
        )

        # Let me check the DataLayer model fields
        self.stdout.write("DataLayer fields:", DataLayer._meta.get_fields())

        # Import data based on available files
        if os.path.exists('data/FutureCityHyderabad_Boundary/FutureCityHyderabad_Boundary.shp'):
            self.import_shapefile(
                'data/FutureCityHyderabad_Boundary/FutureCityHyderabad_Boundary.shp',
                'Future City Boundary',
                boundaries_group
            )

    def import_geojson(self, file_path, layer_name, layer_group):
        if not os.path.exists(file_path):
            self.stdout.write(f'File not found: {file_path}')
            return

        with open(file_path) as f:
            data = json.load(f)

        layer = DataLayer.objects.create(
            name=layer_name,
            group=layer_group,
            is_active=True
        )

        for feature in data['features']:
            geom = GEOSGeometry(json.dumps(feature['geometry']))
            properties = feature.get('properties', {})
            
            GeoFeature.objects.create(
                layer=layer,
                geometry=geom,
                properties=properties
            )

        self.stdout.write(f'Imported {layer_name}')

    def import_shapefile(self, file_path, layer_name, layer_group):
        if not os.path.exists(file_path):
            self.stdout.write(f'File not found: {file_path}')
            return

        ds = DataSource(file_path)
        layer = ds[0]

        # Create DataLayer with correct fields
        data_layer = DataLayer.objects.create(
            city=city,
            category=boundaries_category,
            name=layer_name,
            slug=slugify(layer_name),
            original_filename=os.path.basename(file_path),
            file_format='SHP',
            file_path=file_path,
            layer_group=layer_group
        )

        for feature in layer:
            geom = feature.geom.geos
            properties = {field: feature.get(field) for field in layer.fields}
            
            GeoFeature.objects.create(
                layer=data_layer,
                geometry=geom,
                properties=properties
            )

        self.stdout.write(f'Imported {layer_name}') 