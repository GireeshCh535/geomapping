#!/usr/bin/env python3
"""
Mapbox-Compatible PNG Tile Generator for RRR Roads
=================================================

Generates PNG raster tiles compatible with Mapbox with:
- Road color: #14E098
- Zoom-dependent line widths (proper scaling)
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
from typing import Tuple, List
import mercantile

class MapboxPNGTileGenerator:
    def __init__(self, geojson_path: str, output_dir: str = "mapbox_png_tiles"):
        """
        Initialize the Mapbox PNG tile generator
        
        Args:
            geojson_path: Path to the RRR_Final.geojson file
            output_dir: Directory to save generated tiles
        """
        self.geojson_path = geojson_path
        self.output_dir = Path(output_dir)
        self.road_color = "#14E098"
        self.tile_size = 256  # Standard Mapbox tile size
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Load GeoJSON data
        self.gdf = gpd.read_file(geojson_path)
        print(f"🚗 Mapbox PNG Tile Generator")
        print(f"Loaded {len(self.gdf)} features from {geojson_path}")
        
        # Calculate bounds for the data
        self.bounds = self.gdf.total_bounds  # [minx, miny, maxx, maxy]
        print(f"Data bounds: {self.bounds}")
    
    def get_mapbox_line_width(self, zoom: int) -> float:
        """
        Get Mapbox-style zoom-dependent line width
        
        Args:
            zoom: Zoom level (0-20)
            
        Returns:
            Line width in pixels
        """
        # Mapbox-style zoom stops for ring roads
        zoom_stops = {
            0: 0.2, 1: 0.2, 2: 0.3, 3: 0.3, 4: 0.4,      # Very low zoom
            5: 0.5, 6: 0.6, 7: 0.8, 8: 1.0,               # Low zoom
            9: 1.3, 10: 1.6, 11: 2.0,                     # Medium zoom
            12: 2.5, 13: 3.2, 14: 4.0,                    # High zoom
            15: 5.0, 16: 6.5, 17: 8.0, 18: 10.0,          # Very high zoom
            19: 12.0, 20: 15.0
        }
        
        return zoom_stops.get(zoom, 3.0)
    
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
        
        # Check if any features intersect this tile (with buffer)
        buffer = 0.001  # Small buffer to catch edge cases
        tile_gdf = self.gdf.cx[
            tile_bounds.west - buffer:tile_bounds.east + buffer,
            tile_bounds.south - buffer:tile_bounds.north + buffer
        ]
        
        if tile_gdf.empty:
            return None  # No features in this tile
        
        # Create image with transparent background
        img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Get line width for this zoom level
        line_width = max(1, int(self.get_mapbox_line_width(zoom)))
        
        # Convert hex color to RGB
        color_rgb = tuple(int(self.road_color[i:i+2], 16) for i in (1, 3, 5))
        
        # Draw roads
        features_drawn = False
        for idx, row in tile_gdf.iterrows():
            geom = row.geometry
            
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                
                # Convert coordinates to pixel positions
                pixel_coords = []
                for lon, lat in coords:
                    x_pixel, y_pixel = self.web_mercator_to_pixels(lon, lat, zoom, x, y)
                    pixel_coords.append((x_pixel, y_pixel))
                
                # Draw line segments if we have at least 2 points
                if len(pixel_coords) >= 2:
                    for i in range(len(pixel_coords) - 1):
                        p1, p2 = pixel_coords[i], pixel_coords[i + 1]
                        
                        # Check if line segment is visible in tile (with margin)
                        margin = line_width + 10
                        if (any(-margin <= coord <= self.tile_size + margin for coord in [p1[0], p1[1], p2[0], p2[1]])):
                            draw.line([p1, p2], fill=color_rgb, width=line_width)
                            features_drawn = True
        
        return img if features_drawn else None
    
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
    
    def generate_png_tiles(self, min_zoom: int = 5, max_zoom: int = 16):
        """
        Generate PNG tiles for all zoom levels
        
        Args:
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
        """
        print(f"\n🎨 Generating Mapbox PNG tiles from zoom {min_zoom} to {max_zoom}")
        print(f"Road color: {self.road_color}")
        
        total_tiles = 0
        total_empty_skipped = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"\n📍 Zoom level {zoom}")
            line_width = self.get_mapbox_line_width(zoom)
            print(f"   Line width: {line_width}px")
            
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
                if (i + 1) % 20 == 0:
                    print(f"    Processed {i + 1}/{len(tiles)} tiles...")
            
            print(f"   ✅ Generated: {tiles_generated} tiles")
            print(f"   ⏭️  Skipped empty: {tiles_skipped} tiles")
        
        print(f"\n🎉 Generation Complete!")
        print(f"✅ Total tiles created: {total_tiles}")
        print(f"⏭️  Empty tiles skipped: {total_empty_skipped}")
        print(f"📁 Output directory: {self.output_dir.absolute()}")
    
    def create_mapbox_style_json(self) -> dict:
        """
        Create Mapbox GL style JSON for the PNG tiles
        """
        minx, miny, maxx, maxy = self.bounds
        
        style = {
            "version": 8,
            "name": "RRR Roads PNG",
            "metadata": {
                "description": "Hyderabad Regional Ring Road PNG tiles"
            },
            "sources": {
                "rrr-tiles": {
                    "type": "raster",
                    "tiles": [
                        f"http://localhost:8000/{{z}}/{{x}}/{{y}}.png"
                    ],
                    "tileSize": 256,
                    "minzoom": 5,
                    "maxzoom": 16,
                    "bounds": [minx, miny, maxx, maxy]
                }
            },
            "layers": [
                {
                    "id": "rrr-roads",
                    "type": "raster",
                    "source": "rrr-tiles",
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
        """
        Create TileJSON for the PNG tiles
        """
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 10]
        
        tilejson = {
            "tilejson": "3.0.0",
            "name": "RRR Roads",
            "description": "Hyderabad Regional Ring Road PNG tiles with zoom-dependent styling",
            "version": "1.0.0",
            "attribution": "RRR Data",
            "scheme": "xyz",
            "tiles": [
                f"http://localhost:8000/{{z}}/{{x}}/{{y}}.png"
            ],
            "minzoom": 5,
            "maxzoom": 16,
            "bounds": [minx, miny, maxx, maxy],
            "center": center
        }
        
        tilejson_path = self.output_dir / "tilejson.json"
        with open(tilejson_path, 'w') as f:
            json.dump(tilejson, f, indent=2)
        
        print(f"✅ Created TileJSON: {tilejson_path}")
        return tilejson
    
    def create_mapbox_viewer(self):
        """
        Create Mapbox GL viewer for PNG tiles
        """
        bounds = self.bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>RRR Roads - Mapbox PNG Tiles</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: absolute; top: 10px; right: 10px;
            background: white; padding: 15px; border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            font-family: Arial, sans-serif; z-index: 1000;
        }}
        .zoom-info {{
            position: absolute; bottom: 10px; left: 10px;
            background: rgba(0,0,0,0.8); color: white;
            padding: 8px 12px; border-radius: 4px;
            font-family: monospace; z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>🚗 RRR PNG Tiles</h3>
        <p><strong>Color:</strong> {self.road_color}</p>
        <p><strong>Format:</strong> PNG Raster Tiles</p>
        <p><strong>Zoom:</strong> 5-16</p>
        <p><strong>Features:</strong> Zoom-dependent widths</p>
        <p><strong>Compatible:</strong> Mapbox GL JS/SDK</p>
        <small>No empty tiles • Optimized scaling</small>
    </div>
    <div class="zoom-info" id="zoom-display">Zoom: 10</div>

    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <script>
        const map = new mapboxgl.Map({{
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
                    'rrr-tiles': {{
                        type: 'raster',
                        tiles: ['http://localhost:8000/{{z}}/{{x}}/{{y}}.png'],
                        tileSize: 256,
                        minzoom: 5,
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
                        id: 'rrr-roads',
                        type: 'raster',
                        source: 'rrr-tiles',
                        paint: {{ 'raster-opacity': 1.0 }}
                    }}
                ]
            }},
            center: [{center_lon}, {center_lat}],
            zoom: 10
        }});

        map.addControl(new mapboxgl.NavigationControl());

        function updateZoomDisplay() {{
            const zoom = Math.round(map.getZoom() * 10) / 10;
            document.getElementById('zoom-display').textContent = 'Zoom: ' + zoom;
        }}

        map.on('zoom', updateZoomDisplay);
        map.on('load', updateZoomDisplay);

        console.log('🚗 RRR Mapbox PNG Tiles loaded!');
        console.log('PNG tiles with zoom-dependent line widths');
    </script>
</body>
</html>"""
        
        viewer_path = self.output_dir / "mapbox_png_viewer.html"
        with open(viewer_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Created Mapbox PNG viewer: {viewer_path}")

def main():
    """Main function to generate Mapbox-compatible PNG tiles"""
    
    # Configuration
    geojson_path = "static/geojson/RRR_Final.geojson"
    output_dir = "mapbox_png_tiles"
    
    # Check if GeoJSON file exists
    if not os.path.exists(geojson_path):
        print(f"❌ Error: GeoJSON file not found at {geojson_path}")
        return
    
    # Initialize generator
    generator = MapboxPNGTileGenerator(geojson_path, output_dir)
    
    # Generate PNG tiles
    generator.generate_png_tiles(min_zoom=5, max_zoom=16)
    
    # Create supporting files
    generator.create_mapbox_style_json()
    generator.create_tilejson()
    generator.create_mapbox_viewer()
    
    print("\n" + "="*60)
    print("🎉 MAPBOX PNG TILES COMPLETE!")
    print("="*60)
    print(f"✅ Road Color: {generator.road_color}")
    print(f"✅ Zoom-dependent line widths (0.5px → 15px)")
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