#!/usr/bin/env python3
"""
Karnataka Bengaluru Master Plan Tile Generator
Generate high-quality PNG tiles from Karnataka Bengaluru master plan GeoJSON files
Uses the same rendering logic as Amaravati but with Bangalore-specific configuration
"""

import os
import json
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import math

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box, shape, mapping, Point
from shapely.ops import transform
import mercantile
from PIL import Image, ImageDraw, ImageFont
import pyproj
from functools import partial
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

class KarnatakaBengaluruMasterPlanTileGenerator:
    """Generate PNG tiles for Karnataka Bengaluru Master Plan with perfect rendering."""
    
    def __init__(self, data_dir: str, output_dir: str = "karnataka_bengaluru_master_plan_tiles"):
        """
        Initialize the tile generator.
        
        Args:
            data_dir: Directory containing GeoJSON files
            output_dir: Directory for output tiles
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Zoom level configuration - Same as Amaravati
        self.min_zoom = 17
        self.max_zoom = 18
        
        # Tile size
        self.tile_size = 256
        
        # Color mapping for Bangalore master plan zones
        self.zone_colors = {
            'Residential_Mixed_.json': '#FFC400',
            'Residential_Main_.json': '#FFEB4F',
            'Commercial_Central_.json': '#004DA8',
            'Commercial_Business_.json': '#73B2FF',
            'Industrial.json': '#AA66B2',
            'HighTech.json': '#C29ED7',
            'Public_SemiPublic.json': '#E60000',
            'Defense.json': '#E0B8FC',
            'StateForest_Valley_ProtectedLand_.json': '#70A800',
            'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json': '#98E600',
            'Lake_Tank.json': '#BEE8FF',
            'Road_Rail_Airport_Transport.json': '#828282',
            'Power_Water_GarbageFacility_TreatmentPlant.json': '#D79E9E',
            'Agricultural_Land.json': '#9DC1CB',
            'Unclassified_Use.json': '#E1E1E1',
            'Drains.json': '#267300'
        }
        
        # Zone categories for better organization
        self.zone_categories = {
            'RESIDENTIAL': ['Residential_Mixed_.json', 'Residential_Main_.json'],
            'COMMERCIAL': ['Commercial_Central_.json', 'Commercial_Business_.json'],
            'INDUSTRIAL': ['Industrial.json', 'HighTech.json'],
            'GOVERNMENT': ['Public_SemiPublic.json', 'Defense.json'],
            'PROTECTED': ['StateForest_Valley_ProtectedLand_.json'],
            'PARKS_GREEN': ['Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json'],
            'WATER_BODIES': ['Lake_Tank.json', 'Drains.json'],
            'TRANSPORT': ['Road_Rail_Airport_Transport.json'],
            'UTILITIES': ['Power_Water_GarbageFacility_TreatmentPlant.json'],
            'AGRICULTURAL': ['Agricultural_Land.json'],
            'UNCLASSIFIED': ['Unclassified_Use.json']
        }
        
        logger.info("Karnataka Bengaluru Master Plan Tile Generator initialized")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Zoom levels: {self.min_zoom} to {self.max_zoom}")

    def load_all_geojson_files(self) -> gpd.GeoDataFrame:
        """Load all GeoJSON files and combine them into a single GeoDataFrame."""
        logger.info(f"Loading GeoJSON files from {self.data_dir}")
        
        if not self.data_dir.exists():
            raise ValueError(f"Data directory does not exist: {self.data_dir}")
        
        # Find all JSON files in the directory
        json_files = list(self.data_dir.glob("*.json"))
        if not json_files:
            raise ValueError(f"No GeoJSON files found in {self.data_dir}")
        
        logger.info(f"Found {len(json_files)} GeoJSON files")
        
        all_gdfs = []
        zone_info = {}
        
        for json_file in json_files:
            try:
                logger.info(f"Loading {json_file.name}")
                
                # Load the GeoJSON file
                gdf = gpd.read_file(json_file)
                
                if gdf.empty:
                    logger.warning(f"No data in {json_file.name}")
                    continue
                
                # Add zone information
                zone_name = json_file.stem
                gdf['zone_name'] = zone_name
                gdf['zone_color'] = self.zone_colors.get(json_file.name, '#E1E1E1')
                
                # Determine category
                category = 'UNCLASSIFIED'
                for cat, zones in self.zone_categories.items():
                    if json_file.name in zones:
                        category = cat
                        break
                gdf['zone_category'] = category
                
                all_gdfs.append(gdf)
                zone_info[zone_name] = {
                    'file': json_file.name,
                    'color': gdf['zone_color'].iloc[0],
                    'category': category,
                    'count': len(gdf)
                }
                
                logger.info(f"  - {zone_name}: {len(gdf)} features, color: {gdf['zone_color'].iloc[0]}")
                
            except Exception as e:
                logger.error(f"Error loading {json_file.name}: {e}")
                continue
        
        if not all_gdfs:
            raise ValueError("No valid GeoJSON data loaded")
        
        # Combine all GeoDataFrames
        combined_gdf = gpd.pd.concat(all_gdfs, ignore_index=True)
        
        # Ensure consistent CRS
        if combined_gdf.crs is None:
            combined_gdf.set_crs('EPSG:4326', inplace=True)
        elif combined_gdf.crs != 'EPSG:4326':
            combined_gdf = combined_gdf.to_crs('EPSG:4326')
        
        logger.info(f"Combined dataset: {len(combined_gdf)} total features")
        logger.info(f"CRS: {combined_gdf.crs}")
        
        # Log zone summary
        self._log_zone_summary(zone_info)
        
        return combined_gdf

    def _log_zone_summary(self, zone_info: Dict):
        """Log a summary of loaded zones."""
        logger.info("=" * 60)
        logger.info("ZONE SUMMARY")
        logger.info("=" * 60)
        
        for category, zones in self.zone_categories.items():
            category_zones = [zone for zone in zones if zone in zone_info]
            if category_zones:
                logger.info(f"\n{category}:")
                for zone in category_zones:
                    info = zone_info[zone]
                    logger.info(f"  - {info['file']}: {info['count']} features, color: {info['color']}")
        
        logger.info("=" * 60)

    def get_tile_bounds(self, x: int, y: int, z: int) -> Tuple[float, float, float, float]:
        """Get the geographic bounds of a tile."""
        bounds = mercantile.bounds(x, y, z)
        return bounds.west, bounds.south, bounds.east, bounds.north

    def get_tiles_for_bounds(self, gdf: gpd.GeoDataFrame, zoom: int) -> List[mercantile.Tile]:
        """Get all tiles that intersect with the data bounds at given zoom level."""
        # Get bounds in WGS84 (data is already in WGS84)
        bounds_4326 = gdf.total_bounds
        min_x, min_y, max_x, max_y = bounds_4326
        
        # Add a buffer to ensure we capture tiles at low zoom levels
        # For low zoom levels, we need a larger buffer to ensure we get tiles
        if zoom <= 8:
            buffer = 0.1  # Larger buffer for low zoom levels
        else:
            buffer = 0.01  # Smaller buffer for higher zoom levels
        
        # Apply buffer to bounds
        buffered_min_x = max(-180, min_x - buffer)
        buffered_min_y = max(-85, min_y - buffer)
        buffered_max_x = min(180, max_x + buffer)
        buffered_max_y = min(85, max_y + buffer)
        
        # Get tiles for buffered bounds
        tiles = list(mercantile.tiles(buffered_min_x, buffered_min_y, buffered_max_x, buffered_max_y, [zoom]))
        
        # If no tiles found (shouldn't happen with buffer), try without buffer
        if not tiles:
            logger.warning(f"No tiles found with buffer for zoom {zoom}, trying without buffer")
            tiles = list(mercantile.tiles(min_x, min_y, max_x, max_y, [zoom]))
        
        logger.info(f"  Found {len(tiles)} tiles for zoom {zoom} (bounds: {buffered_min_x:.6f}, {buffered_min_y:.6f}, {buffered_max_x:.6f}, {buffered_max_y:.6f})")
        
        return tiles

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def generate_single_tile(self, gdf: gpd.GeoDataFrame, x: int, y: int, z: int) -> str:
        """Generate a single tile."""
        try:
            # Skip if tile already exists
            tile_path = self.output_dir / str(z) / str(x) / f"{y}.png"
            if tile_path.exists():
                return "skipped"
            
            # Get tile bounds
            west, south, east, north = self.get_tile_bounds(x, y, z)
            tile_bounds = box(west, south, east, north)
            
            # Find features that intersect with this tile
            intersecting_features = gdf[gdf.geometry.intersects(tile_bounds)]
            
            if intersecting_features.empty:
                return "no_content"  # No content for this tile
            
            # Create tile image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Render each feature
            for _, feature in intersecting_features.iterrows():
                self._render_feature(draw, feature, west, south, east, north)
            
            # Create directory if it doesn't exist
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save tile
            img.save(tile_path, 'PNG')
            return "generated"
            
        except Exception as e:
            logger.error(f"Error generating tile {z}/{x}/{y}: {e}")
            return "error"

    def _render_feature(self, draw: ImageDraw.Draw, feature: pd.Series, 
                       west: float, south: float, east: float, north: float):
        """Render a single feature on the tile."""
        try:
            geometry = feature.geometry
            color = self.hex_to_rgb(feature.zone_color)
            
            # Convert geometry to tile coordinates
            if geometry.geom_type == 'Polygon':
                self._render_polygon(draw, geometry, color, west, south, east, north)
            elif geometry.geom_type == 'MultiPolygon':
                for polygon in geometry.geoms:
                    self._render_polygon(draw, polygon, color, west, south, east, north)
            elif geometry.geom_type == 'LineString':
                self._render_linestring(draw, geometry, color, west, south, east, north)
            elif geometry.geom_type == 'MultiLineString':
                for line in geometry.geoms:
                    self._render_linestring(draw, line, color, west, south, east, north)
                    
        except Exception as e:
            logger.error(f"Error rendering feature: {e}")

    def _render_polygon(self, draw: ImageDraw.Draw, polygon, color: Tuple[int, int, int],
                       west: float, south: float, east: float, north: float):
        """Render a polygon on the tile."""
        try:
            # Get exterior coordinates
            exterior_coords = list(polygon.exterior.coords)
            
            # Convert to pixel coordinates
            pixel_coords = []
            for lon, lat in exterior_coords:
                x = int((lon - west) / (east - west) * self.tile_size)
                y = int((north - lat) / (north - south) * self.tile_size)
                pixel_coords.append((x, y))
            
            # Draw filled polygon
            if len(pixel_coords) >= 3:
                draw.polygon(pixel_coords, fill=color + (255,))
                
        except Exception as e:
            logger.error(f"Error rendering polygon: {e}")

    def _render_linestring(self, draw: ImageDraw.Draw, linestring, color: Tuple[int, int, int],
                          west: float, south: float, east: float, north: float):
        """Render a linestring on the tile."""
        try:
            coords = list(linestring.coords)
            
            # Convert to pixel coordinates
            pixel_coords = []
            for lon, lat in coords:
                x = int((lon - west) / (east - west) * self.tile_size)
                y = int((north - lat) / (north - south) * self.tile_size)
                pixel_coords.append((x, y))
            
            # Draw line
            if len(pixel_coords) >= 2:
                draw.line(pixel_coords, fill=color + (255,), width=2)
                
        except Exception as e:
            logger.error(f"Error rendering linestring: {e}")

    def generate_tiles_parallel(self, max_workers: int = 4):
        """Generate tiles using parallel processing."""
        logger.info("Starting parallel tile generation with {} workers".format(max_workers))
        
        # Load all GeoJSON data
        gdf = self.load_all_geojson_files()
        
        # Get overall bounds
        bounds = gdf.total_bounds
        logger.info(f"Overall bounds: {bounds}")
        
        # Calculate tile range for each zoom level
        total_tiles = 0
        skipped_tiles = 0
        
        for z in range(self.min_zoom, self.max_zoom + 1):
            logger.info(f"Processing zoom level {z}")
            
            # Log bounds for debugging
            bounds = gdf.total_bounds
            logger.info(f"  Data bounds: {bounds}")
            
            # Get all tiles that intersect with data
            tiles = self.get_tiles_for_bounds(gdf, z)
            logger.info(f"  Generating {len(tiles)} tiles for zoom {z}")
            
            if len(tiles) == 0:
                logger.warning(f"No tiles found for zoom {z} - this might indicate an issue with bounds calculation")
                continue
            
            # Process tiles in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_tile = {
                    executor.submit(self.generate_single_tile, gdf, tile.x, tile.y, tile.z): (tile.x, tile.y, tile.z)
                    for tile in tiles
                }
                
                for future in as_completed(future_to_tile):
                    x, y, z = future_to_tile[future]
                    try:
                        result = future.result()
                        if result == "generated":
                            total_tiles += 1
                        elif result == "skipped":
                            skipped_tiles += 1
                    except Exception as e:
                        logger.error(f"Tile {z}/{x}/{y} failed: {e}")
                        skipped_tiles += 1
                    
                    # Log progress every 100 tiles
                    if (total_tiles + skipped_tiles) % 100 == 0:
                        logger.info(f"  Processed {total_tiles + skipped_tiles} tiles (generated: {total_tiles}, skipped: {skipped_tiles})")
        
        logger.info(f"Tile generation completed: {total_tiles} new tiles generated, {skipped_tiles} tiles skipped")
        
        # Create supporting files
        self.create_supporting_files(bounds)

    def create_supporting_files(self, bounds: Tuple[float, float, float, float]):
        """Create supporting files for the tile set."""
        logger.info("Creating supporting files...")
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Karnataka - Bengaluru Master Plan",
            "description": "Master plan zones for Bengaluru, Karnataka",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/master_plan/{z}/{x}/{y}.png"
            ],
            "grids": [],
            "data": [],
            "minzoom": self.min_zoom,
            "maxzoom": self.max_zoom,
            "bounds": [
                bounds[0],  # west
                bounds[1],  # south
                bounds[2],  # east
                bounds[3]   # north
            ],
            "center": [
                (bounds[0] + bounds[2]) / 2,
                (bounds[1] + bounds[3]) / 2,
                10
            ]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Karnataka - Bengaluru Master Plan",
            "sources": {
                "karnataka-bengaluru-master-plan": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/master_plan/{z}/{x}/{y}.png"
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "karnataka-bengaluru-master-plan-layer",
                    "type": "raster",
                    "source": "karnataka-bengaluru-master-plan",
                    "paint": {
                        "raster-opacity": 0.8
                    }
                }
            ]
        }
        
        with open(self.output_dir / "style.json", "w") as f:
            json.dump(style_json, f, indent=2)
        
        # Create HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Karnataka - Bengaluru Master Plan</title>
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
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "karnataka-bengaluru-master-plan": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/master_plan/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "karnataka-bengaluru-master-plan-layer",
                        "type": "raster",
                        "source": "karnataka-bengaluru-master-plan",
                        "paint": {{
                            "raster-opacity": 0.8
                        }}
                    }}
                ]
            }},
            center: [{(bounds[0] + bounds[2]) / 2}, {(bounds[1] + bounds[3]) / 2}],
            zoom: 10
        }});
    </script>
</body>
</html>
"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("Created supporting files: tilejson.json, style.json, viewer.html")

    def validate_output(self):
        """Validate the generated tiles."""
        logger.info("Validating output...")
        
        total_tiles = 0
        for z in range(self.min_zoom, self.max_zoom + 1):
            zoom_dir = self.output_dir / str(z)
            if zoom_dir.exists():
                for x_dir in zoom_dir.iterdir():
                    if x_dir.is_dir():
                        total_tiles += len(list(x_dir.glob("*.png")))
        
        logger.info(f"Total tiles generated: {total_tiles}")
        
        # Log zone information
        logger.info("=" * 60)
        logger.info("ZONE COLORS USED")
        logger.info("=" * 60)
        for zone, color in self.zone_colors.items():
            logger.info(f"  - {zone}: {color}")
        logger.info("=" * 60)


def main():
    """Main execution function."""
    # Configuration for Karnataka Bengaluru
    DATA_DIR = "data/karnataka/bengaluru/master_plan"
    OUTPUT_DIR = "karnataka_bengaluru_master_plan_tiles"
    MAX_WORKERS = 4  # Number of parallel workers
    
    # Create tile generator
    generator = KarnatakaBengaluruMasterPlanTileGenerator(
        data_dir=DATA_DIR,
        output_dir=OUTPUT_DIR
    )
    
    try:
        # Generate tiles (use parallel processing for better performance)
        generator.generate_tiles_parallel(max_workers=MAX_WORKERS)
        
        # Validate output
        generator.validate_output()
        
        logger.info("\nTile generation completed successfully!")
        logger.info(f"Tiles saved to: {OUTPUT_DIR}")
        logger.info("\nTo view the tiles:")
        logger.info("1. Open: karnataka_bengaluru_master_plan_tiles/viewer.html")
        logger.info("2. Or use the tilejson.json with your mapping library")
        
    except Exception as e:
        logger.error(f"Error during tile generation: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()