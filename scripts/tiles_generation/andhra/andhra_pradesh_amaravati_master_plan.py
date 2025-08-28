#!/usr/bin/env python3
"""
Amaravati Master Plan PNG Tile Generator
========================================

Generates PNG raster tiles for Amaravati Capital City Master Plan with:
- Multiple zone types (Residential, Commercial, Industrial, etc.)
- Colors from config file
- Zoom-dependent styling
- Standard XYZ tile format for Mapbox
- No empty tiles generated
- Transparent background

Requirements:
- pip install geopandas pillow mapbox-vector-tile
"""

import json
import os
import math
import geopandas as gpd
from pathlib import Path
from PIL import Image, ImageDraw
from typing import Tuple, List, Dict
import mercantile
import sys

# Add Django settings (optional, for future use)
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
# import django
# django.setup()

class AmaravatiMasterPlanTileGenerator:
    def __init__(self, master_plan_dir: str, output_dir: str = "amaravati_master_plan_tiles"):
        """
        Initialize the Amaravati Master Plan PNG tile generator
        
        Args:
            master_plan_dir: Path to the master_plan directory
            output_dir: Directory to save generated tiles
        """
        self.master_plan_dir = Path(master_plan_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256  # Standard Mapbox tile size
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Load all GeoJSON files
        self.load_all_geojson_files()
        
        print(f"🏛️  Amaravati Master Plan PNG Tile Generator")
        print(f"Loaded {len(self.geojson_files)} zone files")
        print(f"Total features: {sum(len(gdf) for gdf in self.geojson_files.values())}")
        
        # Calculate bounds for the entire dataset
        self.calculate_global_bounds()
        print(f"Global bounds: {self.bounds}")
    
    def load_all_geojson_files(self):
        """Load all GeoJSON files from the master plan directory"""
        self.geojson_files = {}
        
        # Get all .geojson files
        geojson_files = list(self.master_plan_dir.glob("*.geojson"))
        
        for file_path in geojson_files:
            try:
                # Load GeoJSON
                gdf = gpd.read_file(file_path)
                
                if not gdf.empty:
                    # Get zone name from filename (remove .geojson extension)
                    zone_name = file_path.stem
                    
                    # Map filename to style name
                    style_name = self.map_filename_to_style_name(zone_name)
                    
                    # Add zone name and style to the GeoDataFrame
                    gdf['zone_name'] = zone_name
                    gdf['style_name'] = style_name
                    
                    self.geojson_files[zone_name] = gdf
                    print(f"  ✅ Loaded {zone_name}: {len(gdf)} features")
                else:
                    print(f"  ⚠️  Skipped {file_path.name}: No features")
                    
            except Exception as e:
                print(f"  ❌ Error loading {file_path.name}: {e}")
    
    def map_filename_to_style_name(self, filename: str) -> str:
        """Map filename to style name from config"""
        # Remove file extension and clean up
        clean_name = filename.replace('_', ' ').replace('  ', ' ')
        
        # Direct mappings based on config
        mappings = {
            'Burial Ground': 'Burial Ground',
            'C1  Mixed use zone': 'C1 - Mixed Use Zone',
            'C2  General commercial zone': 'C2 - General Commercial Zone',
            'C3 Neighbourhood centre zone': 'C3 - Neighbourhood Centre Zone',
            'C4 Town centre zone': 'C4 - Town Centre Zone',
            'C5 Regional centre zone': 'C5 - Regional Centre Zone',
            'C6 Central business district zone': 'C6 - Central Business District Zone',
            'Commercial Vacant': 'Commercial Vacant',
            'I1 Business park zone': 'I1 - Business Park Zone',
            'I2 Logistics zone': 'I2 - Logistics Zone',
            'I3 Non polluting industry zone': 'I3 - Non Polluting Industry Zone',
            'P1 Passive zone': 'P1 - Passive Zone',
            'P2 Active zone': 'P2 - Active Zone',
            'P3 Protected zone': 'P3 - Protected Zone',
            'P3 Protected zone Hills': 'P3 - Protected Zone Hills',
            'PGN G': 'PGN-G',
            'PGN V': 'PGN-V',
            'R1 Village planning zone': 'R1 - Village Planning Zone',
            'R3 Medium to high density zone': 'R3 - Medium to High Density Zone',
            'R4 High density zone': 'R4 - High Density Zone',
            'RAA': 'RAA',
            'Residential Vacant': 'Residential Vacant',
            'S2 Education zone': 'S2 - Education Zone',
            'S3 Special zone': 'S3 - Special Zone',
            'SC1a Mixed Use': 'SC1a - Mixed Use',
            'SC1b   Mixed Use': 'SC1b - Mixed Use',
            'SP1  Passive Zone': 'SP1 - Passive Zone',
            'SP2  Active Zone': 'SP2 - Active Zone',
            'SP3 Protected Zone': 'SP3 - Protected Zone',
            'SR2 Low Density Housing': 'SR2 - Low Density Housing',
            'SR4   High Density Private': 'SR4 - High Density Private',
            'SS1   Government Zone': 'SS1 - Government Zone',
            'SS2a  Education Zone': 'SS2a - Education Zone',
            'SS2b Cultural Zone': 'SS2b - Cultural Zone',
            'SS2c Health Zone': 'SS2c - Health Zone',
            'SS3   Special Zone': 'SS3 - Special Zone',
            'SU1 Reserve Zone': 'SU1 - Reserve Zone',
            'SU2   Road Network': 'SU2 - Road Network',
            'U1 Reserve zone': 'U1 - Reserve Zone',
            'U2  Road reserve zone': 'U2 - Road Reserve Zone'
        }
        
        return mappings.get(clean_name, clean_name)
    
    def calculate_global_bounds(self):
        """Calculate global bounds from all loaded GeoJSON files"""
        all_bounds = []
        
        for gdf in self.geojson_files.values():
            if not gdf.empty:
                bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
                all_bounds.append(bounds)
        
        if all_bounds:
            # Calculate global bounds
            minx = min(bounds[0] for bounds in all_bounds)
            miny = min(bounds[1] for bounds in all_bounds)
            maxx = max(bounds[2] for bounds in all_bounds)
            maxy = max(bounds[3] for bounds in all_bounds)
            
            self.bounds = [minx, miny, maxx, maxy]
        else:
            # Default bounds for Amaravati
            self.bounds = [80.3, 16.4, 80.6, 16.6]
    
    def get_zone_style(self, zone_name: str) -> Dict:
        """Get style configuration for a zone with direct color mapping"""
        
        # Direct color mapping for all Amaravati zones
        zone_colors = {
            'Burial_Ground': {'fill_color': '#E39E00', 'stroke_color': None, 'pattern': 'SOLID'},
            'C1__Mixed_use_zone': {'fill_color': '#73B2FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'C2__General_commercial_zone': {'fill_color': '#00C5FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'C3_Neighbourhood_centre_zone': {'fill_color': '#00C5FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'C4_Town_centre_zone': {'fill_color': '#00A9E6', 'stroke_color': None, 'pattern': 'SOLID'},
            'C5_Regional_centre_zone': {'fill_color': '#0070FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'C6_Central_business_district_zone': {'fill_color': '#005CE6', 'stroke_color': None, 'pattern': 'SOLID'},
            'Commercial_Vacant': {'fill_color': '#C5E2FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'I1_Business_park_zone': {'fill_color': '#FFBEE8', 'stroke_color': None, 'pattern': 'SOLID'},
            'I2_Logistics_zone': {'fill_color': '#FF73DF', 'stroke_color': None, 'pattern': 'SOLID'},
            'I3_Non_polluting_industry_zone': {'fill_color': '#A900E6', 'stroke_color': None, 'pattern': 'SOLID'},
            'P1_Passive_zone': {'fill_color': '#267300', 'stroke_color': None, 'pattern': 'SOLID'},
            'P2_Active_zone': {'fill_color': '#38A800', 'stroke_color': None, 'pattern': 'SOLID'},
            'P3_Protected_zone': {'fill_color': '#BEE8FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'P3_Protected_zone_Hills': {'fill_color': '#4C7300', 'stroke_color': None, 'pattern': 'SOLID'},
            'PGN_G': {'fill_color': '#4C7300', 'stroke_color': None, 'pattern': 'SOLID'},
            'PGN_V': {'fill_color': '#897044', 'stroke_color': None, 'pattern': 'SOLID'},
            'R1_Village_planning_zone': {'fill_color': '#FFFFFF', 'stroke_color': '#000000', 'pattern': 'HATCH'},
            'R3_Medium_to_high_density_zone': {'fill_color': '#F5CA7A', 'stroke_color': None, 'pattern': 'SOLID'},
            'R4_High_density_zone': {'fill_color': '#E69800', 'stroke_color': None, 'pattern': 'SOLID'},
            'RAA': {'fill_color': '#FFAA00', 'stroke_color': None, 'pattern': 'SOLID'},
            'Residential_Vacant': {'fill_color': '#FFD37F', 'stroke_color': None, 'pattern': 'SOLID'},
            'S2_Education_zone': {'fill_color': '#FFF7F7', 'stroke_color': None, 'pattern': 'SOLID'},
            'S3_Special_zone': {'fill_color': '#D7B09E', 'stroke_color': None, 'pattern': 'SOLID'},
            'SC1a_Mixed_Use': {'fill_color': '#0070FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'SC1b___Mixed_Use': {'fill_color': '#73B2FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'SP1__Passive_Zone': {'fill_color': '#267300', 'stroke_color': None, 'pattern': 'SOLID'},
            'SP2__Active_Zone': {'fill_color': '#38A800', 'stroke_color': None, 'pattern': 'SOLID'},
            'SP3_Protected_Zone': {'fill_color': '#00C5FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'SR2_Low_Density_Housing': {'fill_color': '#FFFFBE', 'stroke_color': None, 'pattern': 'SOLID'},
            'SR4___High_Density_Private': {'fill_color': '#FFAA00', 'stroke_color': None, 'pattern': 'SOLID'},
            'SS1___Government_Zone': {'fill_color': '#E60000', 'stroke_color': None, 'pattern': 'SOLID'},
            'SS2a__Education_Zone': {'fill_color': '#FFF7F7', 'stroke_color': None, 'pattern': 'SOLID'},
            'SS2b_Cultural_Zone': {'fill_color': '#C500FF', 'stroke_color': None, 'pattern': 'SOLID'},
            'SS2c_Health_Zone': {'fill_color': '#D3FFBE', 'stroke_color': None, 'pattern': 'SOLID'},
            'SS3___Special_Zone': {'fill_color': '#A83800', 'stroke_color': None, 'pattern': 'SOLID'},
            'SU1_Reserve_Zone': {'fill_color': '#E1E1E1', 'stroke_color': None, 'pattern': 'SOLID'},
            'SU2___Road_Network': {'fill_color': '#FFFFFF', 'stroke_color': None, 'pattern': 'SOLID'},
            'U1_Reserve_zone': {'fill_color': '#CCCCCC', 'stroke_color': None, 'pattern': 'SOLID'},
            'U2__Road_reserve_zone': {'fill_color': '#C47362', 'stroke_color': None, 'pattern': 'SOLID'}
        }
        
        # Get the style for this zone
        style = zone_colors.get(zone_name, {
            'fill_color': '#CCCCCC',  # Default gray
            'stroke_color': None,
            'pattern': 'SOLID',
            'stroke_width': 0
        })
        
        # Set stroke width based on whether stroke color exists
        style['stroke_width'] = 1 if style.get('stroke_color') else 0
        
        return style
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def web_mercator_to_pixels(self, lon: float, lat: float, zoom: int, 
                              tile_x: int, tile_y: int) -> Tuple[float, float]:
        """
        Convert lat/lon to pixel coordinates within a specific tile
        """
        # Get tile bounds in degrees
        tile_bounds = mercantile.bounds(tile_x, tile_y, zoom)
        
        # Convert to pixel coordinates within the tile
        x_pixel = ((lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west)) * self.tile_size
        y_pixel = ((tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south)) * self.tile_size
        
        return x_pixel, y_pixel
    
    def draw_polygon(self, draw: ImageDraw, polygon, zoom: int, tile_x: int, tile_y: int,
                    fill_color: Tuple, stroke_color: Tuple = None, 
                    stroke_width: int = 0, pattern: str = 'SOLID') -> bool:
        """Draw a polygon with fill and optional stroke/hatch pattern"""
        try:
            # Handle both Polygon and MultiPolygon
            if polygon.geom_type == 'Polygon':
                polygons = [polygon]
            elif polygon.geom_type == 'MultiPolygon':
                polygons = list(polygon.geoms)
            else:
                return False
            
            drawn = False
            for poly in polygons:
                # Convert exterior ring to pixel coordinates
                pixel_coords = []
                for coord in poly.exterior.coords:
                    px, py = self.web_mercator_to_pixels(coord[0], coord[1], 
                                                       zoom, tile_x, tile_y)
                    pixel_coords.append((px, py))
                
                if len(pixel_coords) >= 3:
                    # Draw filled polygon
                    draw.polygon(pixel_coords, fill=fill_color + (255,))  # Full opacity
                    
                    # Draw stroke if specified
                    if stroke_color and stroke_width > 0:
                        draw.polygon(pixel_coords, outline=stroke_color + (255,), width=stroke_width)
                    
                    # Draw hatch pattern if specified
                    if pattern == 'HATCH' and stroke_color:
                        self.draw_hatch_pattern(draw, pixel_coords, stroke_color)
                    
                    drawn = True
            
            return drawn
        except Exception as e:
            print(f"    Error drawing polygon: {e}")
            return False
    
    def draw_hatch_pattern(self, draw: ImageDraw, pixel_coords: List[Tuple], 
                          hatch_color: Tuple, spacing: int = 8):
        """Draw a simple diagonal hatch pattern"""
        try:
            # Get bounding box
            x_coords = [p[0] for p in pixel_coords]
            y_coords = [p[1] for p in pixel_coords]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Draw diagonal lines
            for i in range(0, int(max_x - min_x + max_y - min_y), spacing):
                start_x = min_x + i
                start_y = min_y
                end_x = min_x
                end_y = min_y + i
                
                if start_x > max_x:
                    start_x = max_x
                    start_y = min_y + (start_x - max_x)
                
                if end_y > max_y:
                    end_y = max_y
                    end_x = min_x + (end_y - max_y)
                
                # Draw diagonal line
                draw.line([(start_x, start_y), (end_x, end_y)], 
                         fill=hatch_color + (255,), width=1)
        except Exception:
            pass  # Ignore hatch pattern errors
    
    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """
        Generate a single PNG tile for given coordinates
        
        Args:
            x, y: Tile coordinates
            zoom: Zoom level
            
        Returns:
            PIL Image of the tile or None if no features
        """
        # Get tile bounds
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        # Create image with transparent background
        img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        features_drawn = 0
        
        # Process each zone file
        for zone_name, gdf in self.geojson_files.items():
            # Check if any features intersect this tile (with buffer)
            buffer = 0.001  # Small buffer to catch edge cases
            tile_gdf = gdf.cx[
                tile_bounds.west - buffer:tile_bounds.east + buffer,
                tile_bounds.south - buffer:tile_bounds.north + buffer
            ]
            
            if tile_gdf.empty:
                continue
            
            # Get style for this zone
            style = self.get_zone_style(zone_name)
            fill_color = self.hex_to_rgb(style['fill_color'])
            stroke_color = self.hex_to_rgb(style.get('stroke_color', '#000000')) if style.get('stroke_color') else None
            stroke_width = style.get('stroke_width', 0)
            pattern = style.get('pattern', 'SOLID')
            
            # Draw features
            for idx, row in tile_gdf.iterrows():
                geom = row.geometry
                
                # Handle all polygon types
                if geom.geom_type in ['Polygon', 'MultiPolygon']:
                    if self.draw_polygon(draw, geom, zoom, x, y, fill_color, stroke_color, stroke_width, pattern):
                        features_drawn += 1
        
        return img if features_drawn > 0 else None
    
    def get_tile_list_for_zoom(self, zoom: int) -> List[Tuple[int, int]]:
        """
        Get list of tile coordinates that intersect with the data bounds
        
        Args:
            zoom: Zoom level
            
        Returns:
            List of (x, y) tile coordinates
        """
        minx, miny, maxx, maxy = self.bounds
        
        # Get tiles that cover the bounding box
        tiles = list(mercantile.tiles(minx, miny, maxx, maxy, zoom))
        
        return [(tile.x, tile.y) for tile in tiles]
    
    def generate_png_tiles(self, min_zoom: int = 4, max_zoom: int = 7):
        """
        Generate PNG tiles for all zoom levels
        
        Args:
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
        """
        print(f"\n🎨 Generating Amaravati Master Plan PNG tiles from zoom {min_zoom} to {max_zoom}")
        print(f"Zones: {len(self.geojson_files)}")
        
        total_tiles = 0
        total_empty_skipped = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"\n📍 Zoom level {zoom}")
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            # Get tiles that intersect with data
            tiles = self.get_tile_list_for_zoom(zoom)
            print(f"   Checking {len(tiles)} potential tiles...")
            
            tiles_generated = 0
            tiles_skipped = 0
            
            for i, (tile_x, tile_y) in enumerate(tiles):
                # Create x directory
                x_dir = zoom_dir / str(tile_x)
                x_dir.mkdir(exist_ok=True)
                
                # Generate tile
                tile_path = x_dir / f"{tile_y}.png"
                
                if not tile_path.exists():
                    try:
                        tile_img = self.generate_tile(tile_x, tile_y, zoom)
                        
                        if tile_img is not None:
                            tile_img.save(tile_path, 'PNG', optimize=True)
                            tiles_generated += 1
                            total_tiles += 1
                        else:
                            tiles_skipped += 1
                            total_empty_skipped += 1
                            
                    except Exception as e:
                        print(f"    ❌ Error generating tile {tile_x}/{tile_y}: {e}")
                
                # Progress indicator
                if (i + 1) % 100 == 0:
                    print(f"    Processed {i + 1}/{len(tiles)} tiles...")
            
            print(f"   ✅ Generated: {tiles_generated} tiles")
            print(f"   ⏭️  Skipped empty: {tiles_skipped} tiles")
        
        print(f"\n🎉 Generation Complete!")
        print(f"✅ Total tiles created: {total_tiles}")
        print(f"⏭️  Empty tiles skipped: {total_empty_skipped}")
        print(f"📁 Output directory: {self.output_dir.absolute()}")
    
    def create_mapbox_style_json(self) -> dict:
        """Create Mapbox GL style JSON for the PNG tiles"""
        minx, miny, maxx, maxy = self.bounds
        
        style = {
            "version": 8,
            "name": "Amaravati Master Plan",
            "metadata": {
                "description": "Amaravati Capital City Master Plan PNG tiles"
            },
            "sources": {
                "amaravati-tiles": {
                    "type": "raster",
                    "tiles": [
                        f"http://localhost:8000/{{z}}/{{x}}/{{y}}.png"
                    ],
                    "tileSize": 256,
                    "minzoom": 8,
                    "maxzoom": 16,
                    "bounds": [minx, miny, maxx, maxy]
                }
            },
            "layers": [
                {
                    "id": "amaravati-master-plan",
                    "type": "raster",
                    "source": "amaravati-tiles",
                    "paint": {
                        "raster-opacity": 1.0
                    }
                }
            ]
        }
        
        style_path = self.output_dir / "mapbox_style.json"
        with open(style_path, 'w') as f:
            json.dump(style, f, indent=2)
        
        print(f"✅ Created Mapbox style: {style_path}")
        return style
    
    def create_tilejson(self) -> dict:
        """Create TileJSON for the PNG tiles"""
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 11]
        
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Amaravati Master Plan",
            "description": "Amaravati Capital City Master Plan PNG tiles with zone-based styling",
            "version": "1.0.0",
            "attribution": "Amaravati Master Plan Data",
            "scheme": "xyz",
            "tiles": [
                f"http://localhost:8000/{{z}}/{{x}}/{{y}}.png"
            ],
            "minzoom": 8,
            "maxzoom": 16,
            "bounds": [minx, miny, maxx, maxy],
            "center": center
        }
        
        tilejson_path = self.output_dir / "tile.json"
        with open(tilejson_path, 'w') as f:
            json.dump(tilejson, f, indent=2)
        
        print(f"✅ Created TileJSON: {tilejson_path}")
        return tilejson
    
    def create_mapbox_viewer(self):
        """Create a Mapbox GL JS viewer HTML file"""
        minx, miny, maxx, maxy = self.bounds
        center_lon = (minx + maxx) / 2
        center_lat = (miny + maxy) / 2
        
        # Create zone legend
        zone_legend = ""
        for zone_name, gdf in self.geojson_files.items():
            style = self.get_zone_style(zone_name)
            color = style['fill_color']
            zone_legend += f'<div style="display: flex; align-items: center; margin: 5px 0;"><div style="width: 20px; height: 20px; background-color: {color}; margin-right: 10px; border: 1px solid #ccc;"></div><span style="font-size: 12px;">{zone_name}</span></div>'
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Amaravati Master Plan - PNG Tiles</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: absolute; top: 10px; right: 10px;
            background: white; padding: 15px; border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000;
            max-width: 300px; max-height: 80vh; overflow-y: auto;
        }}
        .legend {{
            margin-top: 15px; padding-top: 15px; border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>Amaravati Master Plan</h3>
        <p><strong>Zoom:</strong> <span id="zoom-display">11</span></p>
        <p><strong>Format:</strong> PNG Tiles</p>
        <p><strong>Zones:</strong> {len(self.geojson_files)}</p>
        <small>Generated with Amaravati Master Plan PNG Tile Generator</small>
        
        <div class="legend">
            <h4>Zone Types:</h4>
            {zone_legend}
        </div>
    </div>
    
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                version: 8,
                sources: {{
                    'osm': {{
                        type: 'raster',
                        tiles: ['https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'],
                        tileSize: 256,
                        attribution: '© OpenStreetMap contributors'
                    }},
                    'amaravati-tiles': {{
                        type: 'raster',
                        tiles: ['http://localhost:8000/{{z}}/{{x}}/{{y}}.png'],
                        tileSize: 256,
                        minzoom: 8,
                        maxzoom: 16
                    }}
                }},
                layers: [
                    {{
                        id: 'osm-background',
                        type: 'raster',
                        source: 'osm',
                        paint: {{ 'raster-opacity': 0.3 }}
                    }},
                    {{
                        id: 'amaravati-master-plan',
                        type: 'raster',
                        source: 'amaravati-tiles',
                        paint: {{ 'raster-opacity': 1.0 }}
                    }}
                ]
            }},
            center: [{center_lon}, {center_lat}],
            zoom: 11
        }});

        map.addControl(new mapboxgl.NavigationControl());

        function updateZoomDisplay() {{
            const zoom = Math.round(map.getZoom() * 10) / 10;
            document.getElementById('zoom-display').textContent = 'Zoom: ' + zoom;
        }}

        map.on('zoom', updateZoomDisplay);
        map.on('load', updateZoomDisplay);

        console.log('🏛️ Amaravati Master Plan PNG Tiles loaded!');
        console.log('PNG tiles with zone-based styling');
    </script>
</body>
</html>"""
        
        viewer_path = self.output_dir / "mapbox_png_viewer.html"
        with open(viewer_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Created Mapbox PNG viewer: {viewer_path}")

def main():
    """Main function to generate Amaravati Master Plan PNG tiles"""
    
    # Configuration
    master_plan_dir = "data/andhra_pradesh/amaravati/master_plan"
    output_dir = "amaravati_master_plan_tiles"
    
    # Check if master plan directory exists
    if not os.path.exists(master_plan_dir):
        print(f"❌ Error: Master plan directory not found at {master_plan_dir}")
        return
    
    # Initialize generator
    generator = AmaravatiMasterPlanTileGenerator(master_plan_dir, output_dir)
    
    # Generate PNG tiles
    generator.generate_png_tiles(min_zoom=17, max_zoom=18)
    
    # Create supporting files
    generator.create_mapbox_style_json()
    generator.create_tilejson()
    generator.create_mapbox_viewer()
    
    print("\n" + "="*60)
    print("🎉 AMARAVATI MASTER PLAN PNG TILES COMPLETE!")
    print("="*60)
    print(f"✅ Zones: {len(generator.geojson_files)}")
    print(f"✅ Colors from config")
    print(f"✅ No empty tiles generated")
    print(f"✅ Mapbox GL JS/SDK compatible")
    print(f"✅ Standard XYZ tile format")
    print(f"✅ Transparent backgrounds")
    print(f"\n📁 Output: {generator.output_dir.absolute()}")
    print(f"\n🌐 To serve:")
    print(f"  cd {output_dir}")
    print(f"  python -m http.server 8000")
    print(f"\n📱 View at:")
    print(f"  http://localhost:8000/mapbox_png_viewer.html")
    print(f"\n🗺️ Use in Mapbox:")
    print(f"  Tiles: http://localhost:8000/{{z}}/{{x}}/{{y}}.png")
    print(f"  Style: http://localhost:8000/mapbox_style.json")

if __name__ == "__main__":
    main()
