#!/usr/bin/env python3
"""
Warangal Master Plan PNG Tile Generator
Generates Mapbox-compatible PNG tiles from GeoJSON files
"""

import os
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import geopandas as gpd
import mercantile
from PIL import Image, ImageDraw
import numpy as np

class WarangalPNGTileGenerator:
    def __init__(self, data_dir: str = "data/Telangana/warangal/master_plan", 
                 output_dir: str = "warangal_master_plan_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Load all GeoJSON files
        self.gdfs = []
        self.load_all_geojson_files()
        
        # Calculate global bounds
        self.calculate_global_bounds()
        
        # Direct color mapping for Warangal zones
        self.zone_colors = {
            'Agriculture': {'fill_color': '#D3FFBE', 'stroke_color': None, 'pattern': 'SOLID'},
            'AirStrip': {'fill_color': '#FFFFFF', 'stroke_color': '#FF00C5', 'pattern': 'HATCH'},
            'Commercial': {'fill_color': '#0070FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'Forest': {'fill_color': '#267300', 'stroke_color': None, 'pattern': 'SOLID'},
            'GrowthCorridor': {'fill_color': '#FFBEE8', 'stroke_color': None, 'pattern': 'SOLID'},
            'GrowthCorridor2': {'fill_color': '#FF73DF', 'stroke_color': None, 'pattern': 'SOLID'},
            'Heritage': {'fill_color': '#FFA77F', 'stroke_color': '#732600', 'pattern': 'HATCH'},
            'HillBuffer': {'fill_color': '#55FF00', 'stroke_color': None, 'pattern': 'SOLID'},
            'Hillocks': {'fill_color': '#A87000', 'stroke_color': None, 'pattern': 'SOLID'},
            'Industrial': {'fill_color': '#C500FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'MixedUse': {'fill_color': '#FFAA00', 'stroke_color': None, 'pattern': 'SOLID'},
            'Public_and_SemiPublic': {'fill_color': '#FF0000', 'stroke_color': None, 'pattern': 'SOLID'},
            'PublicUtilities': {'fill_color': '#E69800', 'stroke_color': '#FF0000', 'pattern': 'HATCH'},
            'RailwayLand': {'fill_color': '#CCCCCC', 'stroke_color': None, 'pattern': 'SOLID'},
            'Recreational': {'fill_color': '#55FF00', 'stroke_color': None, 'pattern': 'SOLID'},
            'Residential': {'fill_color': '#FFFF00', 'stroke_color': None, 'pattern': 'SOLID'},
            'ResidentialExpansion': {'fill_color': '#9C9C9C', 'stroke_color': None, 'pattern': 'SOLID'},
            'RoadBuffer': {'fill_color': '#4E4E4E', 'stroke_color': None, 'pattern': 'SOLID'},
            'Transportation': {'fill_color': '#B2B2B2', 'stroke_color': None, 'pattern': 'SOLID'},
            'Water_Bodies': {'fill_color': '#00C5FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'WaterBodyBuffer': {'fill_color': '#55FF00', 'stroke_color': None, 'pattern': 'SOLID'},
            'ZoologicalPark': {'fill_color': '#38A800', 'stroke_color': None, 'pattern': 'SOLID'}
        }
    
    def load_all_geojson_files(self):
        """Load all GeoJSON files from the data directory"""
        print("Loading GeoJSON files...")
        
        for geojson_file in self.data_dir.glob("*.geojson"):
            print(f"Loading {geojson_file.name}...")
            try:
                gdf = gpd.read_file(geojson_file)
                
                # Add zone name and style name properties
                zone_name = geojson_file.stem
                gdf['zone_name'] = zone_name
                gdf['style_name'] = zone_name
                
                print(f"  Loaded {len(gdf)} features from {geojson_file.name}")
                self.gdfs.append(gdf)
                
            except Exception as e:
                print(f"  Error loading {geojson_file.name}: {e}")
        
        print(f"Loaded {len(self.gdfs)} GeoJSON files")
    
    def calculate_global_bounds(self):
        """Calculate global bounds from all loaded data"""
        if not self.gdfs:
            print("No data loaded!")
            return
        
        all_bounds = []
        for gdf in self.gdfs:
            bounds = gdf.total_bounds
            all_bounds.append(bounds)
        
        # Calculate global bounds
        min_x = min(bounds[0] for bounds in all_bounds)
        min_y = min(bounds[1] for bounds in all_bounds)
        max_x = max(bounds[2] for bounds in all_bounds)
        max_y = max(bounds[3] for bounds in all_bounds)
        
        self.global_bounds = (min_x, min_y, max_x, max_y)
        print(f"Global bounds: {self.global_bounds}")
    
    def web_mercator_to_pixels(self, lng: float, lat: float, zoom: int, tile_x: int, tile_y: int) -> Tuple[int, int]:
        """Convert WGS84 coordinates to pixel coordinates within a tile"""
        # Convert to tile coordinates
        tile_bounds = mercantile.bounds(tile_x, tile_y, zoom)
        
        # Convert to Web Mercator
        west_mercator = tile_bounds.west * 20037508.34 / 180
        east_mercator = tile_bounds.east * 20037508.34 / 180
        north_mercator = math.log(math.tan((90 + tile_bounds.north) * math.pi / 360)) * 20037508.34 / math.pi
        south_mercator = math.log(math.tan((90 + tile_bounds.south) * math.pi / 360)) * 20037508.34 / math.pi
        
        # Convert to pixels
        pixel_x = int(256 * (lng * 20037508.34 / 180 - west_mercator) / (east_mercator - west_mercator))
        pixel_y = int(256 * (north_mercator - math.log(math.tan((90 + lat) * math.pi / 360)) * 20037508.34 / math.pi) / (north_mercator - south_mercator))
        
        return pixel_x, pixel_y
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        if not hex_color or hex_color == 'None':
            return (0, 0, 0)
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def draw_hatch_pattern(self, draw: ImageDraw, pixel_coords: List[Tuple], 
                          hatch_color: Tuple, spacing: int = 8):
        """Draw a diagonal hatch pattern clipped to polygon boundaries"""
        if not pixel_coords or len(pixel_coords) < 3:
            return
        
        # Get bounding box
        min_x = min(coord[0] for coord in pixel_coords)
        max_x = max(coord[0] for coord in pixel_coords)
        min_y = min(coord[1] for coord in pixel_coords)
        max_y = max(coord[1] for coord in pixel_coords)
        
        # Create a mask for the polygon
        mask = Image.new('L', (256, 256), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(pixel_coords, fill=255)
        
        # Draw diagonal lines with proper clipping
        for i in range(min_x - (max_y - min_y), max_x + (max_y - min_y), spacing):
            # Calculate line endpoints
            start_x = i
            start_y = min_y
            end_x = i + (max_y - min_y)
            end_y = max_y
            
            # Clip to tile bounds
            if start_x < 0:
                start_y = min_y + (0 - start_x)
                start_x = 0
            if end_x > 255:
                end_y = max_y - (end_x - 255)
                end_x = 255
            if start_y < 0:
                start_x = i + (0 - start_y)
                start_y = 0
            if end_y > 255:
                end_x = i + (255 - end_y)
                end_y = 255
            
            # Only draw if line is within bounds
            if (0 <= start_x <= 255 and 0 <= start_y <= 255 and 
                0 <= end_x <= 255 and 0 <= end_y <= 255):
                
                # Create a temporary image for this line
                line_img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                line_draw = ImageDraw.Draw(line_img)
                line_draw.line([(start_x, start_y), (end_x, end_y)], fill=hatch_color, width=1)
                
                # Apply polygon mask
                line_img.putalpha(mask)
                
                # Composite onto main image
                img = draw._image
                img.paste(line_img, (0, 0), line_img)
    
    def draw_polygon(self, draw: ImageDraw, polygon, zoom: int, tile_x: int, tile_y: int,
                     fill_color: Tuple, stroke_color: Tuple = None, 
                     stroke_width: int = 0, pattern: str = 'SOLID') -> bool:
        """Draw a polygon on the tile"""
        try:
            # Handle MultiPolygon
            if hasattr(polygon, 'geoms'):
                # MultiPolygon
                for poly in polygon.geoms:
                    self.draw_polygon(draw, poly, zoom, tile_x, tile_y, 
                                    fill_color, stroke_color, stroke_width, pattern)
                return True
            
            # Single Polygon
            if hasattr(polygon, 'exterior'):
                # Get coordinates
                coords = list(polygon.exterior.coords)
                pixel_coords = []
                
                for lng, lat in coords:
                    pixel_x, pixel_y = self.web_mercator_to_pixels(lng, lat, zoom, tile_x, tile_y)
                    pixel_coords.append((pixel_x, pixel_y))
                
                if len(pixel_coords) < 3:
                    return False
                
                # Draw fill
                if fill_color and pattern == 'SOLID':
                    draw.polygon(pixel_coords, fill=fill_color, outline=None)
                elif fill_color and pattern == 'HATCH' and stroke_color:
                    draw.polygon(pixel_coords, fill=fill_color, outline=None)
                    self.draw_hatch_pattern(draw, pixel_coords, stroke_color)
                elif pattern == 'HATCH' and stroke_color:
                    self.draw_hatch_pattern(draw, pixel_coords, stroke_color)
                
                # No stroke drawing - only fill and patterns
                
                return True
                
        except Exception as e:
            print(f"Error drawing polygon: {e}")
            return False
        
        return False
    
    def get_zone_style(self, zone_name: str) -> Dict:
        """Get style configuration for a zone"""
        return self.zone_colors.get(zone_name, {
            'fill_color': '#CCCCCC',
            'stroke_color': None,
            'pattern': 'SOLID'
        })
    
    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile"""
        # Create a new image with transparent background
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Get tile bounds
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        # Filter features that intersect with this tile
        for gdf in self.gdfs:
            # Simple spatial filter - check if any feature intersects with tile bounds
            gdf_filtered = gdf[
                (gdf.bounds.minx <= tile_bounds.east) &
                (gdf.bounds.maxx >= tile_bounds.west) &
                (gdf.bounds.miny <= tile_bounds.north) &
                (gdf.bounds.maxy >= tile_bounds.south)
            ]
            
            for idx, row in gdf_filtered.iterrows():
                geometry = row.geometry
                style_name = row.get('style_name', 'Unknown')
                
                # Get style configuration
                style = self.get_zone_style(style_name)
                fill_color = self.hex_to_rgb(style.get('fill_color')) if style.get('fill_color') else None
                stroke_color = self.hex_to_rgb(style.get('stroke_color')) if style.get('stroke_color') else None
                pattern = style.get('pattern', 'SOLID')
                stroke_width = style.get('stroke_width', 0)
                
                # Draw the geometry
                self.draw_polygon(draw, geometry, zoom, x, y, 
                                fill_color, stroke_color, stroke_width, pattern)
        
        return img
    
    def generate_png_tiles(self, min_zoom: int = 3, max_zoom: int = 18):
        """Generate PNG tiles for all zoom levels"""
        print(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}...")
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"Generating tiles for zoom level {zoom}...")
            
            # Calculate tile range for this zoom level
            min_tile = mercantile.tile(self.global_bounds[0], self.global_bounds[1], zoom)
            max_tile = mercantile.tile(self.global_bounds[2], self.global_bounds[3], zoom)
            
            zoom_tiles = 0
            
            # Generate tiles for this zoom level
            for x in range(min_tile.x, max_tile.x + 1):
                for y in range(max_tile.y, min_tile.y + 1):
                    # Create tile directory
                    tile_dir = self.output_dir / str(zoom) / str(x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Generate tile
                    tile_img = self.generate_tile(x, y, zoom)
                    
                    # Save tile
                    tile_path = tile_dir / f"{y}.png"
                    tile_img.save(tile_path, "PNG")
                    zoom_tiles += 1
            
            print(f"  Generated {zoom_tiles} tiles for zoom level {zoom}")
            total_tiles += zoom_tiles
        
        print(f"Total tiles generated: {total_tiles}")
    
    def create_mapbox_style_json(self):
        """Create Mapbox style JSON file"""
        style = {
            "version": 8,
            "name": "Warangal Master Plan",
            "sources": {
                "warangal-master-plan": {
                    "type": "raster",
                    "tiles": ["tiles/{z}/{x}/{y}.png"],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "warangal-master-plan-layer",
                    "type": "raster",
                    "source": "warangal-master-plan",
                    "minzoom": 3,
                    "maxzoom": 18
                }
            ]
        }
        
        style_path = self.output_dir / "warangal_master_plan_style.json"
        with open(style_path, 'w') as f:
            json.dump(style, f, indent=2)
        
        print(f"Created Mapbox style JSON: {style_path}")
    
    def create_tilejson(self):
        """Create TileJSON file"""
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Warangal Master Plan",
            "description": "Warangal Master Plan - Land Use Categories",
            "version": "1.0.0",
            "attribution": "Warangal Master Plan",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": ["tiles/{z}/{x}/{y}.png"],
            "grids": [],
            "data": [],
            "minzoom": 3,
            "maxzoom": 18,
            "bounds": list(self.global_bounds),
            "center": [
                (self.global_bounds[0] + self.global_bounds[2]) / 2,
                (self.global_bounds[1] + self.global_bounds[3]) / 2,
                12
            ]
        }
        
        tilejson_path = self.output_dir / "warangal_master_plan_tilejson.json"
        with open(tilejson_path, 'w') as f:
            json.dump(tilejson, f, indent=2)
        
        print(f"Created TileJSON: {tilejson_path}")
    
    def create_mapbox_viewer(self):
        """Create HTML viewer for the tiles"""
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Warangal Master Plan</title>
    <meta charset="utf-8">
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw';
        
        const map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "name": "Warangal Master Plan",
                "sources": {{
                    "warangal-master-plan": {{
                        "type": "raster",
                        "tiles": ["tiles/{{z}}/{{x}}/{{y}}.png"],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "warangal-master-plan-layer",
                        "type": "raster",
                        "source": "warangal-master-plan",
                        "minzoom": 3,
                        "maxzoom": 18
                    }}
                ]
            }},
            center: [{(self.global_bounds[0] + self.global_bounds[2]) / 2}, {(self.global_bounds[1] + self.global_bounds[3]) / 2}],
            zoom: 12
        }});
        
        map.addControl(new mapboxgl.NavigationControl());
    </script>
</body>
</html>"""
        
        viewer_path = self.output_dir / "warangal_master_plan_viewer.html"
        with open(viewer_path, 'w') as f:
            f.write(html_content)
        
        print(f"Created HTML viewer: {viewer_path}")

def main():
    """Main function"""
    print("Warangal Master Plan PNG Tile Generator")
    print("=" * 50)
    
    # Initialize generator
    generator = WarangalPNGTileGenerator()
    
    # Generate tiles
    generator.generate_png_tiles(min_zoom=3, max_zoom=18)
    
    # Create supporting files
    generator.create_mapbox_style_json()
    generator.create_tilejson()
    generator.create_mapbox_viewer()
    
    print("\nTile generation complete!")
    print(f"Tiles saved to: {generator.output_dir}")
    print(f"View the map at: {generator.output_dir}/warangal_master_plan_viewer.html")

if __name__ == "__main__":
    main()
