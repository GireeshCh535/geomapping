#!/usr/bin/env python3
"""
Warangal Master Plan - Perfect Tile Generator
==============================================

Generates high-quality map tiles from Warangal master plan GeoJSON data
with exact color specifications and seamless rendering.

Features:
- 22 land use zones with precise colors
- Hatched patterns for Air Strip, Heritage, and Public Utilities
- Anti-aliased rendering for smooth edges
- Spatial indexing for fast performance
- Web Mercator tile system (EPSG:3857)
- Interactive HTML viewer

Usage:
    python3 warangal_perfect_tile_generator.py [data_directory] [output_directory] [min_zoom] [max_zoom]

Examples:
    # Default (all parameters auto-detected)
    python3 warangal_perfect_tile_generator.py

    # Custom data directory
    python3 warangal_perfect_tile_generator.py data/Telangana/warangal/master_plan

    # Custom output directory
    python3 warangal_perfect_tile_generator.py data/Telangana/warangal/master_plan tiles_output

    # Custom zoom range (e.g., 10-16 for testing)
    python3 warangal_perfect_tile_generator.py data/Telangana/warangal/master_plan tiles_output 10 16

Author: Geo Mapping System
Date: October 2025
Version: 2.0
"""

import os
import sys
import json
import warnings
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import geopandas as gpd
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import box
import numpy as np

warnings.filterwarnings('ignore')


class WarangalTileGenerator:
    """
    Generates map tiles from Warangal master plan GeoJSON data.
    
    Attributes:
        master_plan_dir: Directory containing GeoJSON files
        output_dir: Directory for generated tiles
        tile_size: Size of each tile in pixels (default: 256)
        zones: Dictionary of loaded GeoJSON data by zone name
        bounds: Geographic bounds [west, south, east, north]
    """
    
    def __init__(self, 
                 master_plan_dir: str = "data/Telangana/warangal/master_plan",
                 output_dir: str = "warangal_tiles",
                 tile_size: int = 256):
        """
        Initialize the tile generator.
        
        Args:
            master_plan_dir: Path to directory containing GeoJSON files
            output_dir: Path to output directory for tiles
            tile_size: Size of tiles in pixels (default: 256)
        """
        self.master_plan_dir = Path(master_plan_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = tile_size
        self.zones = {}
        self.bounds = None
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Print header
        self._print_header()
        
        # Load and validate data
        self._load_zones()
        self._calculate_bounds()
        self._verify_colors()
    
    def _print_header(self):
        """Print script header"""
        print("=" * 80)
        print("🗺️  WARANGAL MASTER PLAN - PERFECT TILE GENERATOR")
        print("=" * 80)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Data Directory: {self.master_plan_dir.absolute()}")
        print(f"Output Directory: {self.output_dir.absolute()}")
        print("=" * 80)
    
    def _load_zones(self):
        """Load all GeoJSON files with proper CRS handling"""
        geojson_files = sorted(self.master_plan_dir.glob("*.geojson"))
        
        if not geojson_files:
            print(f"\n❌ ERROR: No GeoJSON files found in {self.master_plan_dir}")
            print("Please check the directory path and try again.")
            sys.exit(1)
        
        print(f"\n📂 LOADING DATA")
        print("-" * 80)
        print(f"Found {len(geojson_files)} GeoJSON files\n")
        
        total_features = 0
        
        for file_path in geojson_files:
            try:
                # Read GeoJSON
                gdf = gpd.read_file(file_path)
                
                if gdf.empty:
                    print(f"  ⚠️  {file_path.name}: Empty file, skipping")
                    continue
                
                # Fix CRS if missing or incorrect
                if gdf.crs is None:
                    gdf = gdf.set_crs('EPSG:4326', allow_override=True)
                elif gdf.crs.to_string() != 'EPSG:4326':
                    gdf = gdf.to_crs('EPSG:4326')
                
                # Clean geometries (fix self-intersections and invalid geometries)
                gdf['geometry'] = gdf['geometry'].buffer(0)
                gdf = gdf[gdf['geometry'].is_valid]
                gdf = gdf[~gdf['geometry'].is_empty]
                
                # Store with exact filename
                zone_name = file_path.stem
                self.zones[zone_name] = gdf
                total_features += len(gdf)
                
                # Status indicator based on feature count
                if len(gdf) > 10000:
                    status = "🔴 VERY HIGH"
                elif len(gdf) > 1000:
                    status = "🟡 HIGH"
                elif len(gdf) > 100:
                    status = "🟢 MEDIUM"
                else:
                    status = "⚪ LOW"
                
                print(f"  {status:12s} {zone_name:30s} {len(gdf):>8,} features")
                
            except Exception as e:
                print(f"  ❌ Error loading {file_path.name}: {e}")
        
        print("-" * 80)
        print(f"✅ Loaded {len(self.zones)} zones with {total_features:,} total features\n")
    
    def _calculate_bounds(self):
        """Calculate exact bounds from all data"""
        all_bounds = []
        
        for zone_name, gdf in self.zones.items():
            if not gdf.empty:
                all_bounds.append(gdf.total_bounds)
        
        if not all_bounds:
            print("❌ ERROR: No valid bounds found in data")
            sys.exit(1)
        
        self.bounds = [
            min(b[0] for b in all_bounds),  # west (minx)
            min(b[1] for b in all_bounds),  # south (miny)
            max(b[2] for b in all_bounds),  # east (maxx)
            max(b[3] for b in all_bounds)   # north (maxy)
        ]
        
        # Calculate center
        center_lon = (self.bounds[0] + self.bounds[2]) / 2
        center_lat = (self.bounds[1] + self.bounds[3]) / 2
        
        print("🌍 GEOGRAPHIC EXTENT")
        print("-" * 80)
        print(f"West:   {self.bounds[0]:.6f}°E")
        print(f"South:  {self.bounds[1]:.6f}°N")
        print(f"East:   {self.bounds[2]:.6f}°E")
        print(f"North:  {self.bounds[3]:.6f}°N")
        print(f"Center: {center_lat:.6f}°N, {center_lon:.6f}°E")
        print()
    
    def get_color_specifications(self) -> Dict[str, Dict]:
        """
        Get exact color specifications for all 22 Warangal zones.
        
        Returns:
            Dictionary mapping zone names to color/pattern specifications
            
        Color Format:
            - 'fill': RGB tuple (red, green, blue) 0-255
            - 'stroke': RGB tuple for hatching lines, or None
            - 'stroke_width': Line width in pixels
            - 'pattern': 'SOLID' or 'HATCH'
            
        Hatched Patterns:
            - Air Strip: White background (FFFFFF) with pink hatching (FF00C5)
            - Heritage: Orange background (FFA77F) with brown hatching (732600)
            - Public Utilities: Orange background (E69800) with red hatching (FF0000)
        """
        return {
            'Agriculture': {
                'fill': (0xD3, 0xFF, 0xBE),  # #D3FFBE
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'AirStrip': {
                'fill': (0xFF, 0xFF, 0xFF),  # #FFFFFF (white background)
                'stroke': (0xFF, 0x00, 0xC5),  # #FF00C5 (pink hatching)
                'stroke_width': 1,
                'pattern': 'HATCH'
            },
            
            'Commercial': {
                'fill': (0x00, 0x70, 0xFF),  # #0070FF
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Forest': {
                'fill': (0x26, 0x73, 0x00),  # #267300
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'GrowthCorridor': {
                'fill': (0xFF, 0xBE, 0xE8),  # #FFBEE8
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'GrowthCorridor2': {
                'fill': (0xFF, 0x73, 0xDF),  # #FF73DF
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Heritage': {
                'fill': (0xFF, 0xA7, 0x7F),  # #FFA77F (orange background)
                'stroke': (0x73, 0x26, 0x00),  # #732600 (brown hatching)
                'stroke_width': 1,
                'pattern': 'HATCH'
            },
            
            'HillBuffer': {
                'fill': (0x55, 0xFF, 0x00),  # #55FF00
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Hillocks': {
                'fill': (0xA8, 0x70, 0x00),  # #A87000
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Industrial': {
                'fill': (0xC5, 0x00, 0xFF),  # #C500FF
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'MixedUse': {
                'fill': (0xFF, 0xAA, 0x00),  # #FFAA00
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Public_and_SemiPublic': {
                'fill': (0xFF, 0x00, 0x00),  # #FF0000
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'PublicUtilities': {
                'fill': (0xE6, 0x98, 0x00),  # #E69800 (orange background)
                'stroke': (0xFF, 0x00, 0x00),  # #FF0000 (red hatching)
                'stroke_width': 1,
                'pattern': 'HATCH'
            },
            
            'RailwayLand': {
                'fill': (0xCC, 0xCC, 0xCC),  # #CCCCCC
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Recreational': {
                'fill': (0x55, 0xFF, 0x00),  # #55FF00
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Residential': {
                'fill': (0xFF, 0xFF, 0x00),  # #FFFF00
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'ResidentialExpansion': {
                'fill': (0x9C, 0x9C, 0x9C),  # #9C9C9C
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'RoadBuffer': {
                'fill': (0x4E, 0x4E, 0x4E),  # #4E4E4E
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Transportation': {
                'fill': (0xB2, 0xB2, 0xB2),  # #B2B2B2
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'Water_Bodies': {
                'fill': (0x00, 0xC5, 0xFF),  # #00C5FF
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'WaterBodyBuffer': {
                'fill': (0x55, 0xFF, 0x00),  # #55FF00
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            },
            
            'ZoologicalPark': {
                'fill': (0x38, 0xA8, 0x00),  # #38A800
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            }
        }
    
    def get_rendering_order(self) -> List[str]:
        """
        Define proper rendering order (bottom to top layers).
        
        Returns:
            List of zone names in rendering order (bottom layer first)
        """
        return [
            # Infrastructure base (bottom)
            'RoadBuffer',
            'Transportation',
            'RailwayLand',
            
            # Water features
            'Water_Bodies',
            'WaterBodyBuffer',
            
            # Natural features
            'Forest',
            'Hillocks',
            'HillBuffer',
            
            # Parks and recreational
            'Recreational',
            'ZoologicalPark',
            
            # Expansion areas
            'ResidentialExpansion',
            
            # Residential
            'Residential',
            
            # Commercial and mixed
            'Commercial',
            'MixedUse',
            
            # Industrial
            'Industrial',
            
            # Growth corridors
            'GrowthCorridor',
            'GrowthCorridor2',
            
            # Public facilities
            'Public_and_SemiPublic',
            'PublicUtilities',
            
            # Agriculture
            'Agriculture',
            
            # Special zones (top)
            'Heritage',
            'AirStrip'
        ]
    
    def _verify_colors(self):
        """Verify that all zones have color assignments"""
        print("🎨 COLOR VERIFICATION")
        print("-" * 80)
        
        color_map = self.get_color_specifications()
        missing = []
        
        for zone_name in sorted(self.zones.keys()):
            if zone_name in color_map:
                style = color_map[zone_name]
                rgb = style['fill']
                hex_color = '#{:02X}{:02X}{:02X}'.format(rgb[0], rgb[1], rgb[2])
                pattern = f" ({style['pattern']})" if style['pattern'] == 'HATCH' else ""
                print(f"  ✅ {zone_name:30s} {hex_color}{pattern}")
            else:
                missing.append(zone_name)
                print(f"  ❌ {zone_name:30s} NO COLOR DEFINED")
        
        if missing:
            print(f"\n⚠️  WARNING: {len(missing)} zones without color definitions!")
            print("These zones will use default gray color.")
        else:
            print(f"\n✅ All {len(self.zones)} zones have proper color assignments!")
        
        print()
    
    def _draw_hatch_pattern(self, img: Image.Image, coords: List[Tuple], 
                           stroke_color: Tuple, zoom: int, spacing: int = None):
        """
        Draw diagonal hatch pattern clipped to polygon.
        
        Args:
            img: Image to draw on
            coords: Polygon coordinates in pixels
            stroke_color: RGB tuple for hatch lines
            zoom: Current zoom level (affects spacing)
            spacing: Base spacing between lines (auto-calculated if None)
        """
        if len(coords) < 3:
            return
        
        # Zoom-aware spacing - tighter spacing at higher zooms
        if spacing is None:
            base_spacing = 8
            spacing = max(2, int(base_spacing / (2 ** max(0, (zoom - 10)))))
        
        # Create mask for the polygon
        mask = Image.new('L', img.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(coords, fill=255)
        
        # Create hatch pattern image
        hatch_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
        hatch_draw = ImageDraw.Draw(hatch_img)
        
        # Get bounding box
        x_coords = [c[0] for c in coords]
        y_coords = [c[1] for c in coords]
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        # Add padding
        padding = spacing * 3
        min_x = max(0, min_x - padding)
        max_x = min(img.size[0], max_x + padding)
        min_y = max(0, min_y - padding)
        max_y = min(img.size[1], max_y + padding)
        
        # Calculate diagonal distance
        diag_length = int(((max_x - min_x) ** 2 + (max_y - min_y) ** 2) ** 0.5)
        
        # Draw diagonal lines at 45 degrees
        for i in range(-diag_length, diag_length + spacing, spacing):
            x1 = min_x + i
            y1 = min_y
            x2 = min_x + i + (max_y - min_y)
            y2 = max_y
            
            # Only draw if line intersects bounding box
            if x2 >= min_x and x1 <= max_x:
                x1 = max(min_x, min(x1, max_x))
                y1 = max(min_y, min(y1, max_y))
                x2 = max(min_x, min(x2, max_x))
                y2 = max(min_y, min(y2, max_y))
                
                # Draw with full opacity
                hatch_draw.line([(x1, y1), (x2, y2)], 
                              fill=stroke_color + (255,), width=1)
        
        # Apply mask to clip hatch to polygon
        hatch_img.putalpha(mask)
        
        # Composite onto main image
        img.paste(hatch_img, (0, 0), hatch_img)
    
    def _geom_to_pixels(self, coords, bounds, scale_factor: int = 1) -> List[Tuple[float, float]]:
        """
        Convert geographic coordinates to pixel coordinates.
        
        Args:
            coords: List of (lon, lat) tuples
            bounds: Tile bounds (mercantile bounds object)
            scale_factor: Multiplier for resolution (1 = 256px, 2 = 512px)
            
        Returns:
            List of (x, y) pixel coordinates
        """
        pixels = []
        tile_size = self.tile_size * scale_factor
        
        for lon, lat in coords:
            # Convert to pixels with high precision
            px = (lon - bounds.west) / (bounds.east - bounds.west) * tile_size
            py = (bounds.north - lat) / (bounds.north - bounds.south) * tile_size
            pixels.append((px, py))
        
        return pixels
    
    def render_tile(self, x: int, y: int, z: int) -> Optional[Image.Image]:
        """
        Render a single tile with all zones.
        
        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Zoom level
            
        Returns:
            PIL Image object or None if tile is empty
        """
        # Get tile bounds
        bounds = mercantile.bounds(x, y, z)
        tile_box = box(bounds.west, bounds.south, bounds.east, bounds.north)
        
        # Create high-resolution image for anti-aliasing (2x)
        scale_factor = 2
        img_size = self.tile_size * scale_factor
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Get specifications
        color_map = self.get_color_specifications()
        render_order = self.get_rendering_order()
        
        has_features = False
        
        # Render each zone in order
        for zone_name in render_order:
            if zone_name not in self.zones:
                continue
            
            gdf = self.zones[zone_name]
            
            # Get style
            style = color_map.get(zone_name, {
                'fill': (128, 128, 128),
                'stroke': None,
                'stroke_width': 0,
                'pattern': 'SOLID'
            })
            
            try:
                # Spatial query - use spatial index for efficiency
                possible_matches_index = list(gdf.sindex.intersection(tile_box.bounds))
                if not possible_matches_index:
                    continue
                
                possible_matches = gdf.iloc[possible_matches_index]
                precise_matches = possible_matches[possible_matches.intersects(tile_box)]
                
                if precise_matches.empty:
                    continue
                
                # Draw each feature
                for idx, row in precise_matches.iterrows():
                    geom = row.geometry
                    
                    if geom is None or geom.is_empty:
                        continue
                    
                    # Handle Polygon
                    if geom.geom_type == 'Polygon':
                        coords = self._geom_to_pixels(geom.exterior.coords, bounds, scale_factor)
                        if len(coords) >= 3:
                            self._draw_polygon(img, draw, coords, style, z, scale_factor)
                            has_features = True
                            
                            # Draw holes
                            for interior in geom.interiors:
                                hole_coords = self._geom_to_pixels(interior.coords, bounds, scale_factor)
                                if len(hole_coords) >= 3:
                                    draw.polygon(hole_coords, fill=(0, 0, 0, 0))
                    
                    # Handle MultiPolygon
                    elif geom.geom_type == 'MultiPolygon':
                        for poly in geom.geoms:
                            coords = self._geom_to_pixels(poly.exterior.coords, bounds, scale_factor)
                            if len(coords) >= 3:
                                self._draw_polygon(img, draw, coords, style, z, scale_factor)
                                has_features = True
                                
                                # Draw holes
                                for interior in poly.interiors:
                                    hole_coords = self._geom_to_pixels(interior.coords, bounds, scale_factor)
                                    if len(hole_coords) >= 3:
                                        draw.polygon(hole_coords, fill=(0, 0, 0, 0))
            
            except Exception as e:
                # Skip this zone if there's an error
                pass
        
        if not has_features:
            return None
        
        # Downsample with anti-aliasing
        final_img = img.resize((self.tile_size, self.tile_size), Image.Resampling.LANCZOS)
        
        return final_img
    
    def _draw_polygon(self, img, draw, coords, style, zoom, scale_factor):
        """
        Draw a single polygon with appropriate style.
        
        Args:
            img: Image object
            draw: ImageDraw object
            coords: Pixel coordinates
            style: Style dictionary
            zoom: Zoom level
            scale_factor: Resolution multiplier
        """
        if style['pattern'] == 'HATCH':
            # Draw background
            fill_color = style['fill'] + (255,)
            draw.polygon(coords, fill=fill_color)
            
            # Draw hatch pattern
            if style['stroke']:
                self._draw_hatch_pattern(img, coords, style['stroke'], zoom)
            
            # Draw outline if specified
            if style['stroke'] and style['stroke_width'] > 0:
                stroke_color = style['stroke'] + (255,)
                draw.polygon(coords, outline=stroke_color, 
                           width=style['stroke_width'] * scale_factor)
        else:
            # Solid fill
            fill_color = style['fill'] + (255,)
            draw.polygon(coords, fill=fill_color)
            
            # Draw outline if specified
            if style['stroke'] and style['stroke_width'] > 0:
                stroke_color = style['stroke'] + (255,)
                draw.polygon(coords, outline=stroke_color, 
                           width=style['stroke_width'] * scale_factor)
    
    def generate_tiles(self, min_zoom: int = 0, max_zoom: int = 22):
        """
        Generate all tiles for specified zoom range.
        
        Args:
            min_zoom: Minimum zoom level (default: 0)
            max_zoom: Maximum zoom level (default: 22)
        """
        print("🔨 TILE GENERATION")
        print("=" * 80)
        print(f"Zoom Range: {min_zoom} to {max_zoom}")
        print(f"Tile Size: {self.tile_size}×{self.tile_size} pixels")
        print("=" * 80)
        
        total_generated = 0
        total_empty = 0
        start_time = datetime.now()
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"\n🔍 Zoom Level {zoom}")
            print("-" * 80)
            
            # Get all tiles for this zoom
            tiles = list(mercantile.tiles(
                self.bounds[0], self.bounds[1],
                self.bounds[2], self.bounds[3],
                zooms=[zoom]
            ))
            
            print(f"Tiles to process: {len(tiles)}")
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            generated = 0
            empty = 0
            errors = 0
            
            # Process each tile
            for i, tile in enumerate(tiles):
                # Progress indicator
                if i > 0 and i % 100 == 0:
                    print(f"  Progress: {i}/{len(tiles)} ({generated} tiles, {empty} empty)")
                
                # Create directory structure
                x_dir = zoom_dir / str(tile.x)
                x_dir.mkdir(exist_ok=True)
                
                tile_path = x_dir / f"{tile.y}.png"
                
                # Skip if exists
                if tile_path.exists():
                    generated += 1
                    continue
                
                # Generate tile
                try:
                    img = self.render_tile(tile.x, tile.y, zoom)
                    if img:
                        img.save(tile_path, 'PNG', optimize=True, compress_level=6)
                        generated += 1
                        total_generated += 1
                    else:
                        empty += 1
                        total_empty += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:  # Only show first 3 errors
                        print(f"  ⚠️  Error on tile {tile.x}/{tile.y}: {e}")
            
            print(f"✅ Generated: {generated:,} tiles")
            print(f"⬜ Empty: {empty:,} tiles")
            if errors > 0:
                print(f"⚠️  Errors: {errors} tiles")
        
        # Final summary
        elapsed = datetime.now() - start_time
        print("\n" + "=" * 80)
        print("✅ TILE GENERATION COMPLETE!")
        print("=" * 80)
        print(f"Total tiles generated: {total_generated:,}")
        print(f"Empty tiles skipped: {total_empty:,}")
        print(f"Time elapsed: {elapsed}")
        print(f"Output directory: {self.output_dir.absolute()}")
        print()
    
    def create_viewer(self):
        """Create interactive HTML viewer"""
        cx = (self.bounds[0] + self.bounds[2]) / 2
        cy = (self.bounds[1] + self.bounds[3]) / 2
        
        # Create legend HTML
        color_map = self.get_color_specifications()
        legend_items = []
        
        for zone_name in sorted(self.zones.keys()):
            if zone_name in color_map:
                style = color_map[zone_name]
                rgb = style['fill']
                hex_color = '#{:02X}{:02X}{:02X}'.format(rgb[0], rgb[1], rgb[2])
                
                display_name = zone_name.replace('_', ' ')
                pattern_note = " (Hatched)" if style['pattern'] == 'HATCH' else ""
                
                legend_items.append(
                    f'<div class="legend-item">'
                    f'<span class="legend-color" style="background:{hex_color};"></span>'
                    f'<span class="legend-label">{display_name}{pattern_note}</span>'
                    f'</div>'
                )
        
        legend_html = '\n'.join(legend_items)
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Warangal Master Plan - Interactive Map</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ height: 100vh; }}
        .info-panel {{
            position: absolute; top: 10px; right: 10px;
            background: white; padding: 15px; border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000;
            max-width: 300px; max-height: 80vh; overflow-y: auto;
        }}
        .info-panel h3 {{ margin: 0 0 10px 0; font-size: 16px; }}
        .legend-item {{ display: flex; align-items: center; margin: 5px 0; font-size: 12px; }}
        .legend-color {{ width: 20px; height: 20px; border: 1px solid #ccc; margin-right: 8px; }}
        .zoom-info {{
            position: absolute; bottom: 30px; left: 10px;
            background: white; padding: 8px 12px; border-radius: 5px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.2); z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <h3>🗺️ Warangal Master Plan</h3>
        <div style="margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">
            <div><strong>{len(self.zones)}</strong> Zones</div>
            <div><strong>{sum(len(gdf) for gdf in self.zones.values()):,}</strong> Features</div>
        </div>
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;">
            <h4 style="margin: 0 0 10px 0; font-size: 14px;">Legend:</h4>
            {legend_html}
        </div>
    </div>
    <div class="zoom-info">Zoom: <strong id="zoom-level">12</strong></div>
    <script>
        var map = L.map('map').setView([{cy}, {cx}], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap', opacity: 0.3, maxZoom: 19
        }}).addTo(map);
        L.tileLayer('{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Warangal Master Plan', minZoom: 0, maxZoom: 22,
            bounds: [[{self.bounds[1]}, {self.bounds[0]}], [{self.bounds[3]}, {self.bounds[2]}]]
        }}).addTo(map);
        L.control.scale({{imperial: false}}).addTo(map);
        map.on('zoomend', function() {{
            document.getElementById('zoom-level').textContent = map.getZoom();
        }});
        map.fitBounds([[{self.bounds[1]}, {self.bounds[0]}], [{self.bounds[3]}, {self.bounds[2]}]]);
    </script>
</body>
</html>'''
        
        viewer_path = self.output_dir / "index.html"
        with open(viewer_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print("🌐 INTERACTIVE VIEWER")
        print("=" * 80)
        print(f"Created: {viewer_path.absolute()}")
        print("\nTo view:")
        print(f"  cd {self.output_dir}")
        print("  python3 -m http.server 8000")
        print("  Open: http://localhost:8000/")
        print()


def main():
    """Main execution function"""
    # Parse arguments
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/Telangana/warangal/master_plan"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "warangal_tiles"
    min_zoom = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    max_zoom = int(sys.argv[4]) if len(sys.argv) > 4 else 22
    
    # Check if data directory exists
    if not Path(data_dir).exists():
        print(f"❌ ERROR: Data directory not found: {data_dir}")
        print("\nUsage: python3 warangal_perfect_tile_generator.py [data_dir] [output_dir] [min_zoom] [max_zoom]")
        print("\nExample:")
        print("  python3 warangal_perfect_tile_generator.py data/Telangana/warangal/master_plan warangal_tiles 10 16")
        sys.exit(1)
    
    try:
        # Create generator
        generator = WarangalTileGenerator(
            master_plan_dir=data_dir,
            output_dir=output_dir
        )
        
        # Generate tiles
        generator.generate_tiles(min_zoom=min_zoom, max_zoom=max_zoom)
        
        # Create viewer
        generator.create_viewer()
        
        print("=" * 80)
        print("🎉 SUCCESS! All tiles generated with exact colors!")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

