# maps/tile_rendering_service.py - Enhanced version with pattern support

import mapbox_vector_tile
from PIL import Image, ImageDraw
import io
import logging
import math
from typing import Dict, Tuple, Optional, Any
from .config import get_city_config, get_pattern_style
from .models import DataLayer

logger = logging.getLogger(__name__)

class TileRenderingService:
    """
    Enhanced service for rendering vector tiles (MVT) as PNG raster images with pattern support.
    Supports solid fills, hatched patterns, dotted patterns, and striped patterns.
    """
    
    def __init__(self):
        self.tile_size = 256  # Standard tile size in pixels
        self.background_color = (255, 255, 255, 0)  # Transparent background
        # Default color mapping for categories
        self.category_colors = {
            'RESIDENTIAL': '#FFC400',
            'COMMERCIAL': '#004DA8',
            'INDUSTRIAL': '#AA66B2',
            'HIGH_TECH': '#C29ED7',
            'PUBLIC': '#E60000',
            'DEFENSE': '#8B4513',
            'PROTECTED': '#228B22',
            'PARKS_GREEN': '#98E600',
            'WATER_BODIES': '#1E90FF',
            'TRANSPORT': '#808080',
            'UTILITIES': '#FF6347',
            'AGRICULTURAL': '#9ACD32',
            'UNCLASSIFIED': '#D3D3D3',
            'DRAINS': '#4682B4',
        }
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except:
            pass
        return (255, 0, 0)  # Red fallback
    
    def _create_pattern_mask(self, size: Tuple[int, int], pattern_config: Dict) -> Image.Image:
        """Create a pattern mask for the given configuration"""
        pattern_type = pattern_config.get('pattern_type', 'SOLID')
        spacing = pattern_config.get('pattern_spacing', 10)
        angle = pattern_config.get('pattern_angle', 45)
        pattern_size = pattern_config.get('pattern_size', 3)
        
        # Create a mask image
        mask = Image.new('L', size, 0)  # Black background
        draw = ImageDraw.Draw(mask)
        
        if pattern_type == 'HATCHED':
            self._draw_hatched_pattern(draw, size, spacing, angle, pattern_size)
        elif pattern_type == 'DOTTED':
            self._draw_dotted_pattern(draw, size, spacing, pattern_size)
        elif pattern_type == 'STRIPED':
            self._draw_striped_pattern(draw, size, spacing, angle, pattern_size)
        elif pattern_type == 'CROSS_HATCHED':
            self._draw_hatched_pattern(draw, size, spacing, angle, pattern_size)
            self._draw_hatched_pattern(draw, size, spacing, angle + 90, pattern_size)
        else:  # SOLID
            draw.rectangle([0, 0, size[0], size[1]], fill=255)
        
        return mask
    
    def _draw_hatched_pattern(self, draw: ImageDraw.Draw, size: Tuple[int, int], 
                              spacing: int, angle: float, line_width: int):
        """Draw hatched lines on the mask"""
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Calculate the diagonal length to ensure full coverage
        diagonal = int(math.sqrt(size[0]**2 + size[1]**2))
        
        # Draw parallel lines
        for i in range(-diagonal, diagonal, spacing):
            # Calculate line endpoints
            x1 = i * cos_a - diagonal * sin_a + size[0]/2
            y1 = i * sin_a + diagonal * cos_a + size[1]/2
            x2 = i * cos_a + diagonal * sin_a + size[0]/2
            y2 = i * sin_a - diagonal * cos_a + size[1]/2
            
            # Draw the line
            draw.line([(x1, y1), (x2, y2)], fill=255, width=line_width)
    
    def _draw_dotted_pattern(self, draw: ImageDraw.Draw, size: Tuple[int, int], 
                             spacing: int, dot_size: int):
        """Draw a grid of dots on the mask"""
        for x in range(spacing//2, size[0], spacing):
            for y in range(spacing//2, size[1], spacing):
                draw.ellipse([x-dot_size, y-dot_size, x+dot_size, y+dot_size], fill=255)
    
    def _draw_striped_pattern(self, draw: ImageDraw.Draw, size: Tuple[int, int], 
                              spacing: int, angle: float, stripe_width: int):
        """Draw striped pattern (thick lines) on the mask"""
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        diagonal = int(math.sqrt(size[0]**2 + size[1]**2))
        
        # Draw stripes (alternating filled areas)
        for i in range(-diagonal, diagonal, spacing * 2):
            points = []
            # Create a polygon for each stripe
            x1 = i * cos_a - diagonal * sin_a + size[0]/2
            y1 = i * sin_a + diagonal * cos_a + size[1]/2
            x2 = i * cos_a + diagonal * sin_a + size[0]/2
            y2 = i * sin_a - diagonal * cos_a + size[1]/2
            x3 = (i + stripe_width) * cos_a + diagonal * sin_a + size[0]/2
            y3 = (i + stripe_width) * sin_a - diagonal * cos_a + size[1]/2
            x4 = (i + stripe_width) * cos_a - diagonal * sin_a + size[0]/2
            y4 = (i + stripe_width) * sin_a + diagonal * cos_a + size[1]/2
            
            points = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
            draw.polygon(points, fill=255)
    
    def _apply_pattern_to_polygon(self, img: Image.Image, polygon_coords: list, 
                                 style_config: Dict, no_border: bool = True):
        """Apply pattern fill to a polygon area"""
        # Get colors
        fill_color = self._hex_to_rgb(style_config.get('fill_color', '#CCCCCC'))
        pattern_color = self._hex_to_rgb(style_config.get('pattern_color', style_config.get('fill_color', '#CCCCCC')))
        secondary_fill = style_config.get('secondary_fill_color', '')
        
        # Create a temporary image for this polygon
        temp_img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Draw secondary fill if specified (solid background)
        if secondary_fill:
            bg_color = self._hex_to_rgb(secondary_fill) + (180,)  # Semi-transparent
            temp_draw.polygon(polygon_coords, fill=bg_color)
        
        # Apply pattern if not solid
        pattern_type = style_config.get('pattern_type', 'SOLID')
        if pattern_type != 'SOLID':
            # Create pattern mask
            pattern_mask = self._create_pattern_mask((self.tile_size, self.tile_size), style_config)
            
            # Create pattern layer
            pattern_layer = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            pattern_draw = ImageDraw.Draw(pattern_layer)
            
            # Draw the pattern color where the mask is white
            pattern_draw.polygon(polygon_coords, fill=pattern_color + (200,))
            
            # Apply the pattern mask
            pattern_layer.putalpha(Image.composite(pattern_layer.split()[-1], 
                                                  Image.new('L', (self.tile_size, self.tile_size), 0), 
                                                  pattern_mask))
            
            # Composite onto temp image
            temp_img = Image.alpha_composite(temp_img, pattern_layer)
        else:
            # Solid fill
            temp_draw.polygon(polygon_coords, fill=fill_color + (180,))
        
        # Draw border if needed (thickness = 0 means no border)
        if not no_border:
            stroke_color = self._hex_to_rgb(style_config.get('stroke_color', '#000000'))
            stroke_width = style_config.get('stroke_width', 1)
            if stroke_width > 0:
                temp_draw.polygon(polygon_coords, outline=stroke_color + (255,), width=stroke_width)
        
        # Composite onto main image
        img.alpha_composite(temp_img)
    
    def render_mvt_to_png_with_patterns(self, mvt_data: bytes, layers: list, 
                                       z: int, x: int, y: int, 
                                       city_slug: str) -> bytes:
        """Render MVT to PNG with pattern support"""
        try:
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self.create_empty_tile()
            
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            
            # Get style configurations for each layer
            layer_styles = {}
            for layer in layers:
                style = layer.get_style()
                if hasattr(style, 'get_pattern_config'):
                    layer_styles[layer.slug] = style.get_pattern_config()
                else:
                    layer_styles[layer.slug] = {
                        'fill_color': style.get('fill_color', '#CCCCCC'),
                        'stroke_color': style.get('stroke_color', '#000000'),
                        'pattern_type': 'SOLID'
                    }
            
            # Process each layer
            features_drawn = 0
            errors = []
            
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                style_config = layer_styles.get(layer_name, {
                    'fill_color': '#CCCCCC',
                    'pattern_type': 'SOLID'
                })
                
                for feature in features:
                    try:
                        if self._draw_feature_with_pattern(img, feature, style_config):
                            features_drawn += 1
                    except Exception as e:
                        errors.append(f"Layer {layer_name}: {str(e)}")
            
            # Log any errors for tracking
            if errors:
                logger.warning(f"Pattern rendering issues at {z}/{x}/{y}: {errors[:5]}")  # Log first 5 errors
            
            logger.info(f"Drew {features_drawn} features with patterns at {z}/{x}/{y}")
            
            # Save with compression
            return self._save_compressed_png(img)
            
        except Exception as e:
            logger.error(f"Error rendering MVT with patterns: {e}")
            return self.create_empty_tile()
    
    def combined_mvt_to_png(self, mvt_data: bytes, layers: list, z: int, x: int, y: int) -> bytes:
        """Render combined MVT to PNG with per-feature styling for combined layers"""
        try:
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self.create_empty_tile()
            
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            
            # Get city config for per-feature styling lookup
            city_config = None
            if layers:
                city = layers[0].city
                city_config = get_city_config(city.state_ref.slug, city.slug)
            
            # Process each layer
            features_drawn = 0
            errors = []
            
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                
                # Find the corresponding DataLayer
                layer = next((l for l in layers if l.slug == layer_name), None)
                if not layer:
                    continue
                
                # Check if this is a combined layer (has multiple file types)
                is_combined_layer = layer.category.code in ['MIXED_USE', 'TRANSPORT', 'UNCLASSIFIED'] or layer.slug.endswith('_master_plan_2015') or layer.slug.endswith('_highways') or layer.slug.endswith('_metro_lines') or layer.slug.endswith('_strr') or layer.slug.endswith('_workspaces')
                
                for feature in features:
                    try:
                        # Determine styling for this feature
                        if is_combined_layer and city_config:
                            # For combined layers, use per-feature styling from config
                            style_config = self._get_feature_style_from_config(feature, layer, city_config)
                        else:
                            # For regular layers, use layer-level styling
                            style_config = self._get_layer_style(layer)
                        
                        if self._draw_feature_with_pattern(img, feature, style_config):
                            features_drawn += 1
                    except Exception as e:
                        errors.append(f"Layer {layer_name}: {str(e)}")
            
            # Log any errors for tracking
            if errors:
                logger.warning(f"Pattern rendering issues at {z}/{x}/{y}: {errors[:5]}")
            
            logger.info(f"Drew {features_drawn} features with patterns at {z}/{x}/{y}")
            
            # Save with compression
            return self._save_compressed_png(img)
            
        except Exception as e:
            logger.error(f"Error rendering combined MVT with patterns: {e}")
            return self.create_empty_tile()
    
    def _draw_feature_with_pattern(self, img: Image.Image, feature: Dict, 
                                   style_config: Dict) -> bool:
        """Draw a single feature with pattern support"""
        try:
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type', '')
            coordinates = geometry.get('coordinates', [])
            
            if geom_type == 'Polygon' and coordinates:
                return self._draw_polygon_with_pattern(img, coordinates, style_config)
            elif geom_type == 'MultiPolygon' and coordinates:
                drawn = False
                for polygon in coordinates:
                    if self._draw_polygon_with_pattern(img, polygon, style_config):
                        drawn = True
                return drawn
            
            return False
            
        except Exception as e:
            logger.warning(f"Error drawing feature with pattern: {e}")
            return False
    
    def _draw_polygon_with_pattern(self, img: Image.Image, coordinates: list, 
                                   style_config: Dict) -> bool:
        """Draw polygon with pattern fill"""
        try:
            if not coordinates or len(coordinates) == 0:
                return False
            
            exterior_ring = coordinates[0]
            if len(exterior_ring) < 3:
                return False
            
            # Scale coordinates from MVT extent to tile size
            scaled_coords = []
            for coord in exterior_ring:
                if (isinstance(coord, (list, tuple)) and len(coord) >= 2 and
                    isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float))):
                    x = int((coord[0] / 4096.0) * self.tile_size)
                    y = int((coord[1] / 4096.0) * self.tile_size)
                    scaled_coords.append((x, y))
            
            if len(scaled_coords) >= 3:
                # Apply pattern to polygon (no borders as requested)
                self._apply_pattern_to_polygon(img, scaled_coords, style_config, no_border=True)
                return True
                
        except Exception as e:
            logger.warning(f"Error drawing polygon with pattern: {e}")
        
        return False
    
    def _save_compressed_png(self, img: Image.Image, optimize_level: int = 2) -> bytes:
        """Save PIL Image with compression"""
        img_buffer = io.BytesIO()
        
        if optimize_level == 1:
            img.save(img_buffer, format='PNG', optimize=False)
        elif optimize_level == 2:
            img.save(img_buffer, format='PNG', optimize=True)
        else:  # optimize_level >= 3
            img.save(img_buffer, format='PNG', optimize=True, compress_level=9)
        
        return img_buffer.getvalue()
    
    def create_empty_tile(self) -> bytes:
        """Create an empty/transparent PNG tile"""
        img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
        return self._save_compressed_png(img, optimize_level=2)
    
    def _get_feature_style_from_config(self, feature: Dict, layer: DataLayer, city_config: Dict) -> Dict:
        """Get styling for a feature based on its source file from the config"""
        try:
            # Get the source layer name from feature properties
            source_layer_name = feature.get('properties', {}).get('source_layer_name', '')
            
            # Check for metro line colors first (from feature properties)
            feature_properties = feature.get('properties', {})
            if 'color_hex' in feature_properties:
                color = feature_properties['color_hex']
            elif 'line_color' in feature_properties:
                # Metro line color mapping
                line_color = feature_properties['line_color']
                metro_colors = {
                    'Green Line': '#00933D',
                    'Blue Line': '#2D6BA1', 
                    'Red Line': '#E40D17',
                    'Purple Line': '#8C06ED',
                    'Orange Line': '#EF6908'
                }
                color = metro_colors.get(line_color, '#00933D')
            else:
                # Use the pattern style function to get color
                pattern_style = get_pattern_style(layer.city.slug, source_layer_name)
                if pattern_style and 'solid' in pattern_style:
                    color = pattern_style['solid']
                else:
                    # Fallback to hardcoded colors based on source layer name
                    color_map = {
                        'Residential Mixed': '#FFC400',
                        'Residential Main': '#FFEB4F',
                        'Commercial Central': '#004DA8',
                        'Commercial Business': '#73B2FF',
                        'Industrial': '#AA66B2',
                        'High Tech': '#C29ED7',
                        'Public & Semi Public': '#E60000',
                        'Defense': '#E0B8FC',
                        'State Forest Valley Protected Land': '#70A800',
                        'Parks Green Spaces': '#98E600',
                        'Lake Tank': '#BEE8FF',
                        'Road Rail Airport Transport': '#828282',
                        'Power Water Garbage Facility': '#D79E9E',
                        'Agricultural Land': '#9DC1CB',
                        'Unclassified Use': '#E1E1E1',
                        'Drains': '#267300'
                    }
                    color = color_map.get(source_layer_name, '#CCCCCC')
            
            # Debug logging (commented out for production)
            # print(f"DEBUG: Feature source_layer_name='{source_layer_name}' -> color='{color}'")
            
            return {
                'fill_color': color,
                'stroke_color': '#000000',
                'pattern_type': 'SOLID',
                'opacity': 0.8
            }
            
        except Exception as e:
            logger.warning(f"Error getting feature style from config: {e}")
            return self._get_layer_style(layer)
    
    def _get_layer_style(self, layer: DataLayer) -> Dict:
        """Get styling for a layer from its CityLayerStyle"""
        try:
            style = layer.get_style()
            if hasattr(style, 'get_pattern_config'):
                return style.get_pattern_config()
            else:
                return {
                    'fill_color': style.get('fill_color', '#CCCCCC'),
                    'stroke_color': style.get('stroke_color', '#000000'),
                    'pattern_type': 'SOLID',
                    'opacity': style.get('opacity', 0.8)
                }
        except Exception as e:
            logger.warning(f"Error getting layer style: {e}")
            return {
                'fill_color': '#CCCCCC',
                'stroke_color': '#000000',
                'pattern_type': 'SOLID',
                'opacity': 0.8
            }