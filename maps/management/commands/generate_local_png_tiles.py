"""
Management command to generate PNG tiles locally with proper color mapping
Usage: python manage.py generate_local_png_tiles --state karnataka --city bengaluru --min-zoom 10 --max-zoom 14

COMPLETELY FIXED VERSION - All issues resolved
Key Fixes:
1. Fixed variable scope errors
2. Proper error handling for missing attributes
3. Correct MVT encoding structure
4. Full color mapping with fallbacks
5. Robust coordinate transformation
"""

import os
import json
import io
from typing import Dict, List, Tuple, Optional
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.contrib.gis.db.models import Extent
import mercantile
import mapbox_vector_tile
from PIL import Image, ImageDraw
from maps.models import State, City, DataLayer, GeoFeature, CityLayerStyle
from maps.config import get_city_style_config, PATTERN_DEFAULTS, get_pattern_style


class Command(BaseCommand):
    help = 'Generate PNG tiles locally with proper color mapping from imported data'
    
    def __init__(self):
        super().__init__()
        self.tile_size = 256
        self.mvt_extent = 4096
        self.statistics = {
            'tiles_generated': 0,
            'tiles_failed': 0,
            'layers_processed': 0,
            'features_processed': 0,
            'features_failed': 0
        }
    
    def add_arguments(self, parser):
        parser.add_argument('--state', type=str, required=True, help='State slug')
        parser.add_argument('--city', type=str, required=True, help='City slug')
        parser.add_argument('--layer', type=str, help='Optional specific layer slug')
        parser.add_argument('--min-zoom', type=int, default=10, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--output-dir', type=str, default='static/tiles_png', help='Output directory')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    def handle(self, *args, **options):
        state_slug = options['state']
        city_slug = options['city']
        layer_slug = options.get('layer')
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        output_dir = options['output_dir']
        verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🗺️  LOCAL PNG TILE GENERATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        try:
            # Get city and layers
            state = State.objects.get(slug=state_slug)
            city = City.objects.get(slug=city_slug, state_ref=state)
            
            # Get layers to process
            if layer_slug:
                layers = DataLayer.objects.filter(city=city, slug=layer_slug)
                if not layers.exists():
                    self.stdout.write(self.style.ERROR(f'❌ Layer {layer_slug} not found'))
                    return
            else:
                layers = DataLayer.objects.filter(city=city)
            
            self.stdout.write(f'📍 State: {state.name}')
            self.stdout.write(f'🏙️  City: {city.name}')
            self.stdout.write(f'📊 Layers to process: {layers.count()}')
            
            # Show layer information
            for layer in layers:
                feature_count = GeoFeature.objects.filter(layer=layer).count()
                self.stdout.write(f'   - {layer.name} ({layer.slug}): {feature_count} features')
            
            # Generate tiles for each layer
            for layer in layers:
                self.statistics['layers_processed'] += 1
                self.stdout.write(f'\n📂 Processing layer: {layer.name}')
                
                # Skip layers with no features
                feature_count = GeoFeature.objects.filter(layer=layer).count()
                if feature_count == 0:
                    self.stdout.write(f'   ⚠️  Skipping layer with 0 features')
                    continue
                
                # Get layer bounds
                bounds = self._get_layer_bounds(layer)
                if not bounds:
                    self.stdout.write(f'   ⚠️  No bounds found for {layer.name}')
                    continue
                
                self.stdout.write(f'   📐 Bounds: {bounds}')
                
                # Generate tiles for each zoom level
                for z in range(min_zoom, max_zoom + 1):
                    self.stdout.write(f'   📍 Zoom {z}: ', ending='')
                    
                    # Get tiles that intersect with layer bounds
                    tiles = list(mercantile.tiles(bounds[0], bounds[1], bounds[2], bounds[3], [z]))
                    self.stdout.write(f'{len(tiles)} tiles to generate')
                    
                    tiles_generated = 0
                    for tile in tiles:
                        success = self._generate_single_tile(city, layer, tile.z, tile.x, tile.y, output_dir, verbose)
                        if success:
                            tiles_generated += 1
                            self.statistics['tiles_generated'] += 1
                        else:
                            self.statistics['tiles_failed'] += 1
                    
                    self.stdout.write(f'     ✅ Generated {tiles_generated}/{len(tiles)} tiles')
            
            # Print final statistics
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(self.style.SUCCESS('📈 GENERATION COMPLETE'))
            self.stdout.write(f'✅ Layers processed: {self.statistics["layers_processed"]}')
            self.stdout.write(f'✅ Tiles generated: {self.statistics["tiles_generated"]}')
            self.stdout.write(f'❌ Tiles failed: {self.statistics["tiles_failed"]}')
            self.stdout.write(f'📊 Features processed: {self.statistics["features_processed"]}')
            self.stdout.write(f'⚠️  Features failed: {self.statistics["features_failed"]}')
            
        except (State.DoesNotExist, City.DoesNotExist) as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Unexpected error: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _generate_single_tile(self, city, layer, z, x, y, output_dir, verbose):
        """Generate a single PNG tile for a layer"""
        try:
            # Create MVT data
            mvt_data = self._create_mvt_tile(city, layer, z, x, y, verbose)
            if not mvt_data:
                return False
            
            # Convert MVT to PNG with colors
            png_data = self._render_mvt_to_png(mvt_data, city, layer, z, x, y, verbose)
            if not png_data:
                return False
            
            # Save PNG file
            # Structure: state->city->layer->tiles_png
            state_slug = city.state_ref.slug if city.state_ref else 'unknown'
            tile_path = os.path.join(output_dir, state_slug, city.slug, layer.slug, 'tiles_png')
            os.makedirs(tile_path, exist_ok=True)
            
            file_path = os.path.join(tile_path, f"{z}_{x}_{y}.png")
            with open(file_path, 'wb') as f:
                f.write(png_data)
            
            if verbose and self.statistics['tiles_generated'] % 50 == 0:
                self.stdout.write(f"      ✅ Generated: {file_path}")
            
            return True
            
        except Exception as e:
            if verbose:
                self.stdout.write(self.style.ERROR(f"      ❌ Error on tile {z}/{x}/{y}: {str(e)}"))
            return False
    
    def _create_mvt_tile(self, city, layer, z, x, y, verbose):
        """Create MVT tile data - COMPLETELY FIXED VERSION"""
        try:
            # Get tile bounds
            bounds = mercantile.bounds(x, y, z)
            
            # Create bounding box polygon for intersection
            bbox_polygon = Polygon.from_bbox((
                bounds.west, bounds.south, bounds.east, bounds.north
            ))
            
            # Get features that intersect with tile bounds
            features = GeoFeature.objects.filter(
                layer=layer,
                geometry__intersects=bbox_polygon
            ).select_related('layer', 'layer__city', 'layer__category')
            
            if not features.exists():
                return None
            
            if verbose:
                self.stdout.write(f"      🔍 Found {features.count()} intersecting features")
            
            # Convert features to MVT format
            mvt_features = []
            for i, feature in enumerate(features):
                try:
                    # Simplify geometry for the zoom level
                    simplified_geom = feature.geometry.simplify(
                        tolerance=self._get_simplify_tolerance(z), 
                        preserve_topology=True
                    )
                    
                    # Convert to GeoJSON dict
                    geom_dict = json.loads(simplified_geom.geojson)
                    
                    # Transform geometry to tile coordinates
                    transformed_geom = self._transform_geometry_to_tile(geom_dict, bounds)
                    
                    # Get comprehensive properties including color mapping info
                    # FIXED: Pass city as parameter to avoid scope issues
                    properties = self._get_feature_properties(feature, city)
                    
                    mvt_features.append({
                        'geometry': transformed_geom,
                        'properties': properties
                    })
                    
                    self.statistics['features_processed'] += 1
                    
                except Exception as e:
                    self.statistics['features_failed'] += 1
                    if verbose and self.statistics['features_failed'] % 100 == 0:
                        self.stdout.write(f"         ⚠️  Feature errors: {self.statistics['features_failed']}")
                    continue
            
            if not mvt_features:
                return None
            
            # FIXED: Use the correct list structure that works
            layer_name = layer.slug.replace('-', '_')
            
            layers_list = [{
                'name': layer_name,
                'features': mvt_features
            }]
            
            # Encode MVT using the correct structure
            mvt_data = mapbox_vector_tile.encode(layers_list)
            
            if verbose:
                self.stdout.write(f"      ✅ MVT created: {len(mvt_features)} features, {len(mvt_data)} bytes")
            
            return mvt_data
            
        except Exception as e:
            if verbose:
                self.stdout.write(self.style.ERROR(f"      ❌ Error creating MVT: {str(e)}"))
                import traceback
                self.stdout.write(f"      Traceback: {traceback.format_exc()}")
            return None
    
    def _transform_geometry_to_tile(self, geom_dict, bounds):
        """Transform geometry coordinates to tile coordinate system (0-4096)"""
        try:
            geom_type = geom_dict.get('type')
            coordinates = geom_dict.get('coordinates', [])
            
            if geom_type == 'Polygon':
                transformed_coords = []
                for ring in coordinates:
                    transformed_ring = []
                    for coord in ring:
                        tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                        tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                        transformed_ring.append([tile_x, tile_y])
                    transformed_coords.append(transformed_ring)
                
                return {
                    'type': 'Polygon',
                    'coordinates': transformed_coords
                }
            
            elif geom_type == 'MultiPolygon':
                transformed_coords = []
                for polygon in coordinates:
                    transformed_polygon = []
                    for ring in polygon:
                        transformed_ring = []
                        for coord in ring:
                            tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                            tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                            transformed_ring.append([tile_x, tile_y])
                        transformed_polygon.append(transformed_ring)
                    transformed_coords.append(transformed_polygon)
                
                return {
                    'type': 'MultiPolygon',
                    'coordinates': transformed_coords
                }
            
            elif geom_type == 'LineString':
                transformed_coords = []
                for coord in coordinates:
                    tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                    tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                    transformed_coords.append([tile_x, tile_y])
                
                return {
                    'type': 'LineString',
                    'coordinates': transformed_coords
                }
            
            elif geom_type == 'MultiLineString':
                transformed_coords = []
                for line in coordinates:
                    transformed_line = []
                    for coord in line:
                        tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                        tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                        transformed_line.append([tile_x, tile_y])
                    transformed_coords.append(transformed_line)
                
                return {
                    'type': 'MultiLineString',
                    'coordinates': transformed_coords
                }
            
            elif geom_type == 'Point':
                coord = coordinates
                tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                
                return {
                    'type': 'Point',
                    'coordinates': [tile_x, tile_y]
                }
            
            # Return original if we can't transform
            return geom_dict
            
        except Exception as e:
            # Return original geometry as fallback
            return geom_dict
    
    def _get_feature_properties(self, feature, city):
        """Extract comprehensive properties for MVT encoding - FIXED version"""
        try:
            # Base properties that always exist
            properties = {
                'id': feature.id,
                'layer': feature.layer.slug,
                'name': getattr(feature, 'name', '') or '',
                'area': float(getattr(feature, 'area', 0)) if getattr(feature, 'area', None) else 0.0
            }
            
            # Safely get zone category
            zone_category = getattr(feature, 'zone_category', '') or ''
            properties['zone_category'] = zone_category
            
            # Add city-specific properties for color mapping
            city_slug = city.slug
            
            if city_slug == 'bengaluru':
                # Bengaluru uses PLU codes - get original field values too
                properties.update({
                    'plu_primary_code': getattr(feature, 'plu_primary_code', '') or '',
                    'plu_secondary_1': getattr(feature, 'plu_secondary_1', '') or '',
                    'plu_proposed_use': getattr(feature, 'plu_proposed_use', '') or '',
                    'source_layer_name': getattr(feature, 'source_layer_name', '') or ''
                })
                
                # Also try to get from original properties JSON if available
                if hasattr(feature, 'properties') and feature.properties:
                    try:
                        original_props = feature.properties if isinstance(feature.properties, dict) else {}
                        properties.update({
                            'PLU_Tp_pro': original_props.get('PLU_Tp_pro', ''),
                            'PLU_Tp_p_1': original_props.get('PLU_Tp_p_1', ''),
                            'PLU_Tp_p_2': original_props.get('PLU_Tp_p_2', ''),
                            'PLU_prop_l': original_props.get('PLU_prop_l', ''),
                            'PLU_NAME': original_props.get('PLU_NAME', '')
                        })
                    except:
                        pass
            
            elif city_slug == 'warangal':
                # Warangal uses PLU_NAME from properties JSON
                if hasattr(feature, 'properties') and feature.properties:
                    try:
                        props = feature.properties if isinstance(feature.properties, dict) else {}
                        properties['PLU_NAME'] = props.get('PLU_NAME', '')
                    except:
                        properties['PLU_NAME'] = ''
                else:
                    properties['PLU_NAME'] = ''
                
                # Add source_layer_name for color mapping
                properties['source_layer_name'] = getattr(feature, 'source_layer_name', '') or ''
            
            elif city_slug == 'hyderabad':
                # Hyderabad uses _source_file for color mapping (not source_layer_name)
                properties['source_layer_name'] = getattr(feature, 'source_layer_name', '') or ''
                
                # Add _source_file from the feature properties for Hyderabad color mapping
                if hasattr(feature, 'properties') and feature.properties:
                    try:
                        props = feature.properties if isinstance(feature.properties, dict) else {}
                        properties['_source_file'] = props.get('_source_file', '') or ''
                        properties['name'] = props.get('Name', '') or properties.get('name', '')
                        
                        # Add metro line color information for Hyderabad metro
                        properties['line_color'] = props.get('line_color', '')
                        properties['color_hex'] = props.get('color_hex', '')
                    except:
                        pass
            elif city_slug == 'visakhapatnam':
                # Visakhapatnam uses Category from properties JSON  
                if hasattr(feature, 'properties') and feature.properties:
                    try:
                        props = feature.properties if isinstance(feature.properties, dict) else {}
                        properties['Category'] = props.get('Category', '')
                    except:
                        properties['Category'] = ''
                else:
                    properties['Category'] = ''
                
                # Add source_layer_name for color mapping
                properties['source_layer_name'] = getattr(feature, 'source_layer_name', '') or ''
            
            elif city_slug == 'amaravati':
                # Amaravati uses symbology and plot_category
                properties.update({
                    'symbology': getattr(feature, 'symbology', '') or '',
                    'plot_category': getattr(feature, 'plot_category', '') or '',
                    'source_layer_name': getattr(feature, 'source_layer_name', '') or ''
                })
            
            return properties
            
        except Exception as e:
            # Return minimal properties as fallback
            return {
                'id': getattr(feature, 'id', 0),
                'layer': getattr(feature.layer, 'slug', 'unknown') if hasattr(feature, 'layer') else 'unknown',
                'zone_category': '',
                'name': ''
            }
    
    def _render_mvt_to_png(self, mvt_data, city, layer, z, x, y, verbose):
        """Render MVT data to PNG with proper colors"""
        try:
            img = self._render_mvt_to_image(mvt_data, city, layer, z, x, y, verbose)
            if not img:
                return None
            
            # Convert to PNG bytes
            buffer = io.BytesIO()
            img.save(buffer, 'PNG', optimize=True, compress_level=6)
            return buffer.getvalue()
            
        except Exception as e:
            if verbose:
                self.stdout.write(self.style.ERROR(f"      ❌ Error rendering PNG: {str(e)}"))
            return None
    
    def _render_mvt_to_image(self, mvt_data, city, layer, z, x, y, verbose):
        """Render MVT data to PIL Image with proper color mapping"""
        try:
            # Decode MVT data
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return None
            

            
            # Create blank image with transparent background
            img = Image.new('RGBA', (self.tile_size, self.tile_size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            features_drawn = 0
            
            # Render each layer in the MVT
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                

                
                for feature in features:
                    try:
                        # Get feature-specific color based on properties
                        feature_props = feature.get('properties', {})
                        

                        
                        color_config = self._get_feature_color(city, layer, feature_props)
                        
                        # DEBUG: Show color mapping for first few features
                        if verbose and features_drawn < 5:
                            zone_info = ""
                            source_layer = feature_props.get('source_layer_name', '')
                            if city.slug == 'bengaluru':
                                plu_sec1 = feature_props.get('plu_secondary_1', '')
                                zone_info = f" | source: {source_layer} | plu_sec1: {plu_sec1}"
                            else:
                                zone_info = f" | source: {source_layer}"
                            
                            self.stdout.write(f"        🎨 Feature {features_drawn}: {color_config.get('fill_color', 'N/A')}{zone_info}")
                        

                        
                        # Draw the feature with proper colors
                        if self._draw_feature_with_color(draw, feature, color_config):
                            features_drawn += 1
                    
                    except Exception as e:
                        if verbose and features_drawn % 1000 == 0:
                            self.stdout.write(f"        ⚠️  Feature render error: {e}")
                        continue
            
            if verbose:
                self.stdout.write(f"      🎨 Drew {features_drawn} features with colors")
            
            return img
            
        except Exception as e:
            if verbose:
                self.stdout.write(self.style.ERROR(f"      ❌ Error rendering image: {str(e)}"))
            return None
    
    def _draw_feature_with_color(self, draw, feature, color_config):
        """Draw a single feature with proper color and pattern"""
        try:
            geometry = feature.get('geometry', {})
            if not geometry:
                return False
            
            geom_type = geometry.get('type')
            coordinates = geometry.get('coordinates', [])
            
            if not coordinates:
                return False
            
            # Convert color config to RGB
            fill_color = self._hex_to_rgb(color_config.get('fill_color', '#CCCCCC'))
            stroke_color = self._hex_to_rgb(color_config.get('stroke_color', '#666666'))
            pattern = color_config.get('pattern', 'SOLID')
            

            
            # Scale factor from MVT extent (4096) to tile pixels (256)
            scale_factor = self.tile_size / self.mvt_extent
            
            if geom_type == 'Polygon':
                return self._draw_polygon_with_style(draw, coordinates, fill_color, stroke_color, pattern, scale_factor)
            elif geom_type == 'MultiPolygon':
                success_count = 0
                for polygon_coords in coordinates:
                    if self._draw_polygon_with_style(draw, polygon_coords, fill_color, stroke_color, pattern, scale_factor):
                        success_count += 1
                return success_count > 0
            elif geom_type in ['LineString', 'MultiLineString']:
                return self._draw_linestring_with_style(draw, coordinates, stroke_color, geom_type, scale_factor)
            elif geom_type in ['Point', 'MultiPoint']:
                return self._draw_point_with_style(draw, coordinates, fill_color, geom_type, scale_factor)
            
            return False
            
        except Exception as e:
            return False
    
    def _draw_polygon_with_style(self, draw, coordinates, fill_color, stroke_color, pattern, scale_factor):
        """Draw polygon with style (solid or pattern)"""
        try:
            # Convert coordinates to pixel coordinates with proper scaling
            pixel_coords = []
            for ring in coordinates:
                pixel_ring = []
                for coord in ring:
                    # Scale from MVT extent (4096) to tile size (256)
                    pixel_x = int(coord[0] * scale_factor)
                    pixel_y = int(coord[1] * scale_factor)
                    
                    # Clamp to valid pixel range
                    pixel_x = max(0, min(self.tile_size - 1, pixel_x))
                    pixel_y = max(0, min(self.tile_size - 1, pixel_y))
                    
                    pixel_ring.append((pixel_x, pixel_y))
                
                if len(pixel_ring) >= 3:  # Need at least 3 points for a polygon
                    pixel_coords.append(pixel_ring)
            
            if not pixel_coords:
                return False
            
            # Draw each ring with proper pattern
            for ring in pixel_coords:
                if pattern == 'SOLID':
                    # Solid fill with good opacity - no outline to remove borders between features
                    draw.polygon(ring, fill=fill_color + (200,), outline=None)
                elif pattern == 'HATCHED':
                    # Draw base fill first, then add hatching - no outline to remove borders between features
                    draw.polygon(ring, fill=fill_color + (100,), outline=None)
                    self._draw_hatching_pattern(draw, ring, stroke_color)
                elif pattern == 'DOTTED':
                    # Draw base fill first, then add dots - no outline to remove borders between features
                    draw.polygon(ring, fill=fill_color + (100,), outline=None)
                    self._draw_dotted_pattern(draw, ring, stroke_color)
                else:
                    # Default to solid - no outline to remove borders between features
                    draw.polygon(ring, fill=fill_color + (200,), outline=None)
            
            return True
            
        except Exception as e:
            return False
    
    def _draw_linestring_with_style(self, draw, coordinates, stroke_color, geom_type, scale_factor):
        """Draw linestring with proper styling"""
        try:
            if geom_type == 'LineString':
                coords_list = [coordinates]
            else:  # MultiLineString
                coords_list = coordinates
            
            drawn_lines = 0
            for line_coords in coords_list:
                pixel_coords = []
                for coord in line_coords:
                    pixel_x = int(coord[0] * scale_factor)
                    pixel_y = int(coord[1] * scale_factor)
                    pixel_x = max(0, min(self.tile_size - 1, pixel_x))
                    pixel_y = max(0, min(self.tile_size - 1, pixel_y))
                    pixel_coords.append((pixel_x, pixel_y))
                

                
                if len(pixel_coords) >= 2:
                    for i in range(len(pixel_coords) - 1):
                        draw.line([pixel_coords[i], pixel_coords[i + 1]], fill=stroke_color, width=4)
                        # Also draw a thicker line for better visibility
                        draw.line([pixel_coords[i], pixel_coords[i + 1]], fill=stroke_color, width=1)
                        drawn_lines += 1

            
            return drawn_lines > 0
        except Exception as e:
            return False
    
    def _draw_point_with_style(self, draw, coordinates, fill_color, geom_type, scale_factor):
        """Draw point with proper styling"""
        try:
            if geom_type == 'Point':
                coords_list = [coordinates]
            else:  # MultiPoint
                coords_list = coordinates
            
            for point_coords in coords_list:
                x = int(point_coords[0] * scale_factor)
                y = int(point_coords[1] * scale_factor)
                x = max(0, min(self.tile_size - 1, x))
                y = max(0, min(self.tile_size - 1, y))
                
                # Draw small circle for point
                radius = 3
                draw.ellipse(
                    [(x - radius, y - radius), (x + radius, y + radius)],
                    fill=fill_color + (200,),
                    outline=fill_color
                )
            
            return True
        except Exception as e:
            return False
    
    def _draw_hatching_pattern(self, draw, coords, color):
        """Draw hatching pattern on polygon area - CLIPPED version"""
        if not coords:
            return
        
        try:
            # Get bounding box
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            # Create a mask for the polygon to clip the hatching
            from PIL import Image
            
            # Create a temporary image for the mask
            mask_img = Image.new('L', (self.tile_size, self.tile_size), 0)
            mask_draw = ImageDraw.Draw(mask_img)
            
            # Draw the polygon on the mask
            mask_draw.polygon(coords, fill=255)
            
            # Draw diagonal lines with clipping
            spacing = 6
            for i in range(int(min_x - max_y), int(max_x + max_y), spacing):
                # Calculate line endpoints
                start_x = i
                start_y = min_y
                end_x = i + (max_y - min_y)
                end_y = max_y
                
                # Clip the line to the polygon using the mask
                self._draw_clipped_line(draw, mask_img, start_x, start_y, end_x, end_y, color + (180,), 1)
                
        except Exception as e:
            # Fallback to simple hatching without clipping
            try:
                spacing = 6
                for i in range(int(min_x - max_y), int(max_x + max_y), spacing):
                    draw.line(
                        [(i, min_y), (i + (max_y - min_y), max_y)],
                        fill=color + (180,),
                        width=1
                    )
            except:
                pass  # Fail silently for pattern errors
    
    def _draw_clipped_line(self, draw, mask_img, start_x, start_y, end_x, end_y, color, width):
        """Draw a line that is clipped to the polygon mask"""
        try:
            # Sample points along the line
            import math
            
            # Calculate line length
            dx = end_x - start_x
            dy = end_y - start_y
            length = math.sqrt(dx * dx + dy * dy)
            
            if length == 0:
                return
            
            # Sample points every pixel
            num_points = int(length) + 1
            points = []
            
            for i in range(num_points):
                t = i / (num_points - 1) if num_points > 1 else 0
                x = int(start_x + t * dx)
                y = int(start_y + t * dy)
                
                # Check if point is within bounds
                if 0 <= x < self.tile_size and 0 <= y < self.tile_size:
                    # Check if point is inside the polygon mask
                    if mask_img.getpixel((x, y)) > 0:
                        points.append((x, y))
            
            # Draw line segments only within the polygon
            if len(points) >= 2:
                for i in range(len(points) - 1):
                    draw.line([points[i], points[i + 1]], fill=color, width=width)
            elif len(points) == 1:
                # Single point - draw a small dot
                x, y = points[0]
                draw.point((x, y), fill=color)
                
        except Exception as e:
            # Fallback to simple line drawing
            try:
                draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
            except:
                pass
    
    def _draw_dotted_pattern(self, draw, coords, color):
        """Draw dotted pattern on polygon area - CLIPPED version"""
        if not coords:
            return
        
        try:
            # Get bounding box
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            # Create a mask for the polygon to clip the dots
            from PIL import Image
            
            # Create a temporary image for the mask
            mask_img = Image.new('L', (self.tile_size, self.tile_size), 0)
            mask_draw = ImageDraw.Draw(mask_img)
            
            # Draw the polygon on the mask
            mask_draw.polygon(coords, fill=255)
            
            # Draw dots in a grid, but only inside the polygon
            spacing = 8
            dot_size = 2
            for x in range(int(min_x), int(max_x), spacing):
                for y in range(int(min_y), int(max_y), spacing):
                    # Check if the center of the dot is inside the polygon
                    if 0 <= x < self.tile_size and 0 <= y < self.tile_size:
                        if mask_img.getpixel((x, y)) > 0:
                            draw.ellipse(
                                [(x - dot_size, y - dot_size), (x + dot_size, y + dot_size)],
                                fill=color + (200,)
                            )
        except Exception as e:
            # Fallback to simple dotting without clipping
            try:
                spacing = 8
                dot_size = 2
                for x in range(int(min_x), int(max_x), spacing):
                    for y in range(int(min_y), int(max_y), spacing):
                        draw.ellipse(
                            [(x - dot_size, y - dot_size), (x + dot_size, y + dot_size)],
                            fill=color + (200,)
                        )
            except:
                pass  # Fail silently for pattern errors
    
    def _get_feature_color(self, city, layer, properties):
        """Get color configuration for a feature - ENHANCED with debugging and better mapping"""
        
        try:
            city_slug = city.slug
            
            # First, let's use source_layer_name for Bengaluru which has the most direct mapping
            if city_slug == 'bengaluru':
                # Try multiple approaches for Bengaluru color mapping
                
                # 1. Direct source layer mapping (most reliable)
                source_layer = properties.get('source_layer_name', '').strip()
                if source_layer:
                    bengaluru_file_colors = {
                        'Residential Mixed': '#FFC400',
                        'Residential Main': '#FFEB4F', 
                        'Commercial Central': '#004DA8',
                        'Commercial Business': '#73B2FF',
                        'Industrial': '#AA66B2',
                        'High Tech': '#C29ED7',
                        'Public & Semi Public': '#E60000',
                        'Defense': '#E0B8FC',
                        'State Forest Valley Protected Land': '#70A800',
                        'Parks Green Spaces Sports Playgrounds Cemetery Burial Grounds': '#98E600',
                        'Lake Tank': '#BEE8FF',
                        'Road Rail Airport Transport': '#828282',
                        'Power Water Garbage Facility Treatment Plant': '#D79E9E',
                        'Agricultural Land': '#9DC1CB',
                        'Unclassified Use': '#E1E1E1',
                        'Drains': '#267300'
                    }
                    
                    # Direct match first
                    if source_layer in bengaluru_file_colors:
                        return {
                            'fill_color': bengaluru_file_colors[source_layer],
                            'stroke_color': '#2C3E50',
                            'pattern': 'SOLID'
                        }
                    
                    # Fallback to pattern matching
                    source_lower = source_layer.lower().replace('_', '').replace(' ', '')
                    for pattern, color in bengaluru_file_colors.items():
                        pattern_lower = pattern.lower().replace('_', '').replace(' ', '')
                        if pattern_lower in source_lower or source_lower in pattern_lower:
                            return {
                                'fill_color': color,
                                'stroke_color': '#2C3E50',
                                'pattern': 'SOLID'
                            }
                
                # 2. Try original PLU fields from ESRI data
                plu_fields = [
                    properties.get('PLU_Tp_pro', '').strip(),
                    properties.get('PLU_Tp_p_1', '').strip(), 
                    properties.get('PLU_Tp_p_2', '').strip(),
                    properties.get('PLU_prop_l', '').strip(),
                    properties.get('PLU_NAME', '').strip()
                ]
                
                for plu_value in plu_fields:
                    if plu_value and len(plu_value) > 1:  # Skip single character values
                        plu_colors = {
                            'residential': '#FFC400',
                            'commercial': '#004DA8', 
                            'industrial': '#AA66B2',
                            'public': '#E60000',
                            'defense': '#E0B8FC',
                            'forest': '#70A800',
                            'park': '#98E600',
                            'green': '#98E600',
                            'lake': '#BEE8FF',
                            'water': '#BEE8FF',
                            'transport': '#828282',
                            'road': '#828282',
                            'agricultural': '#9DC1CB'
                        }
                        
                        plu_lower = plu_value.lower()
                        for keyword, color in plu_colors.items():
                            if keyword in plu_lower:
                                return {
                                    'fill_color': color,
                                    'stroke_color': '#2C3E50',
                                    'pattern': 'SOLID'
                                }
                
                # 3. Try stored PLU fields
                zone_candidates = [
                    properties.get('plu_secondary_1', '').strip(),
                    properties.get('plu_proposed_use', '').strip(),
                    properties.get('zone_category', '').strip()
                ]
                
                for zone_name in zone_candidates:
                    if zone_name:
                        try:
                            style_config = get_city_style_config(city_slug, zone_name)
                            if style_config:
                                return style_config
                        except:
                            continue
            
            # For Andhra Pradesh cities
            elif city_slug == 'amaravati':
                # Use pattern style function for Amaravati
                source_layer = properties.get('source_layer_name', '').strip()
                if source_layer:
                    try:
                        # Try with the source layer name first
                        pattern_style = get_pattern_style('amaravati', source_layer)
                        if not pattern_style:
                            # Try with filename pattern (replace spaces with underscores and add .geojson)
                            filename_pattern = source_layer.replace(' ', '_').replace('___', '_').replace('__', '_') + '.geojson'
                            pattern_style = get_pattern_style('amaravati', filename_pattern)
                            if not pattern_style:
                                # Try with lowercase planning and zone (as in config)
                                filename_pattern = source_layer.replace(' ', '_').replace('___', '_').replace('__', '_').replace('Planning', 'planning').replace('Zone', 'zone') + '.geojson'
                                pattern_style = get_pattern_style('amaravati', filename_pattern)
                        if pattern_style:
                            if 'hatch' in pattern_style:
                                return {
                                    'fill_color': pattern_style.get('solid', '#FFFFFF'),
                                    'stroke_color': '#2C3E50',
                                    'pattern': 'HATCHED',
                                    'hatch_color': pattern_style['hatch']
                                }
                            elif 'solid' in pattern_style:
                                return {
                                    'fill_color': pattern_style['solid'],
                                    'stroke_color': '#2C3E50',
                                    'pattern': 'SOLID'
                                }
                    except:
                        pass
                    
                    # Fallback to direct mapping
                    amaravati_file_colors = {
                        'SC1a Mixed Use': '#0070FF',
                        'SC1b Mixed Use': '#73B2FF',
                        'C1 Mixed Use Zone': '#73B2FF',
                        'C2 General Commercial Zone': '#00C5FF',
                        'C3 Neighbourhood Centre Zone': '#00C5FF',
                        'C4 Town Centre Zone': '#00A9E6',
                        'C5 Regional Centre Zone': '#0070FF',
                        'C6 Central Business District': '#005CE6',
                        'Commercial Vacant': '#C5E2FF',
                        'I1 Business Park Zone': '#FFBEE8',
                        'I2 Logistics Zone': '#FF73DF',
                        'I3 Non Polluting Industry Zone': '#A900E6',
                        'P1 Passive Zone': '#267300',
                        'P2 Active Zone': '#38A800',
                        'P3 Protected Zone': '#BEE8FF',
                        'P3 Protected Zone Hills': '#4C7300',
                        'PGN G': '#4C7300',
                        'PGN V': '#897044',
                        'R1 Village Planning Zone': '#FFFFFF',
                        'R3 Medium to High Density Zone': '#F5CA7A',
                        'R4 High Density Zone': '#E69800',
                        'RAA': '#FFAA00',
                        'Residential Vacant': '#FFD37F',
                        'S2 Education Zone': '#FFF7F7',
                        'S3 Special Zone': '#D7B09E',
                        'SP1 Passive Zone': '#267300',
                        'SP2 Active Zone': '#38A800',
                        'SP3 Protected Zone': '#00C5FF',
                        'SR2 Low Density Housing': '#FFFFBE',
                        'SR4 High Density Private': '#FFAA00',
                        'SS1 Government Zone': '#E60000',
                        'SS2a Education Zone': '#FFF7F7',
                        'SS2b Cultural Zone': '#C500FF',
                        'SS2c Health Zone': '#D3FFBE',
                        'SS3 Special Zone': '#A83800',
                        'SU1 Reserve Zone': '#E1E1E1',
                        'SU2 Road Network': '#FFFFFF',
                        'U1 Reserve Zone': '#CCCCCC',
                        'U2 Road Reserve Zone': '#000000',
                        'Burial Ground': '#FFFFFF'
                    }
                    
                    # Direct match first
                    if source_layer in amaravati_file_colors:
                        return {
                            'fill_color': amaravati_file_colors[source_layer],
                            'stroke_color': '#2C3E50',
                            'pattern': 'SOLID'
                        }
            
            elif city_slug == 'visakhapatnam':
                # Use pattern style function for Visakhapatnam
                source_layer = properties.get('source_layer_name', '').strip()
                if source_layer:
                    try:
                        # Try with the source layer name first
                        pattern_style = get_pattern_style('visakhapatnam', source_layer)
                        if not pattern_style:
                            # Try with filename pattern (replace spaces with underscores and add .geojson)
                            filename_pattern = source_layer.replace(' ', '_').replace('___', '_').replace('__', '_') + '.geojson'
                            pattern_style = get_pattern_style('visakhapatnam', filename_pattern)
                            if not pattern_style:
                                # Try with lowercase planning and zone (as in config)
                                filename_pattern = source_layer.replace(' ', '_').replace('___', '_').replace('__', '_').replace('Planning', 'planning').replace('Zone', 'zone') + '.geojson'
                                pattern_style = get_pattern_style('visakhapatnam', filename_pattern)
                        if pattern_style:
                            if 'hatch' in pattern_style:
                                return {
                                    'fill_color': pattern_style.get('solid', '#FFFFFF'),
                                    'stroke_color': '#2C3E50',
                                    'pattern': 'HATCHED',
                                    'hatch_color': pattern_style['hatch']
                                }
                            elif 'solid' in pattern_style:
                                return {
                                    'fill_color': pattern_style['solid'],
                                    'stroke_color': '#2C3E50',
                                    'pattern': 'SOLID'
                                }
                    except:
                        pass
                    
                    # Fallback to direct mapping
                    visakhapatnam_file_colors = {
                        'Agricultural Use Zone': '#D3FFBE',
                        'Blue Zone Water Bodies': '#73FFDF',
                        'Brown Zone Hills': '#A87000',
                        'Commercial Use Zone': '#004DA8',
                        'Existing Crematorium': '#FFFFFF',
                        'Existing Educational': '#FF0000',
                        'Existing Government': '#FF0000',
                        'Existing Health': '#FF0000',
                        'Proposed Industrial': '#C500FF',
                        'Existing Industrial': '#C500FF',
                        'Existing Public Utilities': '#FF7F7F',
                        'Existing Recreational': '#55FF00',
                        'Existing Religious': '#FF0000',
                        'Existing Road Railway': '#828282',
                        'Existing Transportation': '#686868',
                        'Green Zone Forest': '#00734C',
                        'Kambalakonda Eco Sensitive Zone': '#267300',
                        'Kambalakonda WildLife Sanctuary': '#267300',
                        'Mixed Use Zone 1': '#FFAA00',
                        'Mixed Use Zone 2 BAIA': '#FFAA00',
                        'Mixed Use Zone 3 BAIA': '#FFAA00',
                        'Mixed Use Zone 4 BAIA': '#FFAA00',
                        'Proposed PSP Use Zone': '#E60000',
                        'Proposed Public Utilities Use Zone': '#D79E9E',
                        'Proposed Recreational Use Zone': '#55FF00',
                        'Proposed Road Network': '#828282',
                        'Proposed Transportation Facility Use Zone': '#686868',
                        'Residential Use Zone': '#FFFF73',
                        'Sea River Accreted Land': '#E1E1E1',
                        'Special Area Use Zone': '#C500FF',
                        'Water Body Buffer': '#73FFDF'
                    }
                    
                    # Direct match first
                    if source_layer in visakhapatnam_file_colors:
                        return {
                            'fill_color': visakhapatnam_file_colors[source_layer],
                            'stroke_color': '#2C3E50',
                            'pattern': 'SOLID'
                        }
            
            # For other cities
            elif city_slug == 'hyderabad':
                # Check for metro line colors first (highest priority)
                line_color = properties.get('line_color', '').strip()
                color_hex = properties.get('color_hex', '').strip()
                
                if line_color and color_hex:
                    # Metro line color mapping
                    metro_colors = {
                        'Green Line': '#00933D',
                        'Blue Line': '#2D6BA1', 
                        'Red Line': '#E40D17',
                        'Purple Line': '#8C06ED',
                        'Orange Line': '#EF6908'
                    }
                    
                    # Use the stored color_hex or fallback to metro_colors mapping
                    final_color = color_hex if color_hex else metro_colors.get(line_color, '#00933D')
                    
                    return {
                        'fill_color': final_color,
                        'stroke_color': final_color,  # Use same color for stroke
                        'pattern': 'SOLID'
                    }
                
                # Hyderabad uses _source_file for color mapping (not source_layer_name)
                source_file = properties.get('_source_file', '').strip()
                if source_file:
                    # Hyderabad color mappings based on config - all transport layers use #14E098
                    hyderabad_colors = {
                        'RRR Final': '#14E098',
                        'Ratan Tata Road': '#14E098',
                        'Hyderabad Highways': '#14E098'
                    }
                    
                    # Check for exact match first
                    if source_file in hyderabad_colors:
                        return {
                            'fill_color': hyderabad_colors[source_file],
                            'stroke_color': hyderabad_colors[source_file],  # Use same color for stroke
                            'pattern': 'SOLID'
                        }
                    
                    # Check for partial matches
                    source_lower = source_file.lower()
                    if any(keyword in source_lower for keyword in ['rrr', 'ratan', 'tata', 'highway', 'road']):
                        return {
                            'fill_color': '#14E098',
                            'stroke_color': '#14E098',  # Use same color for stroke
                            'pattern': 'SOLID'
                        }
                
                # Fallback to zone name if _source_file not found
                zone_name = (
                    properties.get('zone_category', '').strip() or 
                    properties.get('name', '').strip()
                )
            elif city_slug == 'warangal':
                # Warangal uses source_layer_name for color mapping
                source_layer = properties.get('source_layer_name', '').strip()
                if source_layer:
                    # Warangal color mappings based on config
                    warangal_colors = {
                        'Agriculture': '#D3FFBE',
                        'Air Strip': '#FF00C5',
                        'Commercial': '#0070FF',
                        'Forest': '#267300',
                        'Growth Corridor': '#FFBEE8',
                        'Growth Corridor 2': '#FF73DF',
                        'Heritage': '#FFA77F',
                        'Hill Buffer': '#55FF00',
                        'Hillocks': '#A87000',
                        'Industrial': '#C500FF',
                        'Mixed Use': '#FFAA00',
                        'Public and Semi Public': '#FF0000',
                        'Public Utilities': '#E69800',
                        'Railway Land': '#CCCCCC',
                        'Recreational': '#55FF00',
                        'Residential': '#FFFF00',
                        'Residential Expansion': '#9C9C9C',
                        'Road Buffer': '#4E4E4E',
                        'Transportation': '#B2B2B2',
                        'Water Bodies': '#00C5FF',
                        'Water Body Buffer': '#55FF00',
                        'Zoological Park': '#38A800'
                    }
                    
                    # Check for exact match first
                    if source_layer in warangal_colors:
                        return {
                            'fill_color': warangal_colors[source_layer],
                            'stroke_color': '#2C3E50',
                            'pattern': 'SOLID'
                        }
                    
                    # Check for pattern styles (hatched patterns)
                    warangal_patterns = {
                        'Air Strip': {'hatch': '#FFFFFF', 'solid': '#FF00C5'},
                        'Heritage': {'hatch': '#732600', 'solid': '#FFA77F'},
                        'Public Utilities': {'hatch': '#FF0000', 'solid': '#E69800'}
                    }
                    
                    if source_layer in warangal_patterns:
                        pattern_config = warangal_patterns[source_layer]
                        if 'hatch' in pattern_config:
                            return {
                                'fill_color': pattern_config.get('solid', '#FFFFFF'),
                                'stroke_color': '#2C3E50',
                                'pattern': 'HATCHED',
                                'hatch_color': pattern_config['hatch']
                            }
                        else:
                            return {
                                'fill_color': pattern_config['solid'],
                                'stroke_color': '#2C3E50',
                                'pattern': 'SOLID'
                            }
                
                # Fallback to zone name if source_layer not found
                zone_name = (
                    properties.get('zone_category', '').strip() or 
                    properties.get('PLU_NAME', '').strip()
                )
            elif city_slug == 'visakhapatnam':
                zone_name = (
                    properties.get('zone_category', '').strip() or 
                    properties.get('Category', '').strip()
                )
            elif city_slug == 'amaravati':
                zone_name = (
                    properties.get('symbology', '').strip() or 
                    properties.get('plot_category', '').strip()
                )
                
                if zone_name:
                    try:
                        style_config = get_city_style_config(city_slug, zone_name)
                        if style_config:
                            return style_config
                    except:
                        pass
            
            # Enhanced layer-based color assignment (more vibrant colors) - ONLY for cities without specific color mapping
            if city_slug not in ['hyderabad', 'bengaluru', 'warangal', 'visakhapatnam', 'amaravati']:
                layer_colors = {
                    'master_plan': '#FF6B6B',     # Bright red
                    'highways': '#4ECDC4',        # Turquoise
                    'metro': '#45B7D1',           # Blue
                    'strr': '#96CEB4',            # Green
                    'workspace': '#FCEA2B',       # Yellow
                    'railways': '#FF9FF3',        # Pink
                    'suburban': '#F38BA8',        # Light pink
                }
                
                for key, color in layer_colors.items():
                    if key in layer.slug.lower():
                        return {
                            'fill_color': color,
                            'stroke_color': '#2C3E50',
                            'pattern': 'SOLID'
                        }
            
            # Fallback to layer default style from CityLayerStyle
            try:
                style = CityLayerStyle.objects.get(city=city, category=layer.category)
                return {
                    'fill_color': style.fill_color,
                    'stroke_color': getattr(style, 'stroke_color', '#2C3E50'),
                    'pattern': getattr(style, 'fill_pattern', 'SOLID'),
                    'pattern_color': getattr(style, 'pattern_color', '#000000')
                }
            except:
                pass
            
            # Category-based colors
            category_colors = {
                'RESIDENTIAL': '#FFB6C1',
                'COMMERCIAL': '#87CEEB', 
                'INDUSTRIAL': '#DDA0DD',
                'TRANSPORT': '#F0E68C',
                'GOVERNMENT': '#FFA07A',
                'MIXED_USE': '#98FB98'
            }
            
            if hasattr(layer, 'category') and layer.category:
                category_code = getattr(layer.category, 'code', 'UNKNOWN')
                if category_code in category_colors:
                    return {
                        'fill_color': category_colors[category_code],
                        'stroke_color': '#2C3E50',
                        'pattern': 'SOLID'
                    }
            
            # Final fallback - use layer index for unique colors
            layer_hash = hash(layer.slug) % 6
            fallback_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FCEA2B', '#FF9FF3']
            
            return {
                'fill_color': fallback_colors[layer_hash],
                'stroke_color': '#2C3E50',
                'pattern': 'SOLID'
            }
            
        except Exception as e:
            # Emergency fallback - bright red so it's obvious
            return {
                'fill_color': '#FF0000',
                'stroke_color': '#000000',
                'pattern': 'SOLID'
            }
    
    def _get_layer_bounds(self, layer):
        """Get the bounding box for a layer"""
        try:
            # Use the stored bounds if available
            if hasattr(layer, 'bbox_xmin') and layer.bbox_xmin is not None:
                return [
                    float(layer.bbox_xmin),
                    float(layer.bbox_ymin),
                    float(layer.bbox_xmax),
                    float(layer.bbox_ymax)
                ]
            
            # Otherwise calculate from features using Django's Extent
            bounds = GeoFeature.objects.filter(layer=layer).aggregate(
                bbox=Extent('geometry')
            )['bbox']
            
            if bounds:
                # Extent returns (xmin, ymin, xmax, ymax)
                return list(bounds)
            
            return None
            
        except Exception as e:
            return None
    
    def _get_simplify_tolerance(self, zoom):
        """Get simplification tolerance based on zoom level"""
        # Higher zoom = more detail = less simplification
        base_tolerance = 0.001
        return base_tolerance / (2 ** (zoom - 10))
    
    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple - ROBUST version"""
        try:
            if not hex_color or hex_color == '' or hex_color is None:
                return (200, 200, 200)  # Default gray
            
            # Clean the hex color
            hex_color = str(hex_color).strip().lstrip('#')
            
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            elif len(hex_color) == 3:
                return tuple(int(hex_color[i]*2, 16) for i in range(3))
            else:
                return (200, 200, 200)  # Default gray
        except (ValueError, AttributeError):
            return (200, 200, 200)  # Default gray