#!/usr/bin/env python3
"""
Fix layer bounds for Amaravati
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer, GeoFeature
from django.contrib.gis.db.models import Extent

def fix_amaravati_bounds():
    """Fix layer bounds for Amaravati"""
    
    print("🔧 Fixing Amaravati layer bounds...")
    
    try:
        # Get Amaravati city and layer
        city = City.objects.get(slug='amaravati')
        layer = DataLayer.objects.get(slug='amaravati_master_plan')
        
        print(f"Found layer: {layer.name}")
        print(f"Current bounds: {layer.bbox_xmin}, {layer.bbox_ymin} to {layer.bbox_xmax}, {layer.bbox_ymax}")
        
        # Calculate bounds from features
        extent = GeoFeature.objects.filter(
            layer=layer, 
            is_valid=True
        ).aggregate(extent=Extent('geometry'))['extent']
        
        if extent:
            print(f"Calculated extent: {extent}")
            
            # Update layer bounds
            layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax = extent
            layer.save()
            
            print(f"Updated layer bounds: {layer.bbox_xmin}, {layer.bbox_ymin} to {layer.bbox_xmax}, {layer.bbox_ymax}")
            print("✅ Layer bounds fixed!")
            
            return True
        else:
            print("❌ No features found to calculate bounds")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    fix_amaravati_bounds()
