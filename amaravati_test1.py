#!/usr/bin/env python3
"""
Amaravati Master Plan Combined Map & Tile Generator
Generates a single combined PNG map and splits it into tiles
"""

import os
import json
import math
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
from shapely.geometry import shape, Polygon, MultiPolygon
import warnings
warnings.filterwarnings('ignore')

@dataclass
class ZoneStyle:
    """Style configuration for a zone"""
    fill_color: str
    outline_color: Optional[str] = None
    pattern: Optional[str] = None
    opacity: float = 1.0

class AmaravatiMapGenerator:
    """Generate combined map and tiles from Amaravati GeoJSON data"""
    
    def __init__(self, data_path: str = "data/andhra_pradesh/amaravati/master_plan"):
        self.data_path = Path(data_path)
        self.output_path = Path("output_maps")
        
        # Exact bounding box for Amaravati
        self.bounds = {
            'min_lon': 80.407374,
            'min_lat': 16.413905,
            'max_lon': 80.603814,
            'max_lat': 16.589634
        }
        
        # Exact color mapping - updated to match actual file names
        self.zone_colors = {
            # Files with correct naming
            'Burial Ground': ZoneStyle('#FFFFFF', '#E39E00', 'dotted'),
            'Commercial Vacant': ZoneStyle('#C5E2FF'),
            'Not Available': ZoneStyle('#b6b6b6', '#000000'),
            'PGN-G': ZoneStyle('#4C7300'),
            'PGN-V': ZoneStyle('#897044'),
            'RAA': ZoneStyle('#FFAA00'),
            'Residential Vacant': ZoneStyle('#FFD37F'),
            'SC1b - Mixed Use': ZoneStyle('#73B2FF'),
            'SR2 Low Density Housing': ZoneStyle('#FFFFBE'),
            'SR4 - High Density Private': ZoneStyle('#FFAA00'),
            'SS1 - Government Zone': ZoneStyle('#E60000'),
            'SS3 - Special Zone': ZoneStyle('#A83800'),
            'SU2 - Road Network': ZoneStyle('#FFFFFF', '#000000'),
            
            # Files without spaces after hyphen (as they appear in your data)
            'C1 -Mixed use zone': ZoneStyle('#73B2FF'),
            'C2- General commercial zone': ZoneStyle('#00C5FF', '#000000'),
            'C3-Neighbourhood centre zone': ZoneStyle('#00C5FF'),
            'C4-Town centre zone': ZoneStyle('#00A9E6'),
            'C5-Regional centre zone': ZoneStyle('#0070FF'),
            'C6-Central business district zone': ZoneStyle('#005CE6'),
            'I1-Business park zone': ZoneStyle('#FFEEB8'),
            'I2-Logistics zone': ZoneStyle('#FF73DF'),
            'I3-Non polluting industry zone': ZoneStyle('#A900E6'),
            'P1-Passive zone': ZoneStyle('#267300'),
            'P2-Active zone': ZoneStyle('#38A800'),
            'P3-Protected zone': ZoneStyle('#BEE8FF'),
            'P3-Protected zone Hills': ZoneStyle('#4C7300'),
            'R1-Village planning zone': ZoneStyle('#FFFFFF', '#000000', 'hatched'),
            'R3-Medium to high density zone': ZoneStyle('#F5CA7A'),
            'R4-High density zone': ZoneStyle('#E69800'),
            'S2-Education zone': ZoneStyle('#FF7F7F'),
            'S3-Special zone': ZoneStyle('#D7B09E'),
            'SC1a-Mixed Use': ZoneStyle('#0070FF'),
            'SP1- Passive Zone': ZoneStyle('#267300'),
            'SP2- Active Zone': ZoneStyle('#38A800'),
            'SP3-Protected Zone': ZoneStyle('#00C5FF'),
            'SS2a- Education Zone': ZoneStyle('#FF7F7F'),
            'SS2b Cultural Zone': ZoneStyle('#C500FF'),
            'SS2c Health Zone': ZoneStyle('#D3FFBE'),
            'SU1-Reserve Zone': ZoneStyle('#FFFFFF', '#E1E1E1'),
            'U1-Reserve zone': ZoneStyle('#FFFFFF', '#CCCCCC'),
            'U2- Road Reserve Zone': ZoneStyle('#FFFFFF', '#000000'),
            
            # Alternative naming patterns (with spaces)
            'C1 - Mixed use zone': ZoneStyle('#73B2FF'),
            'C2 - General commercial zone': ZoneStyle('#00C5FF', '#000000'),
            'C3 - Neighbourhood centre zone': ZoneStyle('#00C5FF'),
            'C4 - Town centre zone': ZoneStyle('#00A9E6'),
            'C5 - Regional centre zone': ZoneStyle('#0070FF'),
            'C6 - Central business district zone': ZoneStyle('#005CE6'),
            'I1 - Business park zone': ZoneStyle('#FFEEB8'),
            'I2 - Logistics zone': ZoneStyle('#FF73DF'),
            'I3 - Non polluting industry zone': ZoneStyle('#A900E6'),
            'P1 - Passive zone': ZoneStyle('#267300'),
            'P2 - Active zone': ZoneStyle('#38A800'),
            'P3 - Protected zone': ZoneStyle('#BEE8FF'),
            'P3 - Protected zone Hills': ZoneStyle('#4C7300'),
            'R1 - Village planning zone': ZoneStyle('#FFFFFF', '#000000', 'hatched'),
            'R3 - Medium to high density zone': ZoneStyle('#F5CA7A'),
            'R4 - High density zone': ZoneStyle('#E69800'),
            'S2 - Education zone': ZoneStyle('#FF7F7F'),
            'S3 - Special zone': ZoneStyle('#D7B09E'),
            'SC1a - Mixed Use': ZoneStyle('#0070FF'),
            'SP1 - Passive Zone': ZoneStyle('#267300'),
            'SP2 - Active Zone': ZoneStyle('#38A800'),
            'SP3 - Protected Zone': ZoneStyle('#00C5FF'),
            'SS2a - Education Zone': ZoneStyle('#FF7F7F'),
            'SS2b - Cultural Zone': ZoneStyle('#C500FF'),
            'SS2c - Health Zone': ZoneStyle('#D3FFBE'),
            'SU1 - Reserve Zone': ZoneStyle('#FFFFFF', '#E1E1E1'),
            'U1 - Reserve zone': ZoneStyle('#FFFFFF', '#CCCCCC'),
            'U2 - Road Reserve Zone': ZoneStyle('#FFFFFF', '#000000')
        }
        
        self.geojson_data = {}
        self.features_by_zone = {}
        
    def load_geojson_files(self) -> Dict:
        """Load all GeoJSON files from the data directory"""
        print(f"\n📂 Loading GeoJSON files from {self.data_path}")
        print("=" * 60)
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"❌ Data path {self.data_path} does not exist")
        
        geojson_files = list(self.data_path.glob("*.geojson"))
        
        if not geojson_files:
            raise FileNotFoundError(f"❌ No GeoJSON files found in {self.data_path}")
        
        total_features = 0
        
        for file_path in geojson_files:
            zone_name = file_path.stem  # Remove .geojson extension
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.geojson_data[zone_name] = data
                
                # Convert to Shapely geometries for easier processing
                features = []
                for feature in data.get('features', []):
                    try:
                        geom = shape(feature['geometry'])
                        features.append({
                            'geometry': geom,
                            'properties': feature.get('properties', {})
                        })
                        total_features += 1
                    except Exception as e:
                        print(f"  ⚠️  Could not parse feature in {zone_name}: {e}")
                        
                self.features_by_zone[zone_name] = features
                print(f"  ✓ {zone_name}: {len(features)} features")
                
            except Exception as e:
                print(f"  ❌ Error loading {file_path}: {e}")
        
        print("=" * 60)
        print(f"✅ Total: {len(self.geojson_data)} files, {total_features} features loaded\n")
        return self.geojson_data
    
    def _draw_geometry(self, ax, geom, style: ZoneStyle):
        """Draw a geometry with the specified style"""
        from matplotlib.patches import Polygon as MPLPolygon
        
        patches = []
        
        if geom.geom_type == 'Polygon':
            coords = list(geom.exterior.coords)
            patch = MPLPolygon(coords, closed=True)
            patches.append(patch)
            
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                coords = list(poly.exterior.coords)
                patch = MPLPolygon(coords, closed=True)
                patches.append(patch)
        
        if patches:
            # Handle patterns
            if style.pattern == 'hatched':
                collection = PatchCollection(patches, 
                                           facecolor=style.fill_color,
                                           edgecolor=style.outline_color or '#000000',
                                           linewidth=0.5,
                                           hatch='///',
                                           alpha=style.opacity)
            elif style.pattern == 'dotted':
                collection = PatchCollection(patches,
                                           facecolor=style.fill_color,
                                           edgecolor=style.outline_color or '#000000',
                                           linewidth=0.5,
                                           linestyle=':',
                                           alpha=style.opacity)
            else:
                collection = PatchCollection(patches,
                                           facecolor=style.fill_color,
                                           edgecolor=style.outline_color or '#000000',
                                           linewidth=0.5 if style.outline_color else 0,
                                           alpha=style.opacity)
            
            ax.add_collection(collection)
    
    def generate_combined_map(self, width: int = 4000, height: int = 3600, 
                            dpi: int = 100, add_title: bool = True):
        """Generate a single combined map of all zones"""
        
        print(f"🎨 Generating combined map ({width}x{height} pixels at {dpi} DPI)")
        print("=" * 60)
        
        # Create figure
        fig_width = width / dpi
        fig_height = height / dpi
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
        
        # Set bounds
        ax.set_xlim(self.bounds['min_lon'], self.bounds['max_lon'])
        ax.set_ylim(self.bounds['min_lat'], self.bounds['max_lat'])
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Set background
        fig.patch.set_facecolor('#F0F0F0')
        ax.set_facecolor('#F0F0F0')
        
        # Sort zones (roads and utilities last for proper layering)
        sorted_zones = sorted(self.features_by_zone.keys(),
                            key=lambda z: 1 if any(x in z for x in ['Road', 'U1', 'U2', 'SU1', 'SU2']) else 0)
        
        # Draw each zone
        for i, zone_name in enumerate(sorted_zones, 1):
            if zone_name not in self.zone_colors:
                print(f"  ⚠️  No color defined for {zone_name}, skipping...")
                continue
                
            style = self.zone_colors[zone_name]
            features = self.features_by_zone[zone_name]
            
            print(f"  [{i}/{len(sorted_zones)}] Drawing {zone_name}: {len(features)} features")
            
            for feature in features:
                try:
                    self._draw_geometry(ax, feature['geometry'], style)
                except Exception as e:
                    continue
        
        # Add title if requested
        if add_title:
            fig.suptitle('Amaravati Master Plan', fontsize=24, y=0.98, fontweight='bold')
        
        # Create output directory
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Save the combined map
        output_file = self.output_path / "amaravati_master_plan.png"
        print(f"\n💾 Saving combined map to: {output_file}")
        
        plt.savefig(output_file, dpi=dpi, bbox_inches='tight', 
                   facecolor=fig.get_facecolor(), edgecolor='none',
                   pad_inches=0.1)
        plt.close(fig)
        
        print("✅ Combined map saved successfully!\n")
        
        return output_file
    
    def split_into_tiles(self, image_path: Path = None, tile_size: int = 256):
        """Split the combined map into tiles"""
        
        if image_path is None:
            image_path = self.output_path / "amaravati_master_plan.png"
        
        if not image_path.exists():
            print(f"❌ Image not found: {image_path}")
            print("   Please run generate_combined_map() first")
            return
        
        print(f"🔪 Splitting map into {tile_size}x{tile_size} pixel tiles")
        print("=" * 60)
        
        # Open the combined map
        img = Image.open(image_path)
        width, height = img.size
        
        print(f"  Source image: {width}x{height} pixels")
        
        # Calculate number of tiles
        tiles_x = math.ceil(width / tile_size)
        tiles_y = math.ceil(height / tile_size)
        total_tiles = tiles_x * tiles_y
        
        print(f"  Grid: {tiles_x} x {tiles_y} = {total_tiles} tiles")
        
        # Create tiles directory
        tiles_dir = self.output_path / "tiles"
        tiles_dir.mkdir(exist_ok=True)
        
        # Generate tiles
        tile_count = 0
        for y in range(tiles_y):
            for x in range(tiles_x):
                # Calculate crop box
                left = x * tile_size
                top = y * tile_size
                right = min(left + tile_size, width)
                bottom = min(top + tile_size, height)
                
                # Crop tile from main image
                tile = img.crop((left, top, right, bottom))
                
                # If tile is smaller than tile_size (edge tiles), pad it
                if tile.size != (tile_size, tile_size):
                    padded = Image.new('RGB', (tile_size, tile_size), '#F0F0F0')
                    padded.paste(tile, (0, 0))
                    tile = padded
                
                # Save tile
                tile_filename = f"tile_{x:03d}_{y:03d}.png"
                tile_path = tiles_dir / tile_filename
                tile.save(tile_path, 'PNG', optimize=True, compress_level=9)
                
                tile_count += 1
                if tile_count % 10 == 0:
                    print(f"  Progress: {tile_count}/{total_tiles} tiles generated...", end='\r')
        
        print(f"\n✅ Generated {total_tiles} tiles in: {tiles_dir}\n")
        
        # Generate tile index
        self._generate_tile_index(tiles_x, tiles_y, tile_size, width, height)
    
    def _generate_tile_index(self, tiles_x: int, tiles_y: int, tile_size: int,
                            img_width: int, img_height: int):
        """Generate an HTML index for viewing tiles"""
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Amaravati Master Plan - Tile Viewer</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: #2c3e50;
            color: white;
            font-family: Arial, sans-serif;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
        }}
        .info {{
            text-align: center;
            margin-bottom: 20px;
            color: #ecf0f1;
        }}
        .container {{
            position: relative;
            margin: 0 auto;
            width: {img_width}px;
            height: {img_height}px;
            background: #34495e;
            border: 2px solid #7f8c8d;
            transform-origin: top left;
        }}
        .tile {{
            position: absolute;
            width: {tile_size}px;
            height: {tile_size}px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .controls {{
            text-align: center;
            margin: 20px;
        }}
        button {{
            padding: 10px 20px;
            margin: 5px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }}
        button:hover {{
            background: #2980b9;
        }}
        #zoom-level {{
            display: inline-block;
            margin: 0 10px;
            font-size: 18px;
        }}
    </style>
</head>
<body>
    <h1>🗺️ Amaravati Master Plan - Tiled View</h1>
    <div class="info">
        Map Size: {img_width}x{img_height}px | 
        Tile Size: {tile_size}x{tile_size}px | 
        Grid: {tiles_x}x{tiles_y} tiles
    </div>
    
    <div class="controls">
        <button onclick="zoomOut()">➖ Zoom Out</button>
        <span id="zoom-level">Zoom: 100%</span>
        <button onclick="zoomIn()">➕ Zoom In</button>
        <button onclick="resetZoom()">🔄 Reset</button>
    </div>
    
    <div class="container" id="map-container">
"""
        
        # Add tiles
        for y in range(tiles_y):
            for x in range(tiles_x):
                left = x * tile_size
                top = y * tile_size
                tile_filename = f"tile_{x:03d}_{y:03d}.png"
                html_content += f'        <img class="tile" src="tiles/{tile_filename}" style="left:{left}px; top:{top}px;" alt="Tile {x},{y}">\n'
        
        html_content += """    </div>
    
    <script>
        let currentZoom = 1.0;
        const container = document.getElementById('map-container');
        const zoomDisplay = document.getElementById('zoom-level');
        
        function updateZoom() {
            container.style.transform = `scale(${currentZoom})`;
            zoomDisplay.textContent = `Zoom: ${Math.round(currentZoom * 100)}%`;
        }
        
        function zoomIn() {
            currentZoom = Math.min(currentZoom + 0.25, 3.0);
            updateZoom();
        }
        
        function zoomOut() {
            currentZoom = Math.max(currentZoom - 0.25, 0.25);
            updateZoom();
        }
        
        function resetZoom() {
            currentZoom = 1.0;
            updateZoom();
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === '+' || e.key === '=') zoomIn();
            if (e.key === '-' || e.key === '_') zoomOut();
            if (e.key === '0') resetZoom();
        });
    </script>
</body>
</html>"""
        
        # Save HTML file
        index_path = self.output_path / "tile_viewer.html"
        with open(index_path, 'w') as f:
            f.write(html_content)
        
        print(f"📄 Tile viewer HTML saved to: {index_path}")
    
    def generate_legend(self):
        """Generate a legend showing all zone colors"""
        
        print("📊 Generating zone color legend")
        print("=" * 60)
        
        # Create figure for legend
        num_zones = len(self.zone_colors)
        fig_height = max(8, num_zones * 0.3)
        fig, ax = plt.subplots(figsize=(12, fig_height))
        
        ax.set_xlim(0, 10)
        ax.set_ylim(0, num_zones + 1)
        ax.axis('off')
        
        # Sort zones alphabetically
        sorted_zones = sorted(self.zone_colors.keys())
        
        y_pos = num_zones
        
        for zone_name in sorted_zones:
            style = self.zone_colors[zone_name]
            
            # Draw color box
            rect = mpatches.Rectangle((0.5, y_pos - 0.4), 1, 0.8,
                                     facecolor=style.fill_color,
                                     edgecolor=style.outline_color or '#000000',
                                     linewidth=2)
            
            if style.pattern == 'hatched':
                rect.set_hatch('///')
            elif style.pattern == 'dotted':
                rect.set_linestyle(':')
            
            ax.add_patch(rect)
            
            # Add zone name
            ax.text(2, y_pos, zone_name, fontsize=11, 
                   verticalalignment='center')
            
            # Add hex color code
            color_text = style.fill_color
            if style.outline_color and style.outline_color != '#000000':
                color_text += f" / {style.outline_color}"
            ax.text(7, y_pos, color_text, fontsize=9, 
                   verticalalignment='center', color='#666')
            
            y_pos -= 1
        
        # Add title
        ax.text(5, num_zones + 0.5, 'Amaravati Master Plan - Zone Color Legend',
               fontsize=18, fontweight='bold', horizontalalignment='center')
        
        # Save legend
        legend_path = self.output_path / "zone_legend.png"
        plt.savefig(legend_path, bbox_inches='tight', facecolor='white', dpi=100)
        plt.close(fig)
        
        print(f"✅ Legend saved to: {legend_path}\n")
    
    def generate_metadata(self):
        """Generate metadata JSON file"""
        
        metadata = {
            'project': 'Amaravati Master Plan',
            'location': 'Amaravati, Andhra Pradesh, India',
            'bounds': self.bounds,
            'center': {
                'lat': (self.bounds['min_lat'] + self.bounds['max_lat']) / 2,
                'lon': (self.bounds['min_lon'] + self.bounds['max_lon']) / 2
            },
            'zones': {
                zone: {
                    'fill_color': style.fill_color,
                    'outline_color': style.outline_color,
                    'pattern': style.pattern,
                    'feature_count': len(self.features_by_zone.get(zone, []))
                }
                for zone, style in self.zone_colors.items()
            },
            'statistics': {
                'total_zones': len(self.zone_colors),
                'total_features': sum(len(features) for features in self.features_by_zone.values()),
                'total_files': len(self.geojson_data)
            },
            'attribution': 'APCRDA - Andhra Pradesh Capital Region Development Authority'
        }
        
        metadata_path = self.output_path / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"📋 Metadata saved to: {metadata_path}\n")
    
    def run(self, map_width: int = 4000, map_height: int = 3600,
           tile_size: int = 256, dpi: int = 100):
        """Run the complete generation process"""
        
        print("\n" + "=" * 60)
        print("🗺️  AMARAVATI MASTER PLAN - MAP & TILE GENERATOR")
        print("=" * 60)
        
        # Load GeoJSON data
        self.load_geojson_files()
        
        # Generate combined map
        map_file = self.generate_combined_map(
            width=map_width,
            height=map_height,
            dpi=dpi,
            add_title=True
        )
        
        # Split into tiles
        self.split_into_tiles(
            image_path=map_file,
            tile_size=tile_size
        )
        
        # Generate legend
        self.generate_legend()
        
        # Generate metadata
        self.generate_metadata()
        
        print("=" * 60)
        print("✨ ALL TASKS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\n📁 Output Directory: {self.output_path}")
        print("\n📦 Generated Files:")
        print(f"  • amaravati_master_plan.png - Full resolution map")
        print(f"  • tiles/ - Directory containing all tile images")
        print(f"  • tile_viewer.html - Interactive tile viewer")
        print(f"  • zone_legend.png - Color legend for all zones")
        print(f"  • metadata.json - Project metadata")
        print("\n💡 Open 'tile_viewer.html' in a browser to view the tiled map")
        print("=" * 60 + "\n")


def main():
    """Main entry point"""
    
    # === CONFIGURATION ===
    DATA_PATH = "data/andhra_pradesh/amaravati/master_plan"  # Path to GeoJSON files
    MAP_WIDTH = 4000        # Width of combined map in pixels
    MAP_HEIGHT = 3600       # Height of combined map in pixels
    TILE_SIZE = 256         # Size of each tile in pixels
    DPI = 100              # DPI for rendering (higher = better quality but larger files)
    ZOOM_LEVEL = 14        # Zoom level for tile directory structure
    
    try:
        # Create generator instance
        generator = AmaravatiMapGenerator(DATA_PATH)
        
        # Run generation process
        generator.run(
            map_width=MAP_WIDTH,
            map_height=MAP_HEIGHT,
            tile_size=TILE_SIZE,
            dpi=DPI
        )
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print(f"\n📁 Please ensure your GeoJSON files are located in:")
        print(f"   {DATA_PATH}/")
        print("\n   The directory should contain all 41 .geojson files")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check for required packages
    required_packages = ['shapely', 'matplotlib', 'PIL', 'numpy']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package if package != 'PIL' else 'PIL')
        except ImportError:
            missing_packages.append('pillow' if package == 'PIL' else package)
    
    if missing_packages:
        print("📦 Installing required packages...")
        import subprocess
        subprocess.check_call(['pip', 'install'] + missing_packages)
        print("✅ Packages installed. Please run the script again.")
        exit(0)
    
    # Run the main function
    main()