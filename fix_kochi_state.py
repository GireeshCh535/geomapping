#!/usr/bin/env python
"""
Script to move Kochi data from 'kerela' state to 'kerala' state
to match the S3 tile paths.
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import State, City, DataLayer, GeoFeature, CityLayerStyle, LayerGroup, CityZoneMapping
from django.db import transaction

def fix_kochi_state():
    """Move Kochi data from kerela state to kerala state"""
    
    print("🔧 Fixing Kochi state mismatch...")
    
    # First, let's see what states exist
    print("📋 Available states:")
    all_states = State.objects.all()
    for state in all_states:
        print(f"   - {state.name} (slug: {state.slug})")
    
    # Check for both possible state slugs
    kerela_state = None
    kerala_state = None
    
    try:
        kerela_state = State.objects.get(slug='kerela')
        print(f"✅ Found kerela state: {kerela_state.name}")
    except State.DoesNotExist:
        print("❌ kerela state not found")
    
    try:
        kerala_state = State.objects.get(slug='kerala')
        print(f"✅ Found kerala state: {kerala_state.name}")
    except State.DoesNotExist:
        print("❌ kerala state not found")
    
    # Check where Kochi city is located
    print("\n🔍 Looking for Kochi city...")
    kochi_cities = City.objects.filter(slug='kochi')
    for city in kochi_cities:
        print(f"   - Kochi in {city.state_ref.name} (slug: {city.state_ref.slug})")
    
    if not kerela_state and not kerala_state:
        print("❌ Neither kerela nor kerala state found!")
        return
    
    if not kochi_cities.exists():
        print("❌ No Kochi city found!")
        return
    
    # If we have both states and Kochi is in kerela, move it to kerala
    if kerela_state and kerala_state:
        kochi_in_kerela = kochi_cities.filter(state_ref=kerela_state).first()
        if kochi_in_kerela:
            print(f"\n📍 Moving Kochi from {kerela_state.name} to {kerala_state.name}")
            
            with transaction.atomic():
                kochi_in_kerela.state_ref = kerala_state
                kochi_in_kerela.save()
                print(f"✅ Updated city state_ref to {kerala_state.name}")
                
                # Count related objects
                data_layers = DataLayer.objects.filter(city=kochi_in_kerela).count()
                geo_features = GeoFeature.objects.filter(layer__city=kochi_in_kerela).count()
                layer_styles = CityLayerStyle.objects.filter(city=kochi_in_kerela).count()
                layer_groups = LayerGroup.objects.filter(city=kochi_in_kerela).count()
                zone_mappings = CityZoneMapping.objects.filter(city=kochi_in_kerela).count()
                
                print(f"📊 Related objects:")
                print(f"   - DataLayers: {data_layers}")
                print(f"   - GeoFeatures: {geo_features}")
                print(f"   - CityLayerStyles: {layer_styles}")
                print(f"   - LayerGroups: {layer_groups}")
                print(f"   - CityZoneMappings: {zone_mappings}")
                
                print("✅ Successfully moved Kochi data to kerala state")
        else:
            print("ℹ️  Kochi is not in kerela state, no action needed")
    
    # If we only have kerala state, check if Kochi is already there
    elif kerala_state:
        kochi_in_kerala = kochi_cities.filter(state_ref=kerala_state).first()
        if kochi_in_kerala:
            print("✅ Kochi is already in kerala state!")
        else:
            print("❌ Kochi is not in kerala state, but kerela state doesn't exist")
    
    # If we only have kerela state, we need to rename it to kerala
    elif kerela_state:
        print("❌ Only kerela state exists, but kerala state is needed for S3 tiles")
        print("💡 Renaming kerela state to kerala to match S3 tile paths...")
        
        with transaction.atomic():
            # Rename the state slug from kerela to kerala
            kerela_state.slug = 'kerala'
            kerela_state.save()
            print(f"✅ Renamed state slug from 'kerela' to 'kerala'")
            
            # Count related objects
            cities = City.objects.filter(state_ref=kerela_state).count()
            data_layers = DataLayer.objects.filter(city__state_ref=kerela_state).count()
            geo_features = GeoFeature.objects.filter(layer__city__state_ref=kerela_state).count()
            layer_styles = CityLayerStyle.objects.filter(city__state_ref=kerela_state).count()
            layer_groups = LayerGroup.objects.filter(city__state_ref=kerela_state).count()
            zone_mappings = CityZoneMapping.objects.filter(city__state_ref=kerela_state).count()
            
            print(f"📊 Related objects in renamed state:")
            print(f"   - Cities: {cities}")
            print(f"   - DataLayers: {data_layers}")
            print(f"   - GeoFeatures: {geo_features}")
            print(f"   - CityLayerStyles: {layer_styles}")
            print(f"   - LayerGroups: {layer_groups}")
            print(f"   - CityZoneMappings: {zone_mappings}")
            
            print("✅ Successfully renamed kerela state to kerala")

if __name__ == "__main__":
    fix_kochi_state()
