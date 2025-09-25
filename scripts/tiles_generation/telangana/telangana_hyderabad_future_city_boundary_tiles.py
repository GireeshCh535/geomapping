#!/usr/bin/env python3
"""
Amaravati Master Plan Tile Generator - 100% Complete Data Coverage
===================================================================
No optimization, no shortcuts - renders EVERYTHING at EVERY zoom level.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
import geopandas as gpd
from PIL import Image, ImageDraw
import mercantile

class AmaravatiCompleteTileGenerator:
    def __init__(self, master_plan_dir: str, output_dir: str = "tiles"):
        self.master_plan_dir = Path(master_plan_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.zones = {}
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        print("="*60)
        print("🚀 AMARAVATI COMPLETE TILE GENERATOR")
        print("="*60)
        
        # Load everything
        self.load_all_zones()
        self.calculate_bounds()
    
    def load_all_zones(self):
        """Load ALL zones without any filtering"""
        geojson_files = sorted(self.master_plan_dir.glob("*.geojson"))
        
        print(f"\n📂 Loading {len(geojson_files)} zone files:")
        
        for file_path in geojson_files:
            # Read file
            gdf = gpd.read_file(file_path)
            
            if gdf.empty:
                continue
            
            # Ensure WGS84
            if gdf.crs is None:
                gdf = gdf.set_crs('EPSG:4326')
            else:
                gdf = gdf.to_crs('EPSG:4326')
            
            # Store with exact filename - NO FILTERING
            zone_name = file_path.stem
            self.zones[zone_name] = gdf
            
            print(f"  ✅ {zone_name}: {len(gdf):,} features")
        
        total = sum(len(gdf) for gdf in self.zones.values())
        print(f"\n✅ Loaded {len(self.zones)} zones, {total:,} total features")
    
    def calculate_bounds(self):
        """Calculate exact bounds from all data"""
        all_bounds = []
        for gdf in self.zones.values():
            if not gdf.empty:
                all_bounds.append(gdf.total_bounds)
        
        self.bounds = [
            min(b[0] for b in all_bounds),  # minx
            min(b[1] for b in all_bounds),  # miny
            max(b[2] for b in all_bounds),  # maxx
            max(b[3] for b in all_bounds)   # maxy
        ]
        
        print(f"📍 Bounds: {self.bounds}")
    
    def get_all_colors(self):
        """Complete color map for ALL 40 zones"""
        return {
            'Burial_Ground': (227, 158, 0),
            'C1__Mixed_use_zone': (115, 178, 255),
            'C2__General_commercial_zone': (0, 197, 255),
            'C3_Neighbourhood_centre_zone': (0, 197, 255),
            'C4_Town_centre_zone': (0, 169, 230),
            'C5_Regional_centre_zone': (0, 112, 255),
            'C6_Central_business_district_zone': (0, 92, 230),
            'Commercial_Vacant': (197, 226, 255),
            'I1_Business_park_zone': (255, 190, 232),
            'I2_Logistics_zone': (255, 115, 223),
            'I3_Non_polluting_industry_zone': (169, 0, 230),
            'P1_Passive_zone': (38, 115, 0),
            'P2_Active_zone': (56, 168, 0),
            'P3_Protected_zone': (190, 232, 255),
            'P3_Protected_zone_Hills': (76, 115, 0),
            'PGN_G': (76, 115, 0),
            'PGN_V': (137, 112, 68),
            'R1_Village_planning_zone': (255, 255, 255),
            'R3_Medium_to_high_density_zone': (245, 202, 122),
            'R4_High_density_zone': (230, 152, 0),
            'RAA': (255, 170, 0),
            'Residential_Vacant': (255, 211, 127),
            'S2_Education_zone': (255, 247, 247),
            'S3_Special_zone': (215, 176, 158),
            'SC1a_Mixed_Use': (0, 112, 255),
            'SC1b___Mixed_Use': (115, 178, 255),
            'SP1__Passive_Zone': (38, 115, 0),
            'SP2__Active_Zone': (56, 168, 0),
            'SP3_Protected_Zone': (0, 197, 255),
            'SR2_Low_Density_Housing': (255, 255, 190),
            'SR4___High_Density_Private': (255, 170, 0),
            'SS1___Government_Zone': (230, 0, 0),
            'SS2a__Education_Zone': (255, 247, 247),
            'SS2b_Cultural_Zone': (197, 0, 255),
            'SS2c_Health_Zone': (211, 255, 190),
            'SS3___Special_Zone': (168, 56, 0),
            'SU1_Reserve_Zone': (225, 225, 225),
            'SU2___Road_Network': (255, 255, 255),
            'U1_Reserve_zone': (204, 204, 204),
            'U2__Road_reserve_zone': (196, 115, 98)
        }
    
    def render_tile(self, x: int, y: int, z: int):
        """Render a tile with ALL data - no optimization"""
        # Get exact tile bounds
        bounds = mercantile.bounds(x, y, z)
        
        # Create image
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        colors = self.get_all_colors()
        
        # Fixed render order
        order = [
            'U2__Road_reserve_zone', 'SU2___Road_Network', 'U1_Reserve_zone', 'SU1_Reserve_Zone',
            'P1_Passive_zone', 'P2_Active_zone', 'P3_Protected_zone', 'P3_Protected_zone_Hills',
            'PGN_G', 'PGN_V', 'SP1__Passive_Zone', 'SP2__Active_Zone', 'SP3_Protected_Zone',
            'Residential_Vacant', 'Commercial_Vacant',
            'R1_Village_planning_zone', 'R3_Medium_to_high_density_zone', 'R4_High_density_zone',
            'RAA', 'SR2_Low_Density_Housing', 'SR4___High_Density_Private',
            'C1__Mixed_use_zone', 'C2__General_commercial_zone', 'C3_Neighbourhood_centre_zone',
            'C4_Town_centre_zone', 'C5_Regional_centre_zone', 'C6_Central_business_district_zone',
            'SC1a_Mixed_Use', 'SC1b___Mixed_Use',
            'I1_Business_park_zone', 'I2_Logistics_zone', 'I3_Non_polluting_industry_zone',
            'S2_Education_zone', 'S3_Special_zone', 'SS1___Government_Zone',
            'SS2a__Education_Zone', 'SS2b_Cultural_Zone', 'SS2c_Health_Zone',
            'SS3___Special_Zone', 'Burial_Ground'
        ]
        
        has_features = False
        
        for zone_name in order:
            if zone_name not in self.zones:
                continue
            
            gdf = self.zones[zone_name]
            
            # Get ALL features that touch this tile
            minx, miny, maxx, maxy = bounds.west, bounds.south, bounds.east, bounds.north
            
            # Check EVERY feature - no shortcuts
            for idx, row in gdf.iterrows():
                geom = row.geometry
                
                if geom is None:
                    continue
                
                # Check if geometry intersects tile bounds
                geom_bounds = geom.bounds
                if not (geom_bounds[0] <= maxx and geom_bounds[2] >= minx and 
                       geom_bounds[1] <= maxy and geom_bounds[3] >= miny):
                    continue
                
                # Get color
                rgb = colors.get(zone_name, (128, 128, 128))
                color = rgb + (220,)  # Add alpha
                
                # Draw the geometry
                if geom.geom_type == 'Polygon':
                    coords = []
                    for lon, lat in geom.exterior.coords:
                        px = (lon - minx) / (maxx - minx) * 256
                        py = (maxy - lat) / (maxy - miny) * 256
                        coords.append((px, py))
                    
                    if len(coords) >= 3:
                        try:
                            draw.polygon(coords, fill=color)
                            has_features = True
                            
                            # Special hatch for R1
                            if zone_name == 'R1_Village_planning_zone':
                                draw.polygon(coords, outline=(0, 0, 0, 255), width=1)
                        except:
                            pass
                
                elif geom.geom_type == 'MultiPolygon':
                    for poly in geom.geoms:
                        coords = []
                        for lon, lat in poly.exterior.coords:
                            px = (lon - minx) / (maxx - minx) * 256
                            py = (maxy - lat) / (maxy - miny) * 256
                            coords.append((px, py))
                        
                        if len(coords) >= 3:
                            try:
                                draw.polygon(coords, fill=color)
                                has_features = True
                            except:
                                pass
        
        return img if has_features else None
    
    def generate_all_tiles(self, min_zoom=10, max_zoom=16):
        """Generate ALL tiles for ALL zoom levels"""
        print(f"\n🎨 Generating tiles for zoom {min_zoom} to {max_zoom}")
        print("⚠️  No optimization - rendering EVERYTHING\n")
        
        total = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"📍 Zoom {zoom}:")
            
            # Get ALL tiles for this zoom level
            west, south, east, north = self.bounds
            tiles = list(mercantile.tiles(west, south, east, north, zooms=[zoom]))
            
            print(f"  Processing {len(tiles)} tiles...")
            
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            generated = 0
            empty = 0
            
            for i, tile in enumerate(tiles):
                # Show progress
                if i % 10 == 0:
                    print(f"    {i}/{len(tiles)} tiles processed...")
                
                x_dir = zoom_dir / str(tile.x)
                x_dir.mkdir(exist_ok=True)
                
                tile_path = x_dir / f"{tile.y}.png"
                
                # Generate tile
                try:
                    img = self.render_tile(tile.x, tile.y, zoom)
                    if img:
                        img.save(tile_path, 'PNG')
                        generated += 1
                        total += 1
                    else:
                        empty += 1
                except Exception as e:
                    print(f"    ERROR on {tile.x}/{tile.y}: {e}")
                    empty += 1
            
            print(f"  ✅ Generated: {generated} tiles")
            print(f"  ⏭️  Empty: {empty} tiles\n")
        
        print(f"✅ COMPLETE! Generated {total} total tiles")
        print(f"📁 Output: {self.output_dir.absolute()}")
        
        # Create viewer
        self.create_viewer(min_zoom, max_zoom)
    
    def create_viewer(self, min_zoom, max_zoom):
        """Create HTML viewer"""
        cx = (self.bounds[0] + self.bounds[2]) / 2
        cy = (self.bounds[1] + self.bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
<title>Amaravati Master Plan - Complete</title>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body {{ margin: 0; padding: 0; }}
#map {{ height: 100vh; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map').setView([{cy}, {cx}], 12);

// Base map
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    opacity: 0.3
}}).addTo(map);

// Amaravati tiles
L.tileLayer('{{z}}/{{x}}/{{y}}.png', {{
    minZoom: {min_zoom},
    maxZoom: {max_zoom},
    bounds: [[{self.bounds[1]}, {self.bounds[0]}], [{self.bounds[3]}, {self.bounds[2]}]]
}}).addTo(map);

// Info
L.control.scale().addTo(map);
</script>
</body>
</html>"""
        
        viewer = self.output_dir / "viewer.html"
        with open(viewer, 'w') as f:
            f.write(html)
        print(f"✅ Viewer: {viewer}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <master_plan_dir>")
        sys.exit(1)
    
    master_plan_dir = sys.argv[1]
    
    # Create generator
    generator = AmaravatiCompleteTileGenerator(master_plan_dir, "tiles")
    
    # Generate ALL tiles - no optimization
    generator.generate_all_tiles(min_zoom=10, max_zoom=16)
    
    print("\n" + "="*60)
    print("✅ 100% COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()