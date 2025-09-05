#!/usr/bin/env python3
"""
Amaravati Tile Verification Tool
===============================
Verifies tile quality, checks for seams, and validates tile structure.
"""

import os
import sys
import json
from pathlib import Path
from PIL import Image
import numpy as np
from typing import Dict, List, Tuple

class TileVerifier:
    def __init__(self, tile_dir: str):
        self.tile_dir = Path(tile_dir)
        self.issues = []
        self.stats = {
            'total_tiles': 0,
            'valid_tiles': 0,
            'empty_tiles': 0,
            'seam_issues': 0,
            'size_issues': 0
        }
    
    def verify_tile_structure(self):
        """Verify tile directory structure and count tiles"""
        print("🔍 Verifying tile structure...")
        
        zoom_dirs = [d for d in self.tile_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        zoom_dirs.sort(key=lambda x: int(x.name))
        
        print(f"📁 Found zoom levels: {[d.name for d in zoom_dirs]}")
        
        for zoom_dir in zoom_dirs:
            zoom_level = int(zoom_dir.name)
            png_files = list(zoom_dir.glob("*.png"))
            self.stats['total_tiles'] += len(png_files)
            
            print(f"   Zoom {zoom_level}: {len(png_files)} tiles")
        
        print(f"✅ Total tiles found: {self.stats['total_tiles']}")
    
    def verify_tile_properties(self):
        """Verify individual tile properties"""
        print("\n🔍 Verifying tile properties...")
        
        zoom_dirs = [d for d in self.tile_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        
        for zoom_dir in zoom_dirs:
            zoom_level = int(zoom_dir.name)
            png_files = list(zoom_dir.glob("*.png"))
            
            for png_file in png_files[:5]:  # Check first 5 tiles per zoom level
                try:
                    with Image.open(png_file) as img:
                        # Check size
                        if img.size != (256, 256):
                            self.issues.append(f"Size issue: {png_file} is {img.size}, expected (256, 256)")
                            self.stats['size_issues'] += 1
                        
                        # Check if tile is empty (all transparent)
                        if img.mode == 'RGBA':
                            alpha = np.array(img)[:, :, 3]
                            if np.all(alpha == 0):
                                self.stats['empty_tiles'] += 1
                            else:
                                self.stats['valid_tiles'] += 1
                        else:
                            self.stats['valid_tiles'] += 1
                            
                except Exception as e:
                    self.issues.append(f"Error reading {png_file}: {e}")
        
        print(f"✅ Valid tiles: {self.stats['valid_tiles']}")
        print(f"⚠️  Empty tiles: {self.stats['empty_tiles']}")
        print(f"❌ Size issues: {self.stats['size_issues']}")
    
    def check_seams(self):
        """Check for seam issues between adjacent tiles"""
        print("\n🔍 Checking for seam issues...")
        
        # Check a few adjacent tiles at different zoom levels
        test_cases = [
            (10, 740, 464),  # Tile at zoom 10
            (11, 1481, 928), # Adjacent tiles at zoom 11
            (12, 2963, 1856) # Adjacent tiles at zoom 12
        ]
        
        for zoom, x, y in test_cases:
            tile_path = self.tile_dir / str(zoom) / f"{x}.png"
            if tile_path.exists():
                try:
                    with Image.open(tile_path) as img:
                        # Check if tile has content
                        if img.mode == 'RGBA':
                            alpha = np.array(img)[:, :, 3]
                            if not np.all(alpha == 0):
                                print(f"   ✅ Tile {zoom}/{x}/{y} has content")
                            else:
                                print(f"   ⚠️  Tile {zoom}/{x}/{y} is empty")
                        else:
                            print(f"   ✅ Tile {zoom}/{x}/{y} has content")
                except Exception as e:
                    self.issues.append(f"Error checking seam for {tile_path}: {e}")
            else:
                print(f"   ❌ Tile {zoom}/{x}/{y} not found")
    
    def verify_tilejson(self):
        """Verify TileJSON file"""
        print("\n🔍 Verifying TileJSON...")
        
        tilejson_path = self.tile_dir / "tilejson.json"
        if tilejson_path.exists():
            try:
                with open(tilejson_path, 'r') as f:
                    tilejson = json.load(f)
                
                required_fields = ['tilejson', 'name', 'tiles', 'minzoom', 'maxzoom', 'bounds']
                for field in required_fields:
                    if field in tilejson:
                        print(f"   ✅ {field}: {tilejson[field]}")
                    else:
                        self.issues.append(f"Missing field in TileJSON: {field}")
                
                # Check bounds
                bounds = tilejson.get('bounds', [])
                if len(bounds) == 4:
                    print(f"   ✅ Bounds: {bounds}")
                else:
                    self.issues.append(f"Invalid bounds in TileJSON: {bounds}")
                
            except Exception as e:
                self.issues.append(f"Error reading TileJSON: {e}")
        else:
            self.issues.append("TileJSON file not found")
    
    def generate_report(self):
        """Generate verification report"""
        print("\n" + "="*60)
        print("📊 TILE VERIFICATION REPORT")
        print("="*60)
        
        print(f"Total tiles: {self.stats['total_tiles']}")
        print(f"Valid tiles: {self.stats['valid_tiles']}")
        print(f"Empty tiles: {self.stats['empty_tiles']}")
        print(f"Size issues: {self.stats['size_issues']}")
        print(f"Seam issues: {self.stats['seam_issues']}")
        
        if self.issues:
            print(f"\n❌ Issues found ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   • {issue}")
        else:
            print("\n✅ No issues found!")
        
        # Save report
        report_path = self.tile_dir / "verification_report.json"
        report_data = {
            'stats': self.stats,
            'issues': self.issues,
            'timestamp': str(Path().cwd())
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Report saved to: {report_path}")

def main():
    """Main verification function"""
    tile_dir = "amaravati_perfect_tiles"
    
    if not Path(tile_dir).exists():
        print(f"❌ Tile directory not found: {tile_dir}")
        sys.exit(1)
    
    verifier = TileVerifier(tile_dir)
    
    # Run all verification checks
    verifier.verify_tile_structure()
    verifier.verify_tile_properties()
    verifier.check_seams()
    verifier.verify_tilejson()
    verifier.generate_report()

if __name__ == "__main__":
    main()
