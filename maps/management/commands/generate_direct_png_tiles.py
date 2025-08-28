# maps/management/commands/generate_direct_png_tiles.py
"""
Management command to generate PNG tiles directly from GeoFeatures
Bypasses MVT encoding for cleaner tile generation
"""

import os
import json
import mercantile
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon
from django.db import connection
from PIL import Image, ImageDraw
import io
from typing import Dict, Tuple, Optional, List
import time

from maps.models import State, City, DataLayer, GeoFeature, CityLayerStyle, LayerCategory
from maps.config import get_city_style_config


class Command(BaseCommand):
    help = 'Generate PNG tiles directly from GeoFeatures without MVT intermediate step'
    
    def __init__(self):
        super().__init__()
        self.tile_size = 256
        self.tiles_generated = 0
        self.empty_tiles_skipped = 0
        self.errors = 0
        self.start_time = None
        
    def add_arguments(self, parser):
        parser.add_argument(
            '--state',
            type=str,
            required=True,
            help='State slug (e.g., karnataka, telangana)'
        )
        parser.add_argument(
            '--city',
            type=str,
            required=True,
            help='City slug (e.g., bengaluru, hyderabad)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='tiles_output',
            help='Output directory for tiles (default: tiles_output)'
        )
        parser.add_argument(
            '--min-zoom',
            type=int,
            default=8,
            help='Minimum zoom level (default: 8)'
        )
        parser.add_argument(
            '--max-zoom',
            type=int,
            default=18,
            help='Maximum zoom level (default: 18)'
        )
        parser.add_argument(
            '--layers',
            type=str,
            nargs='*',
            help='Specific layer slugs to generate (default: all layers)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing tiles'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress'
        )
    
    def handle(self, *args, **options):
        self.start_time = time.time()
        
        state_slug = options['state']
        city_slug = options['city']
        output_dir = Path(options['output_dir'])
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        layer_slugs = options.get('layers')
        force = options['force']
        verbose = options['verbose']
        
        # Header
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🗺️  DIRECT PNG TILE GENERATOR"))
        self.stdout.write("=" * 70)
        
        # Get state and city
        try:
            state = State.objects.get(slug=state_slug)
            city = City.objects.get(slug=city_slug, state_ref=state)
        except State.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ State '{state_slug}' not found"))
            return
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City '{city_slug}' not found in {state_slug}"))
            return
        
        self.stdout.write(f"📍 State: {state.name}")
        self.stdout.write(f"🏙️  City: {city.name}")
        self.stdout.write(f"📁 Output: {output_dir.absolute()}")
        self.stdout.write(f"🔍 Zoom levels: {min_zoom} to {max_zoom}")
        
        # Get layers to process
        layers = DataLayer.objects.filter(city=city)
        if layer_slugs:
            layers = layers.filter(slug__in=layer_slugs)
        
        if not layers.exists():
            self.stdout.write(self.style.ERROR(f"❌ No layers found for {city.name}"))
            return
        
        self.stdout.write(f"📊 Found {layers.count()} layers to process")
        self.stdout.write("-" * 70)
        
        # Get city style configuration
        style_config = self._get_city_style_config(city)
        
        # Process each layer
        for layer in layers:
            self.stdout.write(f"\n🎨 Processing layer: {layer.name} ({layer.slug})")
            
            # Check if layer has features
            feature_count = GeoFeature.objects.filter(layer=layer).count()
            if feature_count == 0:
                self.stdout.write(f"  ⚠️  No features in layer, skipping...")
                continue
            
            self.stdout.write(f"  📍 Features: {feature_count:,}")
            
            # Get layer bounds
            bounds = self._get_layer_bounds(layer)
            if not bounds:
                self.stdout.write(f"  ⚠️  Could not determine layer bounds, skipping...")
                continue
            
            self.stdout.write(f"  📐 Bounds: [{bounds['west']:.4f}, {bounds['south']:.4f}, "
                            f"{bounds['east']:.4f}, {bounds['north']:.4f}]")
            
            # Create output directory for this layer
            layer_output_dir = output_dir / state_slug / city_slug / layer.slug
            layer_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate tiles for each zoom level
            layer_tiles_count = 0
            layer_empty_count = 0
            
            for zoom in range(min_zoom, max_zoom + 1):
                zoom_start = time.time()
                
                # Get tiles that cover the layer bounds
                tiles = list(mercantile.tiles(
                    bounds['west'], bounds['south'],
                    bounds['east'], bounds['north'],
                    zoom
                ))
                
                if verbose:
                    self.stdout.write(f"\n  🔍 Zoom {zoom}: {len(tiles)} potential tiles")
                    if len(tiles) == 0:
                        self.stdout.write(f"    ⚠️  No tiles found for bounds: {bounds}")
                        continue
                
                zoom_generated = 0
                zoom_skipped = 0
                
                # Create zoom directory
                zoom_dir = layer_output_dir / str(zoom)
                zoom_dir.mkdir(exist_ok=True)
                
                # Process each tile
                for i, tile in enumerate(tiles):
                    if verbose:
                        self.stdout.write(f"    🔍 Processing tile {zoom}/{tile.x}/{tile.y}")
                    
                    # Create x directory
                    x_dir = zoom_dir / str(tile.x)
                    x_dir.mkdir(exist_ok=True)
                    
                    # Output file path
                    tile_path = x_dir / f"{tile.y}.png"
                    
                    # Skip if exists and not forcing
                    if tile_path.exists() and not force:
                        if verbose:
                            self.stdout.write(f"    ⏭️  Skipping existing tile {zoom}/{tile.x}/{tile.y}")
                        continue
                    
                    # Generate tile
                    tile_data = self._generate_tile(
                        layer, tile.x, tile.y, zoom, 
                        style_config, verbose
                    )
                    
                    if tile_data:
                        # Save tile
                        with open(tile_path, 'wb') as f:
                            f.write(tile_data)
                        zoom_generated += 1
                        layer_tiles_count += 1
                        self.tiles_generated += 1
                    else:
                        zoom_skipped += 1
                        layer_empty_count += 1
                        self.empty_tiles_skipped += 1
                    
                    # Progress indicator
                    if verbose and (i + 1) % 100 == 0:
                        self.stdout.write(f"    Processed {i + 1}/{len(tiles)} tiles...")
                
                zoom_time = time.time() - zoom_start
                
                if verbose or zoom_generated > 0:
                    self.stdout.write(
                        f"    ✅ Zoom {zoom}: {zoom_generated} tiles generated, "
                        f"{zoom_skipped} empty skipped ({zoom_time:.1f}s)"
                    )
            
            self.stdout.write(f"  📊 Layer complete: {layer_tiles_count} tiles, "
                            f"{layer_empty_count} empty skipped")
        
        # Summary
        elapsed_time = time.time() - self.start_time
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("🎉 TILE GENERATION COMPLETE!"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Total tiles created: {self.tiles_generated:,}")
        self.stdout.write(f"⏭️  Empty tiles skipped: {self.empty_tiles_skipped:,}")
        self.stdout.write(f"⏱️  Total time: {elapsed_time:.1f} seconds")
        self.stdout.write(f"📁 Output directory: {output_dir.absolute()}")
        
        # Create viewer HTML
        self._create_viewer_html(output_dir, city, layers.values_list('slug', flat=True))
    
    def _get_layer_bounds(self, layer) -> Optional[Dict]:
        """Get comprehensive bounds for all features in a layer"""
        try:
            # Use raw SQL for better performance (using correct table name)
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        ST_XMin(ST_Extent(geometry)) as min_x,
                        ST_YMin(ST_Extent(geometry)) as min_y,
                        ST_XMax(ST_Extent(geometry)) as max_x,
                        ST_YMax(ST_Extent(geometry)) as max_y
                    FROM geo_features
                    WHERE layer_id = %s
                """, [layer.id])
                
                row = cursor.fetchone()
                if row and all(v is not None for v in row):
                    return {
                        'west': float(row[0]),
                        'south': float(row[1]),
                        'east': float(row[2]),
                        'north': float(row[3])
                    }
            
            return None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting bounds: {e}"))
            return None
    
    def _generate_tile(self, layer, x: int, y: int, z: int, 
                       style_config: Dict, verbose: bool) -> Optional[bytes]:
        """Generate a single PNG tile using simplified approach"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, z)
            
            # Create bounding box for spatial query (simplified approach)
            buffer = 0.01  # Larger buffer to catch more features
            bbox = Polygon.from_bbox((
                tile_bounds.west - buffer,
                tile_bounds.south - buffer,
                tile_bounds.east + buffer,
                tile_bounds.north + buffer
            ))
            
            # Get features that intersect this tile
            features = layer.geofeature_set.filter(
                geometry__intersects=bbox
            ).only('geometry', 'properties')
            
            if verbose:
                total_features = layer.geofeature_set.count()
                self.stdout.write(f"    📊 Tile {z}/{x}/{y}: {features.count()}/{total_features} features intersect")
            
            if not features.exists():
                if verbose:
                    self.stdout.write(f"    ⚠️  No features intersect tile {z}/{x}/{y}")
                return None
            
            # Create image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            features_drawn = 0
            
            # Get layer-specific style
            layer_style = self._get_layer_style(layer, style_config)
            
            # Simplified drawing - focus on LineString and Polygon only
            for feature in features:
                geometry = feature.geometry
                if not geometry:
                    continue
                
                # Get color
                fill_color = self._get_feature_color(feature, layer_style)
                fill_rgb = self._hex_to_rgb(fill_color)
                
                # Draw based on geometry type (simplified)
                if geometry.geom_type == 'LineString':
                    if self._draw_simple_linestring(draw, geometry, tile_bounds, fill_rgb, z):
                        features_drawn += 1
                elif geometry.geom_type == 'Polygon':
                    if self._draw_simple_polygon(draw, geometry, tile_bounds, fill_rgb):
                        features_drawn += 1
                elif geometry.geom_type == 'MultiLineString':
                    for line in geometry:
                        if self._draw_simple_linestring(draw, line, tile_bounds, fill_rgb, z):
                            features_drawn += 1
                elif geometry.geom_type == 'MultiPolygon':
                    for poly in geometry:
                        if self._draw_simple_polygon(draw, poly, tile_bounds, fill_rgb):
                            features_drawn += 1
            
            if features_drawn == 0:
                return None
            
            # Convert to PNG bytes
            buffer = io.BytesIO()
            img.save(buffer, 'PNG', optimize=True)
            return buffer.getvalue()
            
        except Exception as e:
            if verbose:
                self.stdout.write(self.style.ERROR(f"    Error generating tile {z}/{x}/{y}: {e}"))
            self.errors += 1
            return None
    
    def _draw_feature(self, draw: ImageDraw, feature, tile_bounds, 
                     style: Dict, zoom: int) -> bool:
        """Draw a single feature on the tile"""
        try:
            geometry = feature.geometry
            if not geometry:
                return False
            
            # Get color based on feature properties
            fill_color = self._get_feature_color(feature, style)
            stroke_color = style.get('stroke_color', '#000000')
            
            # Convert hex to RGB
            fill_rgb = self._hex_to_rgb(fill_color)
            stroke_rgb = self._hex_to_rgb(stroke_color)
            
            # Draw based on geometry type
            geom_type = geometry.geom_type
            
            if geom_type == 'Polygon':
                return self._draw_polygon(draw, geometry, tile_bounds, fill_rgb, stroke_rgb)
            elif geom_type == 'MultiPolygon':
                drawn = False
                for poly in geometry:
                    if self._draw_polygon(draw, poly, tile_bounds, fill_rgb, stroke_rgb):
                        drawn = True
                return drawn
            elif geom_type == 'LineString':
                line_width = self._get_line_width(zoom)
                return self._draw_linestring(draw, geometry, tile_bounds, stroke_rgb, line_width)
            elif geom_type == 'MultiLineString':
                line_width = self._get_line_width(zoom)
                drawn = False
                for line in geometry:
                    if self._draw_linestring(draw, line, tile_bounds, stroke_rgb, line_width):
                        drawn = True
                return drawn
            elif geom_type == 'Point':
                return self._draw_point(draw, geometry, tile_bounds, fill_rgb, zoom)
            
            return False
            
        except Exception as e:
            return False
    
    def _draw_polygon(self, draw: ImageDraw, polygon, tile_bounds, 
                     fill_color: Tuple, stroke_color: Tuple) -> bool:
        """Draw a polygon without borders"""
        try:
            # Convert exterior ring to pixel coordinates
            pixel_coords = []
            for coord in polygon.exterior_ring.coords:
                px, py = self._latlon_to_pixel(coord[0], coord[1], tile_bounds)
                pixel_coords.append((px, py))
            
            if len(pixel_coords) >= 3:
                # Draw filled polygon without outline (no border)
                draw.polygon(pixel_coords, fill=fill_color + (255,))  # Full opacity, no outline
                return True
            
            return False
        except Exception:
            return False
    
    def _draw_linestring(self, draw: ImageDraw, linestring, tile_bounds, 
                        color: Tuple, width: int) -> bool:
        """Draw a linestring"""
        try:
            # Convert to pixel coordinates
            pixel_coords = []
            for coord in linestring.coords:
                px, py = self._latlon_to_pixel(coord[0], coord[1], tile_bounds)
                pixel_coords.append((px, py))
            
            # Draw line segments
            if len(pixel_coords) >= 2:
                for i in range(len(pixel_coords) - 1):
                    p1, p2 = pixel_coords[i], pixel_coords[i + 1]
                    # Check if segment is visible
                    margin = width + 10
                    if any(-margin <= coord <= self.tile_size + margin 
                          for coord in [p1[0], p1[1], p2[0], p2[1]]):
                        draw.line([p1, p2], fill=color, width=width)
                return True
            
            return False
        except Exception:
            return False
    
    def _draw_point(self, draw: ImageDraw, point, tile_bounds, 
                   color: Tuple, zoom: int) -> bool:
        """Draw a point"""
        try:
            px, py = self._latlon_to_pixel(point.x, point.y, tile_bounds)
            
            # Check if point is visible
            if 0 <= px <= self.tile_size and 0 <= py <= self.tile_size:
                radius = max(2, min(6, zoom - 8))  # Scale with zoom
                bbox = [px - radius, py - radius, px + radius, py + radius]
                draw.ellipse(bbox, fill=color, outline=color)
                return True
            
            return False
        except Exception:
            return False
    
    def _latlon_to_pixel(self, lon: float, lat: float, tile_bounds) -> Tuple[float, float]:
        """Convert lat/lon to pixel coordinates within tile"""
        x_pixel = ((lon - tile_bounds.west) / 
                  (tile_bounds.east - tile_bounds.west)) * self.tile_size
        y_pixel = ((tile_bounds.north - lat) / 
                  (tile_bounds.north - tile_bounds.south)) * self.tile_size
        return x_pixel, y_pixel
    
    def _get_line_width(self, zoom: int) -> int:
        """Get line width based on zoom level"""
        # Similar to the working script's zoom-dependent widths
        if zoom <= 8:
            return 1
        elif zoom <= 10:
            return 2
        elif zoom <= 12:
            return 3
        elif zoom <= 14:
            return 4
        elif zoom <= 16:
            return 5
        else:
            return 6
    
    def _get_city_style_config(self, city) -> Dict:
        """Get style configuration for the city"""
        # For Bengaluru, create comprehensive PLU color mapping
        if city.slug == 'bengaluru':
            return {
                'zone_colors': {
                    # Residential zones
                    'residential': {'color': '#FFE4B5'},
                    'residential plotted': {'color': '#FFE4B5'},
                    'residential apartment': {'color': '#FFDAB9'},
                    'residential villa': {'color': '#FFE4E1'},
                    
                    # Commercial zones
                    'commercial': {'color': '#FFB6C1'},
                    'commercial area': {'color': '#FFB6C1'},
                    'commercial zone': {'color': '#FF69B4'},
                    'shopping': {'color': '#FF1493'},
                    
                    # Industrial zones
                    'industrial': {'color': '#DDA0DD'},
                    'industrial area': {'color': '#DDA0DD'},
                    'it park': {'color': '#BA55D3'},
                    'tech park': {'color': '#9370DB'},
                    'software': {'color': '#8B7AB8'},
                    
                    # Public/Semi-public
                    'public': {'color': '#87CEEB'},
                    'semi-public': {'color': '#87CEEB'},
                    'public utility': {'color': '#4682B4'},
                    'civic amenity': {'color': '#5F9EA0'},
                    'government': {'color': '#6495ED'},
                    
                    # Parks and Green spaces
                    'park': {'color': '#90EE90'},
                    'parks and open space': {'color': '#90EE90'},
                    'open space': {'color': '#98FB98'},
                    'green belt': {'color': '#00FF00'},
                    'playground': {'color': '#7CFC00'},
                    
                    # Agricultural
                    'agricultural': {'color': '#F0E68C'},
                    'agriculture': {'color': '#F0E68C'},
                    'cultivation': {'color': '#DAA520'},
                    
                    # Transportation
                    'transport': {'color': '#D3D3D3'},
                    'transportation': {'color': '#D3D3D3'},
                    'road': {'color': '#C0C0C0'},
                    'highway': {'color': '#A9A9A9'},
                    'railway': {'color': '#696969'},
                    
                    # Water bodies
                    'water': {'color': '#ADD8E6'},
                    'water body': {'color': '#ADD8E6'},
                    'lake': {'color': '#4169E1'},
                    'tank': {'color': '#1E90FF'},
                    
                    # Mixed use
                    'mixed': {'color': '#F4A460'},
                    'mixed use': {'color': '#F4A460'},
                    'mixed residential': {'color': '#DEB887'},
                    
                    # Special zones
                    'defense': {'color': '#BC8F8F'},
                    'defense area': {'color': '#BC8F8F'},
                    'education': {'color': '#FFE4B5'},
                    'educational': {'color': '#FFE4B5'},
                    'institutional': {'color': '#87CEEB'},
                    'health': {'color': '#FFE4E1'},
                    'hospital': {'color': '#FFE4E1'},
                    
                    # Default
                    'unclassified': {'color': '#CCCCCC'},
                },
                'default': {'color': '#CCCCCC'}
            }
        
        # For Hyderabad (using source_layer_name for RRR and metro line colors)
        elif city.slug == 'hyderabad':
            return {
                'zone_colors': {
                    # Metro lines - EXACT COLORS from config
                    'green line': {'color': '#00933D'},  # JBS Parade Ground ↔ MG Bus Station
                    'blue line': {'color': '#2D6BA1'},   # Nagole ↔ Raidurg
                    'red line': {'color': '#E40D17'},    # Miyapur ↔ L.B. Nagar
                    'purple line': {'color': '#8C06ED'}, # Purple Line (Phase 2A): Nagole ↔ RGIA
                    'orange line': {'color': '#EF6908'}, # Future City Line (Phase 2B)
                    'metro green': {'color': '#00933D'},
                    'metro blue': {'color': '#2D6BA1'},
                    'metro red': {'color': '#E40D17'},
                    'metro purple': {'color': '#8C06ED'},
                    'metro orange': {'color': '#EF6908'},
                    
                    # RRR Roads and infrastructure (special bright green for RRR)
                    'rrr_final': {'color': '#14E098'},  # Bright green for RRR
                    'rrr': {'color': '#14E098'},
                    'regional ring road': {'color': '#14E098'},
                    'ring road': {'color': '#14E098'},
                    
                    # Other transportation infrastructure
                    'orr': {'color': '#FF6B35'},  # Orange for ORR
                    'outer ring road': {'color': '#FF6B35'},
                    'radial road': {'color': '#4ECDC4'},  # Teal for radial roads
                    'radial': {'color': '#4ECDC4'},
                    'highway': {'color': '#14E098'},  # Using same green as per config
                    'highways': {'color': '#14E098'},
                    'road': {'color': '#9E9E9E'},  # Light gray for regular roads
                    
                    # Land use zones (if any master plan data)
                    'residential': {'color': '#FFE4B5'},
                    'commercial': {'color': '#FFB6C1'},
                    'industrial': {'color': '#DDA0DD'},
                    'it corridor': {'color': '#9C27B0'},
                    'it park': {'color': '#BA55D3'},
                    'institutional': {'color': '#87CEEB'},
                    'public': {'color': '#87CEEB'},
                    'semi-public': {'color': '#87CEEB'},
                    
                    # Green and water
                    'park': {'color': '#90EE90'},
                    'green belt': {'color': '#00E676'},
                    'open space': {'color': '#98FB98'},
                    'water body': {'color': '#00BCD4'},
                    'lake': {'color': '#0288D1'},
                    
                    # Special zones
                    'airport': {'color': '#FFC107'},
                    'defense': {'color': '#795548'},
                    'cantonment': {'color': '#6D4C41'},
                    
                    # Future City
                    'fcda boundary': {'color': '#7D7D7D'},
                    'future city': {'color': '#7D7D7D'},
                    
                    # Mixed use
                    'mixed use': {'color': '#FF9800'},
                    'mixed': {'color': '#FF9800'},
                    
                    # Agricultural
                    'agricultural': {'color': '#CDDC39'},
                    'agriculture': {'color': '#CDDC39'},
                    
                    # Default
                    'unclassified': {'color': '#E0E0E0'},
                },
                'default': {'color': '#E0E0E0'}
            }
        
        # For Visakhapatnam
        elif city.slug == 'visakhapatnam':
            return {
                'zone_colors': {
                    # Agricultural and Green zones
                    'agricultural use zone': {'color': '#D3FFBE'},
                    'agricultural': {'color': '#D3FFBE'},
                    
                    # Water zones
                    'blue zone water bodies': {'color': '#73FFDF'},
                    'water bodies': {'color': '#73FFDF'},
                    'water body buffer': {'color': '#4CE600'},
                    
                    # Hills and terrain
                    'brown zone hills': {'color': '#A87000'},
                    'hills': {'color': '#A87000'},
                    
                    # Commercial zones
                    'commercial use zone': {'color': '#004DA8'},
                    'commercial': {'color': '#004DA8'},
                    'c1 - neighborhood business zone': {'color': '#EE82EE'},
                    'c2a - sub city commercial': {'color': '#FF73DF'},
                    'c2b - business zone': {'color': '#FFBEE8'},
                    'c3a - central business zone': {'color': '#A80084'},
                    'c3b - wholesale zone': {'color': '#E8BEFF'},
                    
                    # Existing facilities (with patterns in actual implementation)
                    'existing crematorium / burial ground / graveyard': {'color': '#FFFFFF'},
                    'existing educational facilities': {'color': '#FF0000'},
                    'existing government / semi government facilities': {'color': '#FF0000'},
                    'existing health facilities': {'color': '#FF0000'},
                    'existing public utilities': {'color': '#FF7F7F'},
                    'existing recreational / playgrounds / parks / open spaces': {'color': '#FFE600'},
                    
                    # Industrial zones
                    'proposed industrial use zone': {'color': '#C500FF'},
                    'existing industrial area': {'color': '#C500FF'},
                    'i1 - general industrial zone': {'color': '#AC8EC9'},
                    'i2 - heavy industrial zone': {'color': '#A064A9'},
                    'i3 - special industrial zone': {'color': '#894465'},
                    'industrial vacant': {'color': '#B0A5A6'},
                    'industrial': {'color': '#C500FF'},
                    
                    # Park and conservation zones
                    'park zone reserve': {'color': '#267300'},
                    'park zone reserve forest': {'color': '#38A800'},
                    'park zone reserve open space': {'color': '#4CE600'},
                    'conservation zone': {'color': '#4CE600'},
                    
                    # Proposed zones
                    'proposed commercial use zone': {'color': '#004DA8'},
                    'proposed recreational / playgrounds / parks / open spaces': {'color': '#98E600'},
                    'proposed religious use zone': {'color': '#FFFF00'},
                    'proposed residential use zone': {'color': '#FFC400'},
                    
                    # Port and special zones
                    'port area zone': {'color': '#E8BEFF'},
                    'special area use zone': {'color': '#FFFFFF'},
                    
                    # Residential zones (existing styles from config)
                    'r1 - low density zone': {'color': '#FFFFD9'},
                    'r2 - medium density zone': {'color': '#FED976'},
                    'r3 - medium to high density zone': {'color': '#F5CA7A'},
                    'r4 - high density zone': {'color': '#E69800'},
                    'raa': {'color': '#FFAA00'},
                    'residential vacant': {'color': '#FFD37F'},
                    'residential': {'color': '#FFC400'},
                    
                    # Public/Special zones
                    's1 - public zone': {'color': '#C7C700'},
                    's2 - education zone': {'color': '#FF7F7F'},
                    's3 - special zone': {'color': '#D7B09E'},
                    
                    # Mixed use zones
                    'sc1a - mixed use': {'color': '#0070FF'},
                    'sc1b - mixed use': {'color': '#73B2FF'},
                    
                    # Parks and protected
                    'sp1 - passive zone': {'color': '#267300'},
                    'sp2 - active zone': {'color': '#38A800'},
                    'sp3 - protected zone': {'color': '#00C5FF'},
                    
                    # Special residential
                    'sr2 - low density housing': {'color': '#FFFFBE'},
                    'sr4 - high density private': {'color': '#FFAA00'},
                    
                    # Government zones
                    'ss1 - government zone': {'color': '#E60000'},
                    'ss2a - education zone': {'color': '#FF7F7F'},
                    'ss2b - cultural zone': {'color': '#C500FF'},
                    'ss2c - health zone': {'color': '#D3FFBE'},
                    'ss3 - special zone': {'color': '#A83800'},
                    
                    # Utility zones
                    'su1 - reserve zone': {'color': '#E1E1E1'},
                    'su2 - road network': {'color': '#FFFFFF'},
                    'u1 - reserve zone': {'color': '#CCCCCC'},
                    'u2 - road reserve zone': {'color': '#000000'},
                    
                    # Tourism zones
                    'tourism zone': {'color': '#D7C29E'},
                    'tourism accommodation': {'color': '#D7C29E'},
                    
                    # General fallback categories
                    'park': {'color': '#267300'},
                    'mixed': {'color': '#0070FF'},
                    'public': {'color': '#C7C700'},
                },
                'default': {'color': '#CCCCCC'}
            }
        
        # For Amaravati
        elif city.slug == 'amaravati':
            return {
                'zone_colors': {
                    # Burial and special areas (patterns in actual implementation)
                    'burial ground': {'color': '#FFFFFF'},
                    
                    # Commercial zones
                    'c1 - mixed use zone': {'color': '#73B2FF'},
                    'c2 - general commercial zone': {'color': '#00C5FF'},
                    'c3 - neighbourhood centre zone': {'color': '#00C5FF'},
                    'c4 - town centre zone': {'color': '#00A9E6'},
                    'c5 - regional centre zone': {'color': '#0070FF'},
                    'c6 - central business district zone': {'color': '#005CE6'},
                    'commercial vacant': {'color': '#C5E2FF'},
                    
                    # Industrial zones  
                    'i1 - business park zone': {'color': '#FFBEE8'},
                    'i2 - logistics zone': {'color': '#FF73DF'},
                    'i3 - non polluting industry zone': {'color': '#A900E6'},
                    
                    # Park and protected zones
                    'p1 - passive zone': {'color': '#267300'},
                    'p2 - active zone': {'color': '#38A800'},
                    'p3 - protected zone': {'color': '#BEE8FF'},
                    'p3 - protected zone hills': {'color': '#4C7300'},
                    'pgn-g': {'color': '#4C7300'},
                    'pgn-v': {'color': '#897044'},
                    
                    # Residential zones (R1 has hatched pattern in actual implementation)
                    'r1 - village planning zone': {'color': '#FFFFFF'},
                    'r2 - low density zone': {'color': '#FFFFD9'},
                    'r3 - medium to high density zone': {'color': '#F5CA7A'},
                    'r4 - high density zone': {'color': '#E69800'},
                    'raa': {'color': '#FFAA00'},
                    'residential vacant': {'color': '#FFD37F'},
                    
                    # Special zones
                    's2 - education zone': {'color': '#FF7F7F'},
                    's3 - special zone': {'color': '#D7B09E'},
                    
                    # Mixed use zones
                    'sc1a - mixed use': {'color': '#0070FF'},
                    'sc1b - mixed use': {'color': '#73B2FF'},
                    
                    # Special park zones
                    'sp1 - passive zone': {'color': '#267300'},
                    'sp2 - active zone': {'color': '#38A800'},
                    'sp3 - protected zone': {'color': '#00C5FF'},
                    
                    # Special residential
                    'sr2 - low density housing': {'color': '#FFFFBE'},
                    'sr4 - high density private': {'color': '#FFAA00'},
                    
                    # Government zones
                    'ss1 - government zone': {'color': '#E60000'},
                    'ss2a - education zone': {'color': '#FF7F7F'},
                    'ss2b - cultural zone': {'color': '#C500FF'},
                    'ss2c - health zone': {'color': '#D3FFBE'},
                    'ss3 - special zone': {'color': '#A83800'},
                    
                    # Utility zones
                    'su1 - reserve zone': {'color': '#E1E1E1'},
                    'su2 - road network': {'color': '#FFFFFF'},
                    'u1 - reserve zone': {'color': '#CCCCCC'},
                    'u2 - road reserve zone': {'color': '#000000'},
                    
                    # From the original Amaravati config (additional zones)
                    'agriculture_land': {'color': '#00D900'},
                    'agricultural_land': {'color': '#00D900'},
                    'agriculture': {'color': '#00D900'},
                    'agricultural land': {'color': '#00D900'},
                    
                    'airport': {'color': '#C8821F'},
                    
                    'cbd_central_business_district': {'color': '#FF00C5'},
                    'cbd': {'color': '#FF00C5'},
                    'central business': {'color': '#FF00C5'},
                    'central business district': {'color': '#FF00C5'},
                    
                    'commercial': {'color': '#FF00C5'},
                    'commercial zone': {'color': '#FF00C5'},
                    'neighbourhood_commercial': {'color': '#FFBEE8'},
                    'neighbourhood commercial': {'color': '#FFBEE8'},
                    
                    'conservation_zone': {'color': '#00A800'},
                    'conservation': {'color': '#00A800'},
                    'conservation zone': {'color': '#00A800'},
                    
                    'education_zone_higher': {'color': '#E69800'},
                    'education_zone_school': {'color': '#FFFF00'},
                    'education': {'color': '#E69800'},
                    'education zone': {'color': '#E69800'},
                    'education zone higher': {'color': '#E69800'},
                    'education zone school': {'color': '#FFFF00'},
                    
                    'government_complex': {'color': '#729FCF'},
                    'government_zone': {'color': '#729FCF'},
                    'government': {'color': '#729FCF'},
                    'government complex': {'color': '#729FCF'},
                    'government zone': {'color': '#729FCF'},
                    
                    'green_zone': {'color': '#73DFFF'},
                    'green zone': {'color': '#73DFFF'},
                    'parks': {'color': '#73DFFF'},
                    'open_space': {'color': '#73DFFF'},
                    'open space': {'color': '#73DFFF'},
                    
                    'heritage_zone': {'color': '#895A44'},
                    'heritage': {'color': '#895A44'},
                    'heritage zone': {'color': '#895A44'},
                    
                    'industrial': {'color': '#C500FF'},
                    'industrial_zone': {'color': '#C500FF'},
                    'industrial zone': {'color': '#C500FF'},
                    'high_tech': {'color': '#8A2BE2'},
                    'high tech': {'color': '#8A2BE2'},
                    
                    'logistic_hub': {'color': '#AA00FF'},
                    'logistics': {'color': '#AA00FF'},
                    'logistic hub': {'color': '#AA00FF'},
                    
                    'mixed_use_zone_commercial': {'color': '#E4211A'},
                    'mixed_use_zone_residential': {'color': '#FFC11A'},
                    'mixed_use': {'color': '#FFC11A'},
                    'mixed': {'color': '#FFC11A'},
                    'mixed use': {'color': '#FFC11A'},
                    'mixed use zone commercial': {'color': '#E4211A'},
                    'mixed use zone residential': {'color': '#FFC11A'},
                    
                    'public_semi_public': {'color': '#AD7F29'},
                    'public_utilities': {'color': '#729FCF'},
                    'public': {'color': '#AD7F29'},
                    'semi-public': {'color': '#AD7F29'},
                    'public semi public': {'color': '#AD7F29'},
                    'public utilities': {'color': '#729FCF'},
                    
                    'recreational_zone': {'color': '#8DD3C7'},
                    'recreation': {'color': '#8DD3C7'},
                    'recreational zone': {'color': '#8DD3C7'},
                    
                    'residential_affordable_ligh': {'color': '#D2FFFF'},
                    'residential_township': {'color': '#F9FFA4'},
                    'residential_villa': {'color': '#73B2FF'},
                    'residential': {'color': '#F9FFA4'},
                    'residential affordable ligh': {'color': '#D2FFFF'},
                    'residential township': {'color': '#F9FFA4'},
                    'residential villa': {'color': '#73B2FF'},
                    
                    'water_bodies': {'color': '#00A6E4'},
                    'water': {'color': '#00A6E4'},
                    'water body': {'color': '#00A6E4'},
                    'water bodies': {'color': '#00A6E4'},
                    
                    'transport': {'color': '#CCCCCC'},
                    'road': {'color': '#CCCCCC'},
                    'roads': {'color': '#CCCCCC'},
                    
                    # Default
                    'unclassified': {'color': '#CCCCCC'},
                },
                'default': {'color': '#CCCCCC'},
                'supports_patterns': True  # Flag to indicate this city uses patterns
            }
        
        # For other cities, return generic config
        else:
            return {
                'zone_colors': {
                    'residential': {'color': '#FFE4B5'},
                    'commercial': {'color': '#FFB6C1'},
                    'industrial': {'color': '#DDA0DD'},
                    'institutional': {'color': '#87CEEB'},
                    'public': {'color': '#87CEEB'},
                    'transport': {'color': '#D3D3D3'},
                    'green': {'color': '#90EE90'},
                    'water': {'color': '#ADD8E6'},
                    'agricultural': {'color': '#F0E68C'},
                    'mixed': {'color': '#F4A460'},
                },
                'default': {'color': '#CCCCCC'}
            }
    
    def _get_layer_style(self, layer, city_style_config: Dict) -> Dict:
        """Get style for a specific layer"""
        # Try to get custom style from CityLayerStyle
        try:
            custom_style = CityLayerStyle.objects.get(
                city=layer.city,
                category=layer.category  # Changed from layer_category to category
            )
            return {
                'fill_color': custom_style.fill_color or '#CCCCCC',
                'stroke_color': custom_style.stroke_color or '#000000',
                'zone_colors': city_style_config.get('zone_colors', {})
            }
        except CityLayerStyle.DoesNotExist:
            pass
        
        # Fallback to category-based style
        category_name = layer.category.name.lower() if layer.category else 'default'
        category_style = city_style_config.get(category_name, city_style_config.get('default', {}))
        
        return {
            'fill_color': category_style.get('color', '#CCCCCC'),
            'stroke_color': '#000000',
            'zone_colors': city_style_config.get('zone_colors', {})
        }
    
    def _get_feature_color(self, feature, style: Dict) -> str:
        """Get color for a feature based on its properties and city-specific fields"""
        city_slug = feature.layer.city.slug
        
        # For Bengaluru, use PLU fields
        if city_slug == 'bengaluru':
            # Check PLU fields directly on the feature model
            zone_value = None
            
            # Priority order for Bengaluru
            if hasattr(feature, 'plu_secondary_1') and feature.plu_secondary_1:
                zone_value = feature.plu_secondary_1
            elif hasattr(feature, 'plu_proposed_use') and feature.plu_proposed_use:
                zone_value = feature.plu_proposed_use
            elif hasattr(feature, 'source_layer_name') and feature.source_layer_name:
                zone_value = feature.source_layer_name
            elif hasattr(feature, 'zone_category') and feature.zone_category:
                zone_value = feature.zone_category
            
            # Also check properties JSON for original PLU fields
            if not zone_value and hasattr(feature, 'properties') and feature.properties:
                props = feature.properties if isinstance(feature.properties, dict) else {}
                zone_value = (props.get('PLU_Tp_pro') or 
                            props.get('PLU_NAME') or 
                            props.get('PLU_prop_l') or
                            props.get('Zone_Categ'))
            
            # Map zone value to color using Bengaluru PLU mapping
            if zone_value and 'zone_colors' in style:
                zone_value_lower = str(zone_value).lower()
                
                # Check exact matches first
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() == zone_value_lower:
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
                
                # Check partial matches
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() in zone_value_lower or zone_value_lower in zone_key.lower():
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
        
        # For Hyderabad (mainly infrastructure layers like RRR and Metro)
        elif city_slug == 'hyderabad':
            zone_value = None
            
            # Special handling for metro lines - check properties for line color
            if hasattr(feature, 'properties') and feature.properties:
                props = feature.properties if isinstance(feature.properties, dict) else {}
                
                # Check for metro line color in properties
                if 'color_hex' in props and props['color_hex']:
                    # Direct color hex from properties (metro lines have this)
                    return props['color_hex']
                
                # Check for line color name
                if 'line_color' in props and props['line_color']:
                    line_color = props['line_color'].lower()
                    # Map to exact metro colors
                    metro_color_map = {
                        'green line': '#00933D',
                        'blue line': '#2D6BA1',
                        'red line': '#E40D17',
                        'purple line': '#8C06ED',
                        'orange line': '#EF6908'
                    }
                    if line_color in metro_color_map:
                        return metro_color_map[line_color]
                
                # Check linecolour field (alternative spelling)
                if 'linecolour' in props and props['linecolour']:
                    line_color = props['linecolour'].lower()
                    metro_color_map = {
                        'green line': '#00933D',
                        'blue line': '#2D6BA1',
                        'red line': '#E40D17',
                        'purple line': '#8C06ED',
                        'orange line': '#EF6908'
                    }
                    if line_color in metro_color_map:
                        return metro_color_map[line_color]
            
            # Check source_layer_name (for RRR and other infrastructure)
            if hasattr(feature, 'source_layer_name') and feature.source_layer_name:
                zone_value = feature.source_layer_name
            # Check the layer slug itself
            elif hasattr(feature, 'layer') and feature.layer:
                zone_value = feature.layer.slug
            # Check zone_category
            elif hasattr(feature, 'zone_category') and feature.zone_category:
                zone_value = feature.zone_category
            
            # Check properties JSON for other fields
            if not zone_value and hasattr(feature, 'properties') and feature.properties:
                props = feature.properties if isinstance(feature.properties, dict) else {}
                zone_value = (props.get('layer_name') or 
                            props.get('type') or 
                            props.get('road_type') or
                            props.get('Category'))
            
            # Map to color
            if zone_value and 'zone_colors' in style:
                zone_value_lower = str(zone_value).lower().strip()
                
                # Check exact matches
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() == zone_value_lower:
                        return zone_config.get('color', style.get('fill_color', '#E0E0E0'))
                
                # Check partial matches (important for RRR)
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() in zone_value_lower or zone_value_lower in zone_key.lower():
                        return zone_config.get('color', style.get('fill_color', '#E0E0E0'))
            
            # Special handling for RRR layer - always return bright green
            if hasattr(feature, 'layer') and feature.layer:
                if 'rrr' in feature.layer.slug.lower():
                    return '#14E098'
                # Special handling for highways
                elif 'highway' in feature.layer.slug.lower():
                    return '#14E098'  # Same green as per config
        
        # For Visakhapatnam
        elif city_slug == 'visakhapatnam':
            zone_value = None
            
            # Check zone_category first
            if hasattr(feature, 'zone_category') and feature.zone_category:
                zone_value = feature.zone_category
            
            # Check properties for Category field
            if not zone_value and hasattr(feature, 'properties') and feature.properties:
                props = feature.properties if isinstance(feature.properties, dict) else {}
                zone_value = props.get('Category') or props.get('Zone_Categ')
            
            # Map to color
            if zone_value and 'zone_colors' in style:
                zone_value_lower = str(zone_value).lower().strip()
                
                # Check exact matches
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() == zone_value_lower:
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
                
                # Check partial matches
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() in zone_value_lower or zone_value_lower in zone_key.lower():
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
        
        # For Amaravati
        elif city_slug == 'amaravati':
            zone_value = None
            
            # Check symbology field first (main field for Amaravati)
            if hasattr(feature, 'symbology') and feature.symbology:
                zone_value = feature.symbology
            elif hasattr(feature, 'plot_category') and feature.plot_category:
                zone_value = feature.plot_category
            elif hasattr(feature, 'source_layer_name') and feature.source_layer_name:
                zone_value = feature.source_layer_name
            elif hasattr(feature, 'zone_category') and feature.zone_category:
                zone_value = feature.zone_category
            
            # Check properties for additional fields
            if not zone_value and hasattr(feature, 'properties') and feature.properties:
                props = feature.properties if isinstance(feature.properties, dict) else {}
                zone_value = (props.get('symbology') or 
                            props.get('plot_categ') or 
                            props.get('Category'))
            
            # Map to color
            if zone_value and 'zone_colors' in style:
                # Clean up the zone value (remove underscores, normalize)
                zone_value_clean = str(zone_value).lower().strip().replace('_', ' ')
                
                # Check exact matches
                for zone_key, zone_config in style['zone_colors'].items():
                    zone_key_clean = zone_key.lower().replace('_', ' ')
                    if zone_key_clean == zone_value_clean:
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
                
                # Check partial matches
                for zone_key, zone_config in style['zone_colors'].items():
                    zone_key_clean = zone_key.lower().replace('_', ' ')
                    if zone_key_clean in zone_value_clean or zone_value_clean in zone_key_clean:
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
        
        # For other cities, use generic zone_category
        else:
            zone_value = None
            
            # Check direct fields
            if hasattr(feature, 'zone_category') and feature.zone_category:
                zone_value = feature.zone_category
            elif hasattr(feature, 'source_layer_name') and feature.source_layer_name:
                zone_value = feature.source_layer_name
                
            # Check properties JSON
            if not zone_value and hasattr(feature, 'properties') and feature.properties:
                props = feature.properties if isinstance(feature.properties, dict) else {}
                zone_keys = ['Category', 'zone_category', 'Zone_Categ', 'symbology', 
                           'plot_category', 'land_use', 'PLU_NAME']
                for key in zone_keys:
                    if key in props and props[key]:
                        zone_value = props[key]
                        break
            
            # Map to color
            if zone_value and 'zone_colors' in style:
                zone_value_lower = str(zone_value).lower()
                for zone_key, zone_config in style['zone_colors'].items():
                    if zone_key.lower() in zone_value_lower or zone_value_lower in zone_key.lower():
                        return zone_config.get('color', style.get('fill_color', '#CCCCCC'))
        
        # Default color fallback
        return style.get('fill_color', '#CCCCCC')
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _draw_simple_linestring(self, draw: ImageDraw, linestring, tile_bounds, 
                               color: Tuple, zoom: int) -> bool:
        """Draw a simple linestring (simplified version)"""
        try:
            # Convert to pixel coordinates
            pixel_coords = []
            for coord in linestring.coords:
                px, py = self._latlon_to_pixel(coord[0], coord[1], tile_bounds)
                pixel_coords.append((px, py))
            
            # Draw line segments
            if len(pixel_coords) >= 2:
                line_width = max(1, min(6, zoom - 8))  # Simple line width
                for i in range(len(pixel_coords) - 1):
                    p1, p2 = pixel_coords[i], pixel_coords[i + 1]
                    # Check if segment is visible
                    margin = line_width + 10
                    if any(-margin <= coord <= self.tile_size + margin 
                          for coord in [p1[0], p1[1], p2[0], p2[1]]):
                        draw.line([p1, p2], fill=color, width=line_width)
                        return True
            return False
        except Exception:
            return False
    
    def _draw_simple_polygon(self, draw: ImageDraw, polygon, tile_bounds, 
                            color: Tuple) -> bool:
        """Draw a simple polygon (simplified version)"""
        try:
            # Convert exterior ring to pixel coordinates
            pixel_coords = []
            for coord in polygon.exterior_ring.coords:
                px, py = self._latlon_to_pixel(coord[0], coord[1], tile_bounds)
                pixel_coords.append((px, py))
            
            if len(pixel_coords) >= 3:
                # Draw filled polygon
                draw.polygon(pixel_coords, fill=color + (255,))  # Full opacity
                return True
            return False
        except Exception:
            return False
    
    def _create_viewer_html(self, output_dir: Path, city, layer_slugs):
        """Create an HTML viewer for the generated tiles"""
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{city.name} - Tile Viewer</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: absolute; top: 10px; right: 10px;
            background: white; padding: 15px; border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000;
            max-width: 300px;
        }}
        .layer-control {{
            position: absolute; top: 10px; left: 60px;
            background: white; padding: 10px; border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>{city.name} Tiles</h3>
        <p><strong>State:</strong> {city.state_ref.name if city.state_ref else 'Unknown'}</p>
        <p><strong>Layers:</strong> {len(layer_slugs)}</p>
        <p><strong>Format:</strong> PNG (256x256)</p>
        <p><strong>Zoom:</strong> <span id="zoom-level">10</span></p>
        <small>Generated with Direct PNG Tile Generator</small>
    </div>
    
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script>
        // Initialize map
        var map = L.map('map').setView([{city.center_lat}, {city.center_lng}], 10);
        
        // Add OpenStreetMap base layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            opacity: 0.5
        }}).addTo(map);
        
        // Add generated tile layers
        var layers = {json.dumps(list(layer_slugs))};
        var layerGroup = L.layerGroup();
        
        layers.forEach(function(layerSlug) {{
            var tileLayer = L.tileLayer('{city.state_ref.slug if city.state_ref else "unknown"}/{city.slug}/' + layerSlug + '/{{z}}/{{x}}/{{y}}.png', {{
                attribution: 'Generated Tiles',
                maxZoom: 18,
                minZoom: 8,
                opacity: 0.8
            }});
            layerGroup.addLayer(tileLayer);
        }});
        
        layerGroup.addTo(map);
        
        // Update zoom level display
        map.on('zoomend', function() {{
            document.getElementById('zoom-level').textContent = map.getZoom();
        }});
        
        // Layer control
        L.control.layers({{
            "OSM": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png')
        }}, {{
            "Generated Tiles": layerGroup
        }}).addTo(map);
        
        console.log('Tile viewer loaded for {city.name}');
    </script>
</body>
</html>"""
        
        viewer_path = output_dir / "viewer.html"
        with open(viewer_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.stdout.write(f"\n📱 Created viewer: {viewer_path}")
        self.stdout.write(f"   Open in browser: file://{viewer_path.absolute()}")