#!/usr/bin/env python3
"""
Amaravati Master Plan Final Tile Generator
=========================================
Generates 256x256 PNG tiles with proper data coverage.
"""

import os
import sys
import json
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import geopandas as gpd
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import box, Point, Polygon, MultiPolygon
import numpy as np
from collections import defaultdict

warnings.filterwarnings('ignore')

class AmaravatiFinalTileGenerator:
    def __init__(self, master_plan_dir: str, output_dir: str = "amaravati_seamless_tiles"):
        self.master_plan_dir = Path(master_plan_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.zones = {}
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        print("="*70)
        print("🚀 AMARAVATI MASTER PLAN - FINAL TILE GENERATOR")
        print("="*70)
        
        # Load zoning mapping
        self.load_zoning_mapping()
        
        # Load all zones
        self.load_all_zones()
        self.calculate_bounds()
    
    def load_zoning_mapping(self):
        """Load the zoning mapping from JSON file"""
        mapping_file = Path("amaravati_zoning_mapping.json")
        if mapping_file.exists():
            with open(mapping_file, 'r') as f:
                mapping_data = json.load(f)
                self.zoning_mapping = mapping_data['zoning_mapping']
                print(f"✅ Loaded zoning mapping with {len(self.zoning_mapping)} zones")
        else:
            print("❌ Zoning mapping file not found. Using default mapping.")
            self.zoning_mapping = self.get_default_zoning_mapping()
    
    def get_default_zoning_mapping(self) -> Dict[str, Dict]:
        """Default zoning mapping as fallback"""
        return {
            "Burial Ground": {
                "fill_color": "#E39E00",
                "fill_pattern": "solid",
                "outline_color": "#000000",
                "outline_width": 1
            },
            "R1-Village planning zone": {
                "fill_color": "#FFFFFF",
                "fill_pattern": "solid",
                "outline_color": "#000000",
                "outline_width": 1
            }
        }
    
    def load_all_zones(self):
        """Load all GeoJSON files"""
        geojson_files = sorted(self.master_plan_dir.glob("*.geojson"))
        
        if not geojson_files:
            print(f"❌ No GeoJSON files found in {self.master_plan_dir}")
            sys.exit(1)
        
        print(f"\n📂 Loading {len(geojson_files)} zone files:")
        print("-" * 50)
        
        total_features = 0
        
        for file_path in geojson_files:
            try:
                # Read GeoJSON
                gdf = gpd.read_file(file_path)
                
                if gdf.empty:
                    print(f"  ⚠️  {file_path.name}: Empty file, skipping")
                    continue
                
                # Ensure CRS is EPSG:4326
                if gdf.crs is None:
                    gdf = gdf.set_crs('EPSG:4326', allow_override=True)
                elif gdf.crs.to_string() != 'EPSG:4326':
                    gdf = gdf.to_crs('EPSG:4326')
                
                # Store with exact filename
                zone_name = file_path.stem
                self.zones[zone_name] = gdf
                total_features += len(gdf)
                
                print(f"  ✅ {zone_name}: {len(gdf):,} features")
                
            except Exception as e:
                print(f"  ❌ Error loading {file_path.name}: {e}")
        
        print("-" * 50)
        print(f"✅ Loaded {len(self.zones)} zones with {total_features:,} total features")
    
    def calculate_bounds(self):
        """Calculate exact bounds from all data"""
        all_bounds = []
        for gdf in self.zones.values():
            if not gdf.empty:
                all_bounds.append(gdf.total_bounds)
        
        if not all_bounds:
            print("❌ No valid bounds found")
            sys.exit(1)
        
        self.bounds = [
            min(b[0] for b in all_bounds),  # minx
            min(b[1] for b in all_bounds),  # miny
            max(b[2] for b in all_bounds),  # maxx
            max(b[3] for b in all_bounds)   # maxy
        ]
        
        print(f"\n📍 Geographic bounds:")
        print(f"   West: {self.bounds[0]:.6f}")
        print(f"   South: {self.bounds[1]:.6f}")
        print(f"   East: {self.bounds[2]:.6f}")
        print(f"   North: {self.bounds[3]:.6f}")
    
    def get_zone_style(self, zone_name: str) -> Dict[str, Any]:
        """Get style configuration for a zone"""
        # Try exact match first
        if zone_name in self.zoning_mapping:
            return self.zoning_mapping[zone_name]
        
        # Default style for unmapped zones
        return {
            "fill_color": "#FF0000",  # Red for unmapped
            "fill_pattern": "solid",
            "outline_color": "#000000",
            "outline_width": 1
        }
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def render_tile(self, x: int, y: int, z: int) -> Image.Image:
        """Render a single tile"""
        # Create canvas
        canvas = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        
        # Get tile bounds
        tile_bounds = mercantile.bounds(x, y, z)
        
        # Convert to pixel coordinates
        def coord_to_pixel(lon, lat):
            # Simple linear interpolation within tile bounds
            tile_x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * self.tile_size
            tile_y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * self.tile_size
            return tile_x, tile_y
        
        # Render each zone
        for zone_name, gdf in self.zones.items():
            if gdf.empty:
                continue
            
            # Get style for this zone
            style = self.get_zone_style(zone_name)
            fill_color = self.hex_to_rgb(style['fill_color'])
            outline_color = self.hex_to_rgb(style.get('outline_color', '#000000'))
            outline_width = style.get('outline_width', 1)
            
            # Filter geometries that intersect with tile
            tile_geom = box(tile_bounds.west, tile_bounds.south, tile_bounds.east, tile_bounds.north)
            intersecting = gdf[gdf.geometry.intersects(tile_geom)]
            
            for idx, row in intersecting.iterrows():
                geom = row.geometry
                
                # Convert geometry to pixel coordinates
                if geom.geom_type == 'Polygon':
                    coords = []
                    for coord in geom.exterior.coords:
                        if len(coord) >= 2:
                            lon, lat = coord[0], coord[1]
                            px, py = coord_to_pixel(lon, lat)
                            coords.append((px, py))
                    
                    if len(coords) > 2:
                        # Fill only - no borders between features
                        draw.polygon(coords, fill=fill_color)
                
                elif geom.geom_type == 'MultiPolygon':
                    for poly in geom.geoms:
                        coords = []
                        for coord in poly.exterior.coords:
                            if len(coord) >= 2:
                                lon, lat = coord[0], coord[1]
                                px, py = coord_to_pixel(lon, lat)
                                coords.append((px, py))
                        
                        if len(coords) > 2:
                            # Fill only - no borders between features
                            draw.polygon(coords, fill=fill_color)
        
        return canvas
    
    def generate_tiles(self, min_zoom: int = 5, max_zoom: int = 18):
        """Generate tiles for all zoom levels"""
        print(f"\n🎨 Generating tiles for zoom levels {min_zoom}-{max_zoom}")
        print("-" * 50)
        
        total_tiles = 0
        
        for z in range(min_zoom, max_zoom + 1):
            print(f"\n🔍 Processing zoom level {z}...")
            
            # Get tiles that intersect with our bounds
            tiles = list(mercantile.tiles(self.bounds[0], self.bounds[1], 
                                        self.bounds[2], self.bounds[3], z))
            
            print(f"   📊 {len(tiles)} tiles to generate")
            
            zoom_dir = self.output_dir / str(z)
            zoom_dir.mkdir(exist_ok=True)
            
            tiles_with_content = 0
            
            for i, tile in enumerate(tiles):
                # Create x directory
                x_dir = zoom_dir / str(tile.x)
                x_dir.mkdir(exist_ok=True)
                
                # Create tile path as z/x/y.png
                tile_path = x_dir / f"{tile.y}.png"
                
                # Skip if tile already exists
                if tile_path.exists():
                    continue
                
                try:
                    # Render tile
                    tile_image = self.render_tile(tile.x, tile.y, tile.z)
                    
                    # Check if tile has content
                    if tile_image.mode == 'RGBA':
                        alpha = np.array(tile_image)[:, :, 3]
                        non_transparent = np.sum(alpha > 0)
                        if non_transparent > 0:
                            tiles_with_content += 1
                    
                    # Save tile
                    tile_image.save(tile_path, 'PNG')
                    total_tiles += 1
                    
                    if (i + 1) % 50 == 0:
                        print(f"   ✅ Generated {i + 1}/{len(tiles)} tiles ({tiles_with_content} with content)")
                
                except Exception as e:
                    print(f"   ❌ Error generating tile {tile.x}/{tile.y}/{tile.z}: {e}")
            
            print(f"   ✅ Completed zoom level {z} - {tiles_with_content} tiles with content")
        
        print(f"\n🎉 Generated {total_tiles} tiles total")
    
    def create_tilejson(self):
        """Create TileJSON specification file"""
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Amaravati Master Plan",
            "description": "Amaravati Master Plan Zoning Tiles",
            "version": "1.0.0",
            "attribution": "Amaravati Development Authority",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [f"/{{z}}/{{x}}/{{y}}.png"],
            "grids": [],
            "data": [],
            "minzoom": 5,
            "maxzoom": 18,
            "bounds": self.bounds,
            "center": [
                (self.bounds[0] + self.bounds[2]) / 2,
                (self.bounds[1] + self.bounds[3]) / 2,
                10
            ]
        }
        
        tilejson_path = self.output_dir / "tilejson.json"
        with open(tilejson_path, 'w') as f:
            json.dump(tilejson, f, indent=2)
        
        print(f"📋 TileJSON created at {tilejson_path}")

def main():
    """Main execution function"""
    # Configuration
    master_plan_dir = "data/andhra_pradesh/amaravati/msater_plan"
    output_dir = "amaravati_seamless_tiles"
    
    # Check if data directory exists
    if not Path(master_plan_dir).exists():
        print(f"❌ Data directory not found: {master_plan_dir}")
        print("Please ensure the data directory exists and contains GeoJSON files.")
        sys.exit(1)
    
    # Create generator
    generator = AmaravatiFinalTileGenerator(master_plan_dir, output_dir)
    
    # Generate tiles
    generator.generate_tiles(min_zoom=5, max_zoom=18)
    
    # Create TileJSON
    generator.create_tilejson()
    
    print("\n" + "="*70)
    print("🎉 AMARAVATI MASTER PLAN TILE GENERATION COMPLETE!")
    print("="*70)
    print(f"📁 Output directory: {output_dir}")
    print(f"📋 TileJSON: {output_dir}/tilejson.json")
    print("="*70)

if __name__ == "__main__":
    main()
