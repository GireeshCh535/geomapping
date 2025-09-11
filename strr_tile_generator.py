#!/usr/bin/env python3
"""
Perfect STRR Tile Generator for Bangalore
Generates high-quality PNG tiles from STRR GeoJSON data with color #14e098
Clean, robust, and optimized for production use
"""

import os
import sys
import math
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

import mercantile
from PIL import Image, ImageDraw, ImageFilter
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, box, Point
from shapely.ops import unary_union
from shapely.validation import make_valid
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PerfectSTRRTileGenerator:
    """
    Perfect STRR Tile Generator - Clean, robust, and optimized
    Generates high-quality PNG tiles with color #14e098
    """
    
    def __init__(self, 
                 data_path: str = "data/karnataka/bengaluru/strr/STRR.geojson",
                 output_dir: str = "karnataka_bengaluru_strr_tiles",
                 min_zoom: int = 8,
                 max_zoom: int = 18,
                 skip_existing: bool = True,
                 max_workers: int = 4):
        """
        Initialize the perfect STRR tile generator
        
        Args:
            data_path: Path to STRR GeoJSON file
            output_dir: Output directory for tiles
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            skip_existing: Skip existing tiles
            max_workers: Number of parallel workers
        """
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.skip_existing = skip_existing
        self.max_workers = max_workers
        
        # STRR Color: #14e098
        self.strr_color = (20, 224, 152)
        
        # Tile configuration
        self.tile_size = 256
        
        # Line width configuration by zoom level
        self.line_widths = {
            8: 1, 9: 1, 10: 2, 11: 2, 12: 3, 13: 4, 14: 5, 15: 6, 16: 8, 17: 10, 18: 12
        }
        
        # Data storage
        self.gdf = None
        self.spatial_index = None
        self.bounds = None
        
        # Statistics
        self.stats = {
            'tiles_generated': 0,
            'tiles_skipped': 0,
            'tiles_empty': 0,
            'errors': 0
        }
        
        logger.info("Perfect STRR Tile Generator initialized")
        logger.info(f"Data path: {self.data_path}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Zoom levels: {self.min_zoom} to {self.max_zoom}")
        logger.info(f"STRR Color: #14e098")
    
    def load_and_validate_data(self) -> bool:
        """
        Load and validate STRR data with comprehensive error handling
        
        Returns:
            bool: True if data loaded successfully, False otherwise
        """
        try:
            logger.info("Loading STRR data...")
            
            if not self.data_path.exists():
                logger.error(f"Data file not found: {self.data_path}")
                return False
            
            # Load GeoJSON data
            self.gdf = gpd.read_file(self.data_path)
            
            if self.gdf.empty:
                logger.error("No data found in STRR file")
                return False
            
            logger.info(f"Loaded {len(self.gdf)} features")
            
            # Ensure CRS is WGS84
            if self.gdf.crs is None:
                self.gdf.crs = 'EPSG:4326'
                logger.info("Set CRS to EPSG:4326")
            elif self.gdf.crs != 'EPSG:4326':
                self.gdf = self.gdf.to_crs('EPSG:4326')
                logger.info("Converted CRS to EPSG:4326")
            
            # Validate and clean geometries
            self._clean_geometries()
            
            # Build spatial index
            self.spatial_index = self.gdf.sindex
            logger.info("Built spatial index")
            
            # Calculate bounds
            self.bounds = self.gdf.total_bounds
            logger.info(f"Data bounds: {self.bounds}")
            
            # Log feature information
            self._log_feature_info()
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False
    
    def _clean_geometries(self):
        """Clean and validate geometries"""
        logger.info("Cleaning geometries...")
        
        cleaned_geometries = []
        for idx, row in self.gdf.iterrows():
            geom = row.geometry
            
            # Fix invalid geometries
            if not geom.is_valid:
                try:
                    geom = make_valid(geom)
                except:
                    logger.warning(f"Could not fix geometry at index {idx}")
                    continue
            
            # Remove duplicate coordinates and simplify
            geom = self._remove_duplicate_coordinates(geom)
            geom = self._simplify_geometry(geom)
            
            cleaned_geometries.append(geom)
        
        self.gdf.geometry = cleaned_geometries
        logger.info("Geometry cleaning completed")
    
    def _remove_duplicate_coordinates(self, geom):
        """Remove duplicate coordinates from geometry"""
        try:
            if hasattr(geom, 'geoms'):  # MultiLineString
                cleaned_geoms = []
                for g in geom.geoms:
                    coords = list(g.coords)
                    # Remove consecutive duplicates
                    cleaned_coords = [coords[0]]
                    for coord in coords[1:]:
                        if coord != cleaned_coords[-1]:
                            cleaned_coords.append(coord)
                    
                    if len(cleaned_coords) >= 2:
                        cleaned_geoms.append(LineString(cleaned_coords))
                
                return MultiLineString(cleaned_geoms) if len(cleaned_geoms) > 1 else (cleaned_geoms[0] if cleaned_geoms else geom)
            
            elif hasattr(geom, 'coords'):  # LineString
                coords = list(geom.coords)
                cleaned_coords = [coords[0]]
                for coord in coords[1:]:
                    if coord != cleaned_coords[-1]:
                        cleaned_coords.append(coord)
                
                return LineString(cleaned_coords) if len(cleaned_coords) >= 2 else geom
            
            return geom
            
        except Exception as e:
            logger.warning(f"Error removing duplicate coordinates: {e}")
            return geom
    
    def _simplify_geometry(self, geom):
        """Simplify geometry for better performance"""
        try:
            # Only simplify if geometry has many points
            if hasattr(geom, 'geoms'):
                total_points = sum(len(g.coords) for g in geom.geoms)
            else:
                total_points = len(geom.coords)
            
            if total_points > 1000:
                tolerance = 0.00001  # Small tolerance for simplification
                return geom.simplify(tolerance, preserve_topology=True)
            
            return geom
            
        except Exception as e:
            logger.warning(f"Error simplifying geometry: {e}")
            return geom
    
    def _log_feature_info(self):
        """Log detailed feature information"""
        logger.info("=" * 60)
        logger.info("STRR FEATURE INFORMATION")
        logger.info("=" * 60)
        
        for idx, row in self.gdf.iterrows():
            props = row.get('properties', {})
            name = props.get('Name', f'Feature {idx}')
            status = props.get('Current_Status', 'Unknown')
            width = props.get('Width', 'Unknown')
            
            # Count coordinate points
            if hasattr(row.geometry, 'geoms'):
                total_points = sum(len(g.coords) for g in row.geometry.geoms)
                segments = len(row.geometry.geoms)
            else:
                total_points = len(row.geometry.coords)
                segments = 1
            
            logger.info(f"Feature {idx + 1}: {name}")
            logger.info(f"  Status: {status}")
            logger.info(f"  Width: {width}")
            logger.info(f"  Segments: {segments}")
            logger.info(f"  Coordinate Points: {total_points}")
        
        logger.info("=" * 60)
    
    def get_tiles_for_bounds(self, zoom: int) -> List[mercantile.Tile]:
        """Get all tiles that intersect with data bounds at given zoom level"""
        west, south, east, north = self.bounds
        
        # Add small buffer to ensure we capture edge tiles
        buffer = 0.001
        buffered_bounds = (
            max(-180, west - buffer),
            max(-85, south - buffer),
            min(180, east + buffer),
            min(85, north + buffer)
        )
        
        tiles = list(mercantile.tiles(*buffered_bounds, [zoom]))
        logger.info(f"Zoom {zoom}: Found {len(tiles)} tiles")
        
        return tiles
    
    def get_features_for_tile(self, tile: mercantile.Tile) -> gpd.GeoDataFrame:
        """Get features that intersect with a specific tile"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(tile)
            tile_polygon = box(tile_bounds.west, tile_bounds.south, tile_bounds.east, tile_bounds.north)
            
            # Use spatial index for efficient intersection
            possible_matches_idx = list(self.spatial_index.intersection(tile_polygon.bounds))
            if not possible_matches_idx:
                return self.gdf.iloc[0:0]  # Empty GeoDataFrame
            
            possible_matches = self.gdf.iloc[possible_matches_idx]
            intersecting_features = possible_matches[possible_matches.intersects(tile_polygon)]
            
            return intersecting_features
            
        except Exception as e:
            logger.error(f"Error getting features for tile {tile}: {e}")
            return self.gdf.iloc[0:0]
    
    def coords_to_pixels(self, coords: List[Tuple[float, float]], tile_bounds) -> List[Tuple[float, float]]:
        """Convert geographic coordinates to pixel coordinates"""
        pixels = []
        for lon, lat in coords:
            # Convert to tile-relative coordinates (0-1)
            x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west)
            y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south)
            
            # Convert to pixel coordinates
            pixel_x = x * self.tile_size
            pixel_y = y * self.tile_size
            
            pixels.append((pixel_x, pixel_y))
        
        return pixels
    
    def draw_line_with_antialiasing(self, draw: ImageDraw.Draw, pixels: List[Tuple[float, float]], 
                                  color: Tuple[int, int, int], width: int):
        """Draw line with anti-aliasing for smooth rendering"""
        if len(pixels) < 2:
            return
        
        # Draw main line
        draw.line(pixels, fill=color, width=width)
        
        # Add subtle highlight for wider lines
        if width > 3:
            highlight_color = tuple(min(255, c + 20) for c in color)
            draw.line(pixels, fill=highlight_color, width=max(1, width // 2))
    
    def generate_single_tile(self, tile: mercantile.Tile) -> str:
        """Generate a single tile with perfect rendering"""
        try:
            # Check if tile already exists
            tile_path = self.output_dir / str(tile.z) / str(tile.x) / f"{tile.y}.png"
            
            if tile_path.exists() and self.skip_existing:
                self.stats['tiles_skipped'] += 1
                return "skipped"
            
            # Get features for this tile
            features = self.get_features_for_tile(tile)
            
            if features.empty:
                # Create empty tile
                tile_path.parent.mkdir(parents=True, exist_ok=True)
                empty_img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
                empty_img.save(tile_path, 'PNG')
                self.stats['tiles_empty'] += 1
                return "empty"
            
            # Create tile image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Get tile bounds and line width
            tile_bounds = mercantile.bounds(tile)
            line_width = self.line_widths.get(tile.z, 3)
            
            # Render each feature
            for _, feature in features.iterrows():
                geom = feature.geometry
                
                # Handle different geometry types
                if hasattr(geom, 'geoms'):  # MultiLineString
                    for g in geom.geoms:
                        if hasattr(g, 'coords') and len(g.coords) >= 2:
                            pixels = self.coords_to_pixels(g.coords, tile_bounds)
                            self.draw_line_with_antialiasing(draw, pixels, self.strr_color, line_width)
                
                elif hasattr(geom, 'coords') and len(geom.coords) >= 2:  # LineString
                    pixels = self.coords_to_pixels(geom.coords, tile_bounds)
                    self.draw_line_with_antialiasing(draw, pixels, self.strr_color, line_width)
            
            # Save tile
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(tile_path, 'PNG')
            self.stats['tiles_generated'] += 1
            
            return "generated"
            
        except Exception as e:
            logger.error(f"Error generating tile {tile.z}/{tile.x}/{tile.y}: {e}")
            self.stats['errors'] += 1
            return "error"
    
    def generate_tiles_parallel(self):
        """Generate tiles using parallel processing"""
        logger.info("Starting parallel tile generation...")
        
        total_tiles = 0
        
        for zoom in range(self.min_zoom, self.max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")
            
            # Get tiles for this zoom level
            tiles = self.get_tiles_for_bounds(zoom)
            
            if not tiles:
                logger.warning(f"No tiles found for zoom {zoom}")
                continue
            
            # Process tiles in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_tile = {
                    executor.submit(self.generate_single_tile, tile): tile
                    for tile in tiles
                }
                
                for future in as_completed(future_to_tile):
                    tile = future_to_tile[future]
                    try:
                        result = future.result()
                        total_tiles += 1
                        
                        # Log progress every 100 tiles
                        if total_tiles % 100 == 0:
                            logger.info(f"  Processed {total_tiles} tiles for zoom {zoom}")
                            
                    except Exception as e:
                        logger.error(f"Tile {tile.z}/{tile.x}/{tile.y} failed: {e}")
                        self.stats['errors'] += 1
        
        logger.info("Tile generation completed!")
        self._log_statistics()
    
    def _log_statistics(self):
        """Log generation statistics"""
        logger.info("=" * 60)
        logger.info("TILE GENERATION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Tiles generated: {self.stats['tiles_generated']}")
        logger.info(f"Tiles skipped: {self.stats['tiles_skipped']}")
        logger.info(f"Empty tiles: {self.stats['tiles_empty']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)
    
    def create_supporting_files(self):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Karnataka Bengaluru STRR",
            "description": "Satellite Town Ring Road (STRR) in Bengaluru, Karnataka",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                f"https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/strr/{{z}}/{{x}}/{{y}}.png"
            ],
            "grids": [],
            "data": [],
            "minzoom": self.min_zoom,
            "maxzoom": self.max_zoom,
            "bounds": list(self.bounds),
            "center": [
                (self.bounds[0] + self.bounds[2]) / 2,
                (self.bounds[1] + self.bounds[3]) / 2,
                10
            ]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Karnataka Bengaluru STRR",
            "sources": {
                "karnataka-bengaluru-strr": {
                    "type": "raster",
                    "tiles": [
                        f"https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/strr/{{z}}/{{x}}/{{y}}.png"
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "karnataka-bengaluru-strr-layer",
                    "type": "raster",
                    "source": "karnataka-bengaluru-strr",
                    "paint": {
                        "raster-opacity": 0.8
                    }
                }
            ]
        }
        
        with open(self.output_dir / "style.json", "w") as f:
            json.dump(style_json, f, indent=2)
        
        # Create HTML viewer
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Karnataka Bengaluru STRR</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
            font-family: Arial, sans-serif;
        }}
    </style>
</head>
<body>
    <div id='map'></div>
    <div class='info'>
        <h3>Karnataka Bengaluru STRR</h3>
        <p><strong>Satellite Town Ring Road</strong></p>
        <p>Color: #14e098</p>
        <p>Zoom: {self.min_zoom} - {self.max_zoom}</p>
    </div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "karnataka-bengaluru-strr": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/strr/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "karnataka-bengaluru-strr-layer",
                        "type": "raster",
                        "source": "karnataka-bengaluru-strr",
                        "paint": {{
                            "raster-opacity": 0.8
                        }}
                    }}
                ]
            }},
            center: [{(self.bounds[0] + self.bounds[2]) / 2}, {(self.bounds[1] + self.bounds[3]) / 2}],
            zoom: 10
        }});
    </script>
</body>
</html>"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("Created supporting files: tilejson.json, style.json, viewer.html")
    
    def run(self):
        """Run the complete tile generation process"""
        logger.info("Starting Perfect STRR Tile Generation")
        logger.info("=" * 60)
        
        try:
            # Load and validate data
            if not self.load_and_validate_data():
                logger.error("Failed to load data. Exiting.")
                return False
            
            # Generate tiles
            self.generate_tiles_parallel()
            
            # Create supporting files
            self.create_supporting_files()
            
            logger.info("Perfect STRR tile generation completed successfully!")
            logger.info(f"Tiles saved to: {self.output_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during tile generation: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Perfect STRR Tile Generator for Bangalore')
    parser.add_argument('--data-path', type=str, 
                       default='data/karnataka/bengaluru/strr/STRR.geojson',
                       help='Path to STRR GeoJSON file')
    parser.add_argument('--output-dir', type=str, 
                       default='karnataka_bengaluru_strr_tiles',
                       help='Output directory for tiles')
    parser.add_argument('--min-zoom', type=int, default=8,
                       help='Minimum zoom level (default: 8)')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level (default: 18)')
    parser.add_argument('--force', action='store_true',
                       help='Force regeneration of all tiles (ignore existing)')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of parallel workers (default: 4)')
    
    args = parser.parse_args()
    
    # Create generator
    generator = PerfectSTRRTileGenerator(
        data_path=args.data_path,
        output_dir=args.output_dir,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        skip_existing=not args.force,
        max_workers=args.workers
    )
    
    # Run generation
    success = generator.run()
    
    if success:
        logger.info("\n🎉 Perfect STRR tile generation completed successfully!")
        logger.info(f"📁 Tiles saved to: {args.output_dir}")
        logger.info("🌐 Open viewer.html to preview the tiles")
        sys.exit(0)
    else:
        logger.error("\n❌ Tile generation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
