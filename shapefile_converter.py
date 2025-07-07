#!/usr/bin/env python
"""
Shapefile to GeoJSON Converter
This script helps convert shapefiles to GeoJSON format for the geomapping system.
"""

import os
import sys
import json
from pathlib import Path

def convert_shapefile_to_geojson(shp_path, output_path=None):
    """
    Convert a shapefile to GeoJSON format
    
    Args:
        shp_path: Path to the .shp file
        output_path: Output GeoJSON file path (optional)
    
    Returns:
        Path to the converted GeoJSON file
    """
    
    try:
        # Try to use GDAL/OGR if available
        try:
            from osgeo import ogr, gdal
            return _convert_with_gdal(shp_path, output_path)
        except ImportError:
            print("GDAL not available, trying alternative methods...")
            
        # Try to use Fiona if available
        try:
            import fiona
            return _convert_with_fiona(shp_path, output_path)
        except ImportError:
            print("Fiona not available...")
            
        # Try to use geopandas if available
        try:
            import geopandas as gpd
            return _convert_with_geopandas(shp_path, output_path)
        except ImportError:
            print("GeoPandas not available...")
            
        print("❌ No shapefile conversion libraries found!")
        print("Please install one of the following:")
        print("  pip install GDAL")
        print("  pip install fiona")
        print("  pip install geopandas")
        return None
        
    except Exception as e:
        print(f"❌ Error converting shapefile: {e}")
        return None

def _convert_with_gdal(shp_path, output_path):
    """Convert using GDAL/OGR"""
    print("🔧 Converting with GDAL/OGR...")
    
    # Open the shapefile
    driver = ogr.GetDriverByName('ESRI Shapefile')
    data_source = driver.Open(shp_path, 0)
    
    if data_source is None:
        raise Exception(f"Could not open shapefile: {shp_path}")
    
    layer = data_source.GetLayer()
    
    # Create GeoJSON structure
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    # Process features
    feature = layer.GetNextFeature()
    while feature:
        # Get geometry
        geom = feature.GetGeometryRef()
        if geom is not None:
            # Convert to GeoJSON geometry
            geom_json = json.loads(geom.ExportToJson())
            
            # Get attributes
            properties = {}
            for i in range(feature.GetFieldCount()):
                field_def = feature.GetFieldDefnRef(i)
                field_name = field_def.GetName()
                field_value = feature.GetField(i)
                properties[field_name] = field_value
            
            # Create feature
            geojson_feature = {
                "type": "Feature",
                "geometry": geom_json,
                "properties": properties
            }
            
            geojson["features"].append(geojson_feature)
        
        feature = layer.GetNextFeature()
    
    # Close data source
    data_source = None
    
    # Determine output path
    if output_path is None:
        output_path = Path(shp_path).with_suffix('.geojson')
    
    # Write GeoJSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Converted to: {output_path}")
    print(f"📊 Features: {len(geojson['features'])}")
    
    return output_path

def _convert_with_fiona(shp_path, output_path):
    """Convert using Fiona"""
    print("🔧 Converting with Fiona...")
    
    # Determine output path
    if output_path is None:
        output_path = Path(shp_path).with_suffix('.geojson')
    
    # Convert using fiona
    with fiona.open(shp_path, 'r') as source:
        # Write to GeoJSON
        with fiona.open(output_path, 'w', 
                       driver='GeoJSON',
                       crs=source.crs,
                       schema=source.schema) as dest:
            for feature in source:
                dest.write(feature)
    
    print(f"✅ Converted to: {output_path}")
    return output_path

def _convert_with_geopandas(shp_path, output_path):
    """Convert using GeoPandas"""
    print("🔧 Converting with GeoPandas...")
    
    # Read shapefile
    gdf = gpd.read_file(shp_path)
    
    # Determine output path
    if output_path is None:
        output_path = Path(shp_path).with_suffix('.geojson')
    
    # Write to GeoJSON
    gdf.to_file(output_path, driver='GeoJSON')
    
    print(f"✅ Converted to: {output_path}")
    print(f"📊 Features: {len(gdf)}")
    
    return output_path

def main():
    """Main function for command line usage"""
    if len(sys.argv) < 2:
        print("Usage: python shapefile_converter.py <shapefile_path> [output_path]")
        print("Example: python shapefile_converter.py data.shp")
        return
    
    shp_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(shp_path):
        print(f"❌ Shapefile not found: {shp_path}")
        return
    
    print(f"🔍 Converting shapefile: {shp_path}")
    result = convert_shapefile_to_geojson(shp_path, output_path)
    
    if result:
        print(f"\n🎉 Conversion successful!")
        print(f"📁 Output file: {result}")
        print(f"\n💡 Next steps:")
        print(f"1. Copy the GeoJSON file to the Docker container:")
        print(f"   docker cp {result} geomapping-web-1:/app/")
        print(f"2. Import it using the web interface or management commands")
    else:
        print("❌ Conversion failed!")

if __name__ == "__main__":
    main() 