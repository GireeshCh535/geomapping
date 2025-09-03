#!/usr/bin/env python3
"""
Perfect tile generator for Future City Hyderabad GeoJSON boundary
Generates clean tiles with perfect borders and full data coverage
"""

import os
import sys
import math
import time
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw
import json
import logging
from shapely.geometry import shape, Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union
from shapely.prepared import prep

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PerfectFCDABoundaryTileGenerator:
    """
    Generate perfect PNG tiles from Future City Hyderabad GeoJSON boundary
    Clean tiles with proper borders and complete coverage
    """
    
    def __init__(self, data_dir="data/Telangana/Hyderabad/future-city", 
                 output_dir="hyderabad_future_city_boundary_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Colors for boundary visualization
        self.fill_color = (125, 125, 125, 128)      # #7D7D7D with 50% opacity (fill)
        self.border_color = (195, 195, 195, 255)    # #C3C3C3 with full opacity (border)
        self.border_width = 2                        # Border line width in pixels
        
        # Store the original boundary for reference
        self.original_boundary = None
        self.prepared_boundary = None  # For faster point-in-polygon tests
        
        logger.info("🚀 Perfect FCDA Boundary Tile Generator initialized")
        logger.info(f"📂 Data directory: {self.data_dir}")
        logger.info(f"📁 Output directory: {self.output_dir}")
    
    def load_geojson_boundary(self):
        """Load and parse the GeoJSON boundary with validation"""
        geojson_path = self.data_dir / "FCDA Boundary.geojson"
        
        if not geojson_path.exists():
            logger.error(f"❌ GeoJSON file not found: {geojson_path}")
            return None, None
        
        try:
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            
            features = data.get('features', [])
            if not features:
                logger.error("❌ No features found in GeoJSON")
                return None, None
            
            # Process all features and union them
            geometries = []
            for feature in features:
                geom = shape(feature['geometry'])
                # Ensure geometry is valid
                if not geom.is_valid:
                    geom = geom.buffer(0)  # Fix invalid geometries
                if geom.is_valid:
                    geometries.append(geom)
            
            if not geometries:
                logger.error("❌ No valid geometries found")
                return None, None
            
            # Union all geometries into a single shape
            boundary_shape = unary_union(geometries) if len(geometries) > 1 else geometries[0]
            
            # Ensure the final shape is valid
            if not boundary_shape.is_valid:
                boundary_shape = boundary_shape.buffer(0)
            
            # Store original boundary and prepare it for fast operations
            self.original_boundary = boundary_shape
            self.prepared_boundary = prep(boundary_shape)
            
            # Get bounds
            bounds = boundary_shape.bounds
            
            logger.info(f"✅ Loaded GeoJSON boundary successfully")
            logger.info(f"📊 Boundary type: {type(boundary_shape).__name__}")
            logger.info(f"📍 Bounds: [{bounds[0]:.6f}, {bounds[1]:.6f}, {bounds[2]:.6f}, {bounds[3]:.6f}]")
            logger.info(f"🔍 Shape is valid: {boundary_shape.is_valid}")
            logger.info(f"📏 Area: {boundary_shape.area:.6f} sq degrees")
            
            return boundary_shape, bounds
            
        except Exception as e:
            logger.error(f"❌ Error loading GeoJSON: {e}")
            return None, None
    
    def render_tile_perfect(self, boundary_shape, tile_bounds, zoom):
        """
        Render the boundary to a tile with perfect coverage and clean borders
        Returns the rendered image or None if no data in tile
        """
        try:
            # Create tile polygon
            tile_polygon = Polygon([
                (tile_bounds.west, tile_bounds.south),
                (tile_bounds.east, tile_bounds.south),
                (tile_bounds.east, tile_bounds.north),
                (tile_bounds.west, tile_bounds.north),
                (tile_bounds.west, tile_bounds.south)
            ])
            
            # Quick check: does this tile intersect with our boundary at all?
            if not boundary_shape.intersects(tile_polygon):
                return None
            
            # Clip boundary to tile bounds
            clipped_boundary = boundary_shape.intersection(tile_polygon)
            
            if clipped_boundary.is_empty:
                return None
            
            # Create tile image
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img, 'RGBA')
            
            # Calculate pixel conversion factors
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            def coord_to_pixel(lon, lat):
                """Convert WGS84 coordinates to tile pixel coordinates with subpixel precision"""
                px = (lon - tile_bounds.west) / tile_width * 256
                py = (tile_bounds.north - lat) / tile_height * 256
                return (px, py)
            
            # Convert clipped boundary to polygons
            polygons = []
            if isinstance(clipped_boundary, Polygon):
                polygons = [clipped_boundary]
            elif isinstance(clipped_boundary, MultiPolygon):
                polygons = list(clipped_boundary.geoms)
            
            if not polygons:
                return None
            
            # First pass: Draw filled polygons for complete coverage
            for polygon in polygons:
                if hasattr(polygon, 'exterior'):
                    # Get exterior coordinates
                    exterior_coords = list(polygon.exterior.coords)
                    if len(exterior_coords) >= 3:
                        # Convert to pixel coordinates
                        exterior_pixels = [coord_to_pixel(lon, lat) for lon, lat in exterior_coords]
                        
                        # Draw filled polygon
                        draw.polygon(exterior_pixels, fill=self.fill_color, outline=None)
                        
                        # Handle interior holes if any
                        for interior in polygon.interiors:
                            interior_coords = list(interior.coords)
                            if len(interior_coords) >= 3:
                                interior_pixels = [coord_to_pixel(lon, lat) for lon, lat in interior_coords]
                                # Cut out the hole with transparent fill
                                draw.polygon(interior_pixels, fill=(0, 0, 0, 0), outline=None)
            
            # Second pass: Draw borders only where they represent actual data boundaries
            for polygon in polygons:
                if hasattr(polygon, 'exterior'):
                    self._draw_clean_border(polygon.exterior.coords, tile_bounds, draw, coord_to_pixel)
                    
                    # Draw interior boundaries if any
                    for interior in polygon.interiors:
                        self._draw_clean_border(interior.coords, tile_bounds, draw, coord_to_pixel)
            
            return img
            
        except Exception as e:
            logger.error(f"❌ Error rendering tile at zoom {zoom}: {e}")
            return None
    
    def _draw_clean_border(self, coords, tile_bounds, draw, coord_to_pixel):
        """
        Draw clean borders only for actual data boundaries, not tile edges
        """
        coords_list = list(coords)
        if len(coords_list) < 2:
            return
        
        tolerance = 0.0000001  # Very small tolerance for edge detection
        
        for i in range(len(coords_list) - 1):
            p1 = coords_list[i]
            p2 = coords_list[i + 1]
            
            # Check if this segment is part of the original boundary
            midpoint = Point((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            
            # Only draw if this is part of the original boundary
            if self.original_boundary.boundary.distance(midpoint) < 0.00001:
                # Check if segment is NOT a tile edge
                is_tile_edge = False
                
                # Check if both points are on the same tile edge
                if abs(p1[0] - tile_bounds.west) < tolerance and abs(p2[0] - tile_bounds.west) < tolerance:
                    is_tile_edge = True
                elif abs(p1[0] - tile_bounds.east) < tolerance and abs(p2[0] - tile_bounds.east) < tolerance:
                    is_tile_edge = True
                elif abs(p1[1] - tile_bounds.south) < tolerance and abs(p2[1] - tile_bounds.south) < tolerance:
                    is_tile_edge = True
                elif abs(p1[1] - tile_bounds.north) < tolerance and abs(p2[1] - tile_bounds.north) < tolerance:
                    is_tile_edge = True
                
                # Only draw if it's not a tile edge or if it's also part of the original boundary
                if not is_tile_edge:
                    pixel1 = coord_to_pixel(p1[0], p1[1])
                    pixel2 = coord_to_pixel(p2[0], p2[1])
                    draw.line([pixel1, pixel2], fill=self.border_color, width=self.border_width)
    
    def generate_tiles(self, min_zoom=2, max_zoom=16):
        """Generate perfect PNG tiles for all zoom levels"""
        # Load GeoJSON boundary
        boundary_shape, bounds = self.load_geojson_boundary()
        if boundary_shape is None:
            logger.error("❌ Failed to load GeoJSON boundary")
            return 0
        
        total_tiles = 0
        tiles_with_data = 0
        start_time = time.time()
        
        # Statistics per zoom level
        zoom_stats = {}
        
        for zoom in range(min_zoom, max_zoom + 1):
            zoom_start = time.time()
            logger.info(f"🔄 Processing zoom level {zoom}")
            
            # Calculate tile bounds for this zoom level
            # Add small buffer to ensure edge tiles are included
            buffer = 0.01  # Buffer in degrees
            min_tile = mercantile.tile(
                max(-180, bounds[0] - buffer), 
                max(-85, bounds[1] - buffer), 
                zoom
            )
            max_tile = mercantile.tile(
                min(180, bounds[2] + buffer), 
                min(85, bounds[3] + buffer), 
                zoom
            )
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            zoom_tiles = 0
            zoom_tiles_with_data = 0
            
            # Process each tile
            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                
                for y in range(max_tile.y, min_tile.y + 1):
                    # Get tile bounds
                    tile_bounds = mercantile.bounds(x, y, zoom)
                    
                    # Render the tile
                    img = self.render_tile_perfect(boundary_shape, tile_bounds, zoom)
                    
                    if img is not None:
                        # Create x directory only if we have data
                        if not x_dir.exists():
                            x_dir.mkdir(exist_ok=True)
                        
                        # Save the tile
                        tile_path = x_dir / f"{y}.png"
                        img.save(tile_path, 'PNG', optimize=True, compress_level=9)
                        zoom_tiles_with_data += 1
                        tiles_with_data += 1
                    
                    zoom_tiles += 1
                    total_tiles += 1
            
            zoom_elapsed = time.time() - zoom_start
            zoom_stats[zoom] = {
                'total': zoom_tiles,
                'with_data': zoom_tiles_with_data,
                'time': zoom_elapsed
            }
            
            logger.info(f"✅ Zoom {zoom}: {zoom_tiles_with_data}/{zoom_tiles} tiles with data ({zoom_elapsed:.1f}s)")
        
        total_elapsed = time.time() - start_time
        
        # Print summary statistics
        logger.info("=" * 60)
        logger.info("📊 TILE GENERATION SUMMARY")
        logger.info("=" * 60)
        for zoom, stats in zoom_stats.items():
            if stats['with_data'] > 0:
                logger.info(f"  Zoom {zoom:2d}: {stats['with_data']:5d} tiles ({stats['time']:5.1f}s)")
        logger.info("-" * 60)
        logger.info(f"✅ Total tiles processed: {total_tiles:,}")
        logger.info(f"✅ Tiles with data: {tiles_with_data:,}")
        logger.info(f"⏱️  Total time: {total_elapsed:.1f}s")
        logger.info(f"⚡ Average: {total_elapsed/max(tiles_with_data,1):.3f}s per tile")
        logger.info("=" * 60)
        
        # Create supporting files
        self.create_supporting_files(bounds, min_zoom, max_zoom)
        
        return tiles_with_data
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("📝 Creating supporting files...")
        
        # Create tilejson
        tilejson = {
            "tilejson": "3.0.0",
            "name": "FCDA Boundary - Hyderabad",
            "description": "Future City Development Authority boundary tiles",
            "version": "1.0.0",
            "attribution": "FCDA",
            "scheme": "xyz",
            "tiles": [
                "{z}/{x}/{y}.png"
            ],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [bounds[0], bounds[1], bounds[2], bounds[3]],
            "center": [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2, 10]
        }
        
        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        # Create test HTML that works locally
        test_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>FCDA Boundary Tiles - Local Test</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ height: 100vh; }}
        .info {{
            padding: 8px 10px;
            background: white;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            border-radius: 5px;
        }}
        .info h4 {{ margin: 0 0 5px; color: #333; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        // Initialize map
        var map = L.map('map').setView([{(bounds[1] + bounds[3]) / 2}, {(bounds[0] + bounds[2]) / 2}], 10);
        
        // Base layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }}).addTo(map);
        
        // FCDA tiles - will work with local server
        var fcdaLayer = L.tileLayer('{{z}}/{{x}}/{{y}}.png', {{
            minZoom: {min_zoom},
            maxZoom: {max_zoom},
            opacity: 0.7,
            attribution: 'FCDA Boundary'
        }}).addTo(map);
        
        // Bounds rectangle
        var bounds = L.latLngBounds(
            [{bounds[1]}, {bounds[0]}],
            [{bounds[3]}, {bounds[2]}]
        );
        
        L.rectangle(bounds, {{
            color: "#ff0000",
            weight: 2,
            fill: false,
            dashArray: '5, 10'
        }}).addTo(map);
        
        // Layer control
        L.control.layers(
            {{"OpenStreetMap": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png')}},
            {{"FCDA Boundary": fcdaLayer}}
        ).addTo(map);
        
        // Info control
        var info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            this._div = L.DomUtil.create('div', 'info');
            this.update();
            return this._div;
        }};
        info.update = function() {{
            this._div.innerHTML = '<h4>FCDA Tiles</h4>Zoom: ' + map.getZoom();
        }};
        info.addTo(map);
        
        map.on('zoomend', function() {{ info.update(); }});
        map.fitBounds(bounds);
        
        // Tile debugging
        fcdaLayer.on('tileload', function(e) {{
            console.log('Loaded:', e.coords.z + '/' + e.coords.x + '/' + e.coords.y);
        }});
        
        console.log('To use: Run "python -m http.server 8000" in the tiles directory');
        console.log('Then open: http://localhost:8000/test.html');
    </script>
</body>
</html>"""
        
        with open(self.output_dir / "test.html", "w") as f:
            f.write(test_html)
        
        logger.info("✅ Created supporting files: metadata.json, test.html")
        logger.info("📌 To test: cd to output dir, run 'python -m http.server 8000', open http://localhost:8000/test.html")

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 PERFECT FCDA BOUNDARY TILE GENERATOR")
    logger.info("=" * 60)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Generate perfect tiles for FCDA boundary')
    parser.add_argument('--min-zoom', type=int, default=2, help='Minimum zoom level (default: 2)')
    parser.add_argument('--max-zoom', type=int, default=16, help='Maximum zoom level (default: 16)')
    parser.add_argument('--data-dir', default="data/Telangana/Hyderabad/future-city", help='Input data directory')
    parser.add_argument('--output-dir', default="hyderabad_future_city_boundary_tiles", help='Output directory')
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = PerfectFCDABoundaryTileGenerator(
        data_dir=args.data_dir,
        output_dir=args.output_dir
    )
    
    # Generate tiles
    total_tiles = generator.generate_tiles(
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom
    )
    
    if total_tiles > 0:
        logger.info("=" * 60)
        logger.info("🎉 TILE GENERATION COMPLETED SUCCESSFULLY!")
        logger.info(f"📊 Generated {total_tiles:,} tiles with clean borders")
        logger.info(f"📁 Output directory: {generator.output_dir.absolute()}")
        logger.info("=" * 60)
    else:
        logger.error("❌ No tiles were generated. Check your input data.")

if __name__ == "__main__":
    main()