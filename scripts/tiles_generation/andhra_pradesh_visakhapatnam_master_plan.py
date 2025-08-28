#!/usr/bin/env python3
"""
Visakhapatnam Master Plan PNG Tile Generator
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

class VisakhapatnamPNGTileGenerator:
    def __init__(self, data_dir: str = "data/andhra_pradesh/visakhapatnam/master_plan", 
                 output_dir: str = "visakhapatnam_master_plan_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Load all GeoJSON files
        self.gdfs = []
        self.load_all_geojson_files()
        
        # Calculate global bounds
        self.global_bounds = self.calculate_global_bounds()
        
        # Direct color mapping for Visakhapatnam zones
        self.zone_colors = {
            'Agricultural Use Zone': {'fill_color': '#D3FFBE', 'stroke_color': None, 'pattern': 'SOLID'},
            'Blue Zone Water Bodies': {'fill_color': '#73FFDF', 'stroke_color': None, 'pattern': 'SOLID'},
            'Brown Zone Hills': {'fill_color': '#A87000', 'stroke_color': None, 'pattern': 'SOLID'},
            'Commercial Use Zone': {'fill_color': '#004DA8', 'stroke_color': None, 'pattern': 'SOLID'},
            'Existing Crematorium': {'fill_color': '#FFFFFF', 'stroke_color': '#FF0000', 'pattern': 'HATCH'},
            'Existing Educational': {'fill_color': '#FF0000', 'stroke_color': '#000000', 'pattern': 'HATCH'},
            'Existing Government': {'fill_color': '#FF0000', 'stroke_color': None, 'pattern': 'SOLID'},
            'Existing Health': {'fill_color': '#FF0000', 'stroke_color': '#CCCCCC', 'pattern': 'DOT'},
            'Proposed Industrial': {'fill_color': '#C500FF', 'stroke_color': '#FFFFFF', 'pattern': 'HATCH'},
            'Existing Industrial': {'fill_color': '#C500FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'Existing Public Utilities': {'fill_color': '#FF7F7F', 'stroke_color': '#E60000', 'pattern': 'HATCH'},
            'Existing Recreational': {'fill_color': '#55FF00', 'stroke_color': None, 'pattern': 'SOLID'},
            'Existing Religious': {'fill_color': '#FF0000', 'stroke_color': '#55FF00', 'pattern': 'HATCH'},
            'Existing Road Railway': {'fill_color': None, 'stroke_color': '#828282', 'pattern': 'HATCH'},
            'Existing Transportation': {'fill_color': '#686868', 'stroke_color': None, 'pattern': 'SOLID'},
            'Green Zone Forest': {'fill_color': '#00734C', 'stroke_color': None, 'pattern': 'SOLID'},
            'Kambalakonda Eco': {'fill_color': '#D7C29E', 'stroke_color': None, 'pattern': 'SOLID'},
            'Kambalakonda Wildlife': {'fill_color': '#38A800', 'stroke_color': None, 'pattern': 'SOLID'},
            'Mixed Use Zone 1': {'fill_color': '#FFAA00', 'stroke_color': None, 'pattern': 'SOLID'},
            'Mixed Use Zone 2': {'fill_color': '#FFD37F', 'stroke_color': None, 'pattern': 'SOLID'},
            'Mixed Use Zone 3': {'fill_color': '#E69800', 'stroke_color': '#E1E1E1', 'pattern': 'HATCH'},
            'Mixed Use Zone 4': {'fill_color': '#FFAA00', 'stroke_color': '#000000', 'pattern': 'DOT'},
            'Proposed PSP': {'fill_color': None, 'stroke_color': '#FF0000', 'pattern': 'HATCH'},
            'Proposed Public Utilities': {'fill_color': '#F57A7A', 'stroke_color': '#FFFFFF', 'pattern': 'HATCH'},
            'Proposed Recreational': {'fill_color': '#4C7300', 'stroke_color': None, 'pattern': 'SOLID'},
            'Proposed Road Network': {'fill_color': '#C47362', 'stroke_color': None, 'pattern': 'SOLID'},
            'Proposed Transportation': {'fill_color': '#343434', 'stroke_color': '#FFFFFF', 'pattern': 'HATCH'},
            'Residential Use Zone': {'fill_color': '#FFFF73', 'stroke_color': None, 'pattern': 'SOLID'},
            'Sea River Accreted Land': {'fill_color': '#D7C29E', 'stroke_color': '#E39E00', 'pattern': 'DOT'},
            'Special Area Use Zone': {'fill_color': '#FFFFFF', 'stroke_color': '#002673', 'pattern': 'HATCH'},
            'Water Body Buffer': {'fill_color': '#4CE600', 'stroke_color': '#267300', 'pattern': 'DOT'}
        }
    
    def load_all_geojson_files(self):
        """Load all GeoJSON files from the data directory"""
        if not self.data_dir.exists():
            print(f"Data directory {self.data_dir} does not exist!")
            return
        
        for geojson_file in self.data_dir.glob("*.geojson"):
            try:
                print(f"Loading {geojson_file.name}...")
                gdf = gpd.read_file(geojson_file)
                
                # Add zone name and style name properties
                gdf['zone_name'] = geojson_file.stem
                gdf['style_name'] = self.map_filename_to_style_name(geojson_file.stem)
                
                self.gdfs.append(gdf)
                print(f"  Loaded {len(gdf)} features from {geojson_file.name}")
                
            except Exception as e:
                print(f"Error loading {geojson_file.name}: {e}")
    
    def map_filename_to_style_name(self, filename: str) -> str:
        """Map filename to style name"""
        # Clean up the filename to match the style names
        name_mapping = {
            'Agricultural_Use_Zone': 'Agricultural Use Zone',
            'Blue_Zone_Water_Bodies': 'Blue Zone Water Bodies',
            'Brown_Zone_Hills': 'Brown Zone Hills',
            'Commercial_Use_Zone': 'Commercial Use Zone',
            'Existing_Crematorium_Burial_Ground_Graveyard': 'Existing Crematorium',
            'Existing_Educational_Facilities': 'Existing Educational',
            'Existing_Government_Semi_Government_Facilities': 'Existing Government',
            'Existing_Health_Facilities': 'Existing Health',
            'Proposed_Industrial_Use_Zone': 'Proposed Industrial',
            'Existing_Industrial_Area': 'Existing Industrial',
            'Existing_Public_Utilities': 'Existing Public Utilities',
            'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace': 'Existing Recreational',
            'Existing_Religious_Facilities': 'Existing Religious',
            'Existing_Road_Railway_Line_Area': 'Existing Road Railway',
            'Existing_Transportation_Facility': 'Existing Transportation',
            'Green_Zone_Forest': 'Green Zone Forest',
            'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park': 'Kambalakonda Eco',
            'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area': 'Kambalakonda Wildlife',
            'Mixed_Use_Zone_1': 'Mixed Use Zone 1',
            'Mixed_Use_Zone_2_BAIA': 'Mixed Use Zone 2',
            'Mixed_Use_Zone_3_BAIA': 'Mixed Use Zone 3',
            'Mixed_Use_Zone_4_BAIA': 'Mixed Use Zone 4',
            'Proposed_PSP_Use_Zone': 'Proposed PSP',
            'Proposed_Public_Utilities_Use_Zone': 'Proposed Public Utilities',
            'Proposed_Recreational_Use_Zone': 'Proposed Recreational',
            'Proposed_Road_Network': 'Proposed Road Network',
            'Proposed_Transportation_Facility_Use_Zone': 'Proposed Transportation',
            'Residential_Use_Zone': 'Residential Use Zone',
            'Sea_River_Accreted_Land': 'Sea River Accreted Land',
            'Special_Area_Use_Zone': 'Special Area Use Zone',
            'Water_Body_Buffer': 'Water Body Buffer'
        }
        
        return name_mapping.get(filename, filename)
    
    def get_zone_style(self, zone_name: str) -> Dict:
        """Get style configuration for a zone"""
        return self.zone_colors.get(zone_name, {
            'fill_color': '#CCCCCC',
            'stroke_color': None,
            'pattern': 'SOLID',
            'stroke_width': 0
        })
    
    def calculate_global_bounds(self) -> Tuple[float, float, float, float]:
        """Calculate global bounds from all loaded GeoJSON files"""
        if not self.gdfs:
            return (0, 0, 0, 0)
        
        bounds_list = []
        for gdf in self.gdfs:
            bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)
            bounds_list.append(bounds)
        
        if not bounds_list:
            return (0, 0, 0, 0)
        
        minx = min(bounds[0] for bounds in bounds_list)
        miny = min(bounds[1] for bounds in bounds_list)
        maxx = max(bounds[2] for bounds in bounds_list)
        maxy = max(bounds[3] for bounds in bounds_list)
        
        return (minx, miny, maxx, maxy)
    
    def web_mercator_to_pixels(self, lng: float, lat: float, zoom: int, tile_x: int, tile_y: int) -> Tuple[int, int]:
        """Convert WGS84 coordinates to pixel coordinates within a tile"""
        # Convert to Web Mercator
        x = lng * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) * 20037508.34 / math.pi
        
        # Get tile bounds in Web Mercator
        tile_bounds = mercantile.bounds(tile_x, tile_y, zoom)
        tile_bounds_mercator = mercantile.bounds(tile_x, tile_y, zoom)
        
        # Convert tile bounds to Web Mercator
        west_mercator = tile_bounds_mercator.west * 20037508.34 / 180
        east_mercator = tile_bounds_mercator.east * 20037508.34 / 180
        north_mercator = math.log(math.tan((90 + tile_bounds_mercator.north) * math.pi / 360)) * 20037508.34 / math.pi
        south_mercator = math.log(math.tan((90 + tile_bounds_mercator.south) * math.pi / 360)) * 20037508.34 / math.pi
        
        # Convert to pixels
        pixel_x = int(256 * (x - west_mercator) / (east_mercator - west_mercator))
        pixel_y = int(256 * (north_mercator - y) / (north_mercator - south_mercator))
        
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
    
    def draw_dot_pattern(self, draw: ImageDraw, pixel_coords: List[Tuple], 
                        dot_color: Tuple, spacing: int = 6):
        """Draw a dot pattern clipped to polygon boundaries"""
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
        
        # Create a temporary image for dots
        dot_img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        dot_draw = ImageDraw.Draw(dot_img)
        
        # Draw dots in a grid pattern
        for x in range(min_x, max_x, spacing):
            for y in range(min_y, max_y, spacing):
                if 0 <= x <= 255 and 0 <= y <= 255:
                    dot_draw.ellipse([x-1, y-1, x+1, y+1], fill=dot_color)
        
        # Apply polygon mask
        dot_img.putalpha(mask)
        
        # Composite onto main image
        img = draw._image
        img.paste(dot_img, (0, 0), dot_img)
    
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
                    draw.polygon(pixel_coords, fill=fill_color)
                elif fill_color and pattern == 'HATCH' and stroke_color:
                    draw.polygon(pixel_coords, fill=fill_color)
                    self.draw_hatch_pattern(draw, pixel_coords, stroke_color)
                elif fill_color and pattern == 'DOT' and stroke_color:
                    draw.polygon(pixel_coords, fill=fill_color)
                    self.draw_dot_pattern(draw, pixel_coords, stroke_color)
                elif pattern == 'HATCH' and stroke_color:
                    self.draw_hatch_pattern(draw, pixel_coords, stroke_color)
                elif pattern == 'DOT' and stroke_color:
                    self.draw_dot_pattern(draw, pixel_coords, stroke_color)
                
                # No stroke drawing - only fill and patterns
                
                return True
                
        except Exception as e:
            print(f"Error drawing polygon: {e}")
            return False
        
        return False
    
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
    
    def generate_png_tiles(self, min_zoom: int = 8, max_zoom: int = 16):
        """Generate PNG tiles for all zoom levels"""
        print(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}...")
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"Generating tiles for zoom level {zoom}...")
            
            # Calculate tile range for this zoom level
            min_tile = mercantile.tile(self.global_bounds[0], self.global_bounds[1], zoom)
            max_tile = mercantile.tile(self.global_bounds[2], self.global_bounds[3], zoom)
            
            zoom_tiles = 0
            
            for x in range(min_tile.x, max_tile.x + 1):
                for y in range(max_tile.y, min_tile.y + 1):
                    # Create tile directory
                    tile_dir = self.output_dir / str(zoom) / str(x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Generate tile
                    tile_path = tile_dir / f"{y}.png"
                    
                    if not tile_path.exists():  # Skip if tile already exists
                        try:
                            tile_img = self.generate_tile(x, y, zoom)
                            tile_img.save(tile_path, 'PNG')
                            zoom_tiles += 1
                        except Exception as e:
                            print(f"Error generating tile {zoom}/{x}/{y}: {e}")
            
            print(f"  Generated {zoom_tiles} tiles for zoom level {zoom}")
            total_tiles += zoom_tiles
        
        print(f"Total tiles generated: {total_tiles}")
    
    def create_mapbox_style_json(self):
        """Create Mapbox style JSON file"""
        style = {
            "version": 8,
            "name": "Visakhapatnam Master Plan",
            "sources": {
                "visakhapatnam-master-plan": {
                    "type": "raster",
                    "tiles": ["http://localhost:8000/api/visakhapatnam-tiles/{z}/{x}/{y}.png"],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "visakhapatnam-master-plan-layer",
                    "type": "raster",
                    "source": "visakhapatnam-master-plan",
                    "minzoom": 8,
                    "maxzoom": 16
                }
            ]
        }
        
        style_path = self.output_dir / "visakhapatnam_master_plan_style.json"
        with open(style_path, 'w') as f:
            json.dump(style, f, indent=2)
        
        print(f"Created Mapbox style JSON: {style_path}")
    
    def create_tilejson(self):
        """Create TileJSON file"""
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Visakhapatnam Master Plan",
            "description": "Visakhapatnam Master Plan - Land Use Categories",
            "version": "1.0.0",
            "attribution": "Visakhapatnam Development Authority",
            "template": "http://localhost:8000/api/visakhapatnam-tiles/{z}/{x}/{y}.png",
            "legend": "http://localhost:8000/api/visakhapatnam-tiles/legend",
            "scheme": "xyz",
            "tiles": ["http://localhost:8000/api/visakhapatnam-tiles/{z}/{x}/{y}.png"],
            "grids": [],
            "data": [],
            "minzoom": 8,
            "maxzoom": 16,
            "bounds": list(self.global_bounds),
            "center": [
                (self.global_bounds[0] + self.global_bounds[2]) / 2,
                (self.global_bounds[1] + self.global_bounds[3]) / 2,
                12
            ]
        }
        
        tilejson_path = self.output_dir / "visakhapatnam_master_plan_tilejson.json"
        with open(tilejson_path, 'w') as f:
            json.dump(tilejson, f, indent=2)
        
        print(f"Created TileJSON: {tilejson_path}")
    
    def create_mapbox_viewer(self):
        """Create HTML viewer for the tiles"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Visakhapatnam Master Plan Viewer</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
    <div id='map'></div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        
        const map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "name": "Visakhapatnam Master Plan",
                "sources": {{
                    "visakhapatnam-master-plan": {{
                        "type": "raster",
                        "tiles": ["http://localhost:8000/api/visakhapatnam-tiles/{{z}}/{{x}}/{{y}}.png"],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "visakhapatnam-master-plan-layer",
                        "type": "raster",
                        "source": "visakhapatnam-master-plan",
                        "minzoom": 8,
                        "maxzoom": 16
                    }}
                ]
            }},
            center: [{(self.global_bounds[0] + self.global_bounds[2]) / 2}, {(self.global_bounds[1] + self.global_bounds[3]) / 2}],
            zoom: 12
        }});
    </script>
</body>
</html>
"""
        
        viewer_path = self.output_dir / "visakhapatnam_master_plan_viewer.html"
        with open(viewer_path, 'w') as f:
            f.write(html_content)
        
        print(f"Created HTML viewer: {viewer_path}")

def main():
    """Main function"""
    print("Visakhapatnam Master Plan PNG Tile Generator")
    print("=" * 50)
    
    # Initialize generator
    generator = VisakhapatnamPNGTileGenerator()
    
    if not generator.gdfs:
        print("No GeoJSON files loaded. Exiting.")
        return
    
    print(f"Loaded {len(generator.gdfs)} GeoJSON files")
    print(f"Global bounds: {generator.global_bounds}")
    
    # Generate tiles
    generator.generate_png_tiles(min_zoom=17, max_zoom=18)
    
    # Create supporting files
    generator.create_mapbox_style_json()
    generator.create_tilejson()
    generator.create_mapbox_viewer()
    
    print("\nTile generation complete!")
    print(f"Tiles saved to: {generator.output_dir}")
    print(f"View the map at: {generator.output_dir}/visakhapatnam_master_plan_viewer.html")

if __name__ == "__main__":
    main()
