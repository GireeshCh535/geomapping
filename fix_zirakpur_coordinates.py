#!/usr/bin/env python
"""
Fix Zirakpur coordinates that were imported in EPSG:3857 but stored as EPSG:4326
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from django.contrib.gis.geos import Point, GEOSGeometry
from maps.models import DataLayer, GeoFeature

def main():
    print("=" * 80)
    print("Zirakpur Coordinate System Fix")
    print("=" * 80)
    
    # Get the Zirakpur layer
    layer = DataLayer.objects.filter(slug='zirakpur_masterplan').first()
    if not layer:
        print("ERROR: Zirakpur masterplan layer not found!")
        return
    
    print(f"\nLayer: {layer.name}")
    print(f"City: {layer.city.name}")
    print(f"State: {layer.city.state_ref.name if layer.city.state_ref else 'N/A'}")
    
    # Get features
    features = GeoFeature.objects.filter(layer=layer)
    print(f"\nTotal features: {features.count()}")
    
    if features.count() == 0:
        print("No features found!")
        return
    
    # Check the first feature
    feature = features.first()
    print(f"\n{'Current State':=^80}")
    print(f"Feature ID: {feature.id}")
    print(f"Feature Name: {feature.name or 'N/A'}")
    print(f"Geometry SRID: {feature.geometry.srid}")
    print(f"Geometry Type: {feature.geometry.geom_type}")
    print(f"Geometry Bounds: {feature.geometry.extent}")
    
    # Test the search point
    search_lat = 30.649330251327584
    search_lng = 76.85335294820209
    search_point = Point(search_lng, search_lat, srid=4326)
    
    print(f"\n{'Test Search Point':=^80}")
    print(f"Latitude: {search_lat}")
    print(f"Longitude: {search_lng}")
    print(f"Point intersects geometry: {feature.geometry.intersects(search_point)}")
    print(f"Point within geometry: {feature.geometry.contains(search_point)}")
    
    # The bounds show this is EPSG:3857 data stored as EPSG:4326
    # Let's get a sample coordinate from the geometry
    if feature.geometry.geom_type == 'MultiPolygon':
        sample_coord = feature.geometry[0][0][0]
    elif feature.geometry.geom_type == 'Polygon':
        sample_coord = feature.geometry[0][0]
    else:
        sample_coord = feature.geometry.coords[0]
    
    print(f"\n{'Sample Coordinate from Database':=^80}")
    print(f"X (should be longitude ~76-77): {sample_coord[0]}")
    print(f"Y (should be latitude ~30-31): {sample_coord[1]}")
    
    # Check if coordinates are in EPSG:3857 range
    if sample_coord[0] > 180 or sample_coord[1] > 90:
        print("\n" + "!" * 80)
        print("PROBLEM DETECTED: Coordinates are in EPSG:3857 (Web Mercator) format!")
        print("The geometry needs to be transformed from EPSG:3857 to EPSG:4326")
        print("!" * 80)
        
        # Fix the geometry
        print(f"\n{'Fixing Geometry':=^80}")
        
        # Clone the geometry and set it to EPSG:3857 first
        corrected_geom = feature.geometry.clone()
        corrected_geom.srid = 3857  # Set the actual SRID of the data
        
        # Transform to EPSG:4326
        corrected_geom.transform(4326)
        
        print(f"Corrected Geometry Bounds: {corrected_geom.extent}")
        
        # Get corrected sample coordinate
        if corrected_geom.geom_type == 'MultiPolygon':
            corrected_sample = corrected_geom[0][0][0]
        elif corrected_geom.geom_type == 'Polygon':
            corrected_sample = corrected_geom[0][0]
        else:
            corrected_sample = corrected_geom.coords[0]
        
        print(f"\n{'Corrected Sample Coordinate':=^80}")
        print(f"X (longitude): {corrected_sample[0]}")
        print(f"Y (latitude): {corrected_sample[1]}")
        
        # Test with the search point again
        print(f"\n{'Testing with Corrected Geometry':=^80}")
        print(f"Point intersects corrected geometry: {corrected_geom.intersects(search_point)}")
        print(f"Point within corrected geometry: {corrected_geom.contains(search_point)}")
        
        # Ask user to confirm fix
        print(f"\n{'Ready to Apply Fix':=^80}")
        print(f"This will update {features.count()} feature(s) in the database")
        response = input("Do you want to apply the fix? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            print("\nApplying fix...")
            for idx, feat in enumerate(features, 1):
                # Clone and correct the geometry
                geom = feat.geometry.clone()
                geom.srid = 3857
                geom.transform(4326)
                
                # Update the feature
                feat.geometry = geom
                feat.save(update_fields=['geometry'])
                
                print(f"  Fixed feature {idx}/{features.count()}")
            
            print(f"\n{'SUCCESS!':=^80}")
            print(f"Updated {features.count()} feature(s)")
            
            # Verify the fix
            print(f"\n{'Verification':=^80}")
            feature.refresh_from_db()
            print(f"New Geometry Bounds: {feature.geometry.extent}")
            print(f"Point intersects geometry: {feature.geometry.intersects(search_point)}")
            print(f"Point within geometry: {feature.geometry.contains(search_point)}")
        else:
            print("\nFix cancelled by user")
    else:
        print("\nNo problem detected - coordinates appear to be in correct format")

if __name__ == '__main__':
    main()

