# maps/tile_rendering_service.py - CORRECTED VERSION
"""
Fixed Convert MVT tiles to PNG images
"""

import mapbox_vector_tile
from PIL import Image, ImageDraw
import io
import logging

logger = logging.getLogger(__name__)

class TileRenderingService:
    """FIXED - Convert MVT vector tiles to PNG raster images"""
    
    def __init__(self):
        self.tile_size = 256
        self.background_color = (255, 255, 255, 0)  # Transparent
        
        # Simplified color mapping - use bright colors for visibility
        self.category_colors = {
            'RESIDENTIAL': '#FFC400',      # Yellow
            'COMMERCIAL': '#004DA8',       # Blue
            'INDUSTRIAL': '#AA66B2',       # Purple
            'HIGH_TECH': '#C29ED7',        # Light Purple
            'PUBLIC': '#E60000',           # Red
            'DEFENSE': '#8B4513',          # Brown
            'PROTECTED': '#228B22',        # Forest Green
            'PARKS_GREEN': '#98E600',      # Bright Green
            'WATER_BODIES': '#1E90FF',     # Dodger Blue
            'TRANSPORT': '#808080',        # Gray
            'UTILITIES': '#FF6347',        # Tomato
            'AGRICULTURAL': '#9ACD32',     # Yellow Green
            'UNCLASSIFIED': '#D3D3D3',     # Light Gray
            'DRAINS': '#4682B4',           # Steel Blue
        }
    
    def mvt_to_png(self, mvt_data, layer, z, x, y):
        """FIXED - Convert single layer MVT to PNG image"""
        
        try:
            # Decode MVT data
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            
            if not decoded_data:
                logger.warning(f"No decoded data for {layer.slug} at {z}/{x}/{y}")
                return self.create_empty_tile()
            
            # Create blank image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            draw = ImageDraw.Draw(img)
            
            # Get layer color - SIMPLIFIED
            layer_color = self._get_layer_color_simple(layer)
            rgb_color = self._hex_to_rgb(layer_color)
            
            # Count features drawn
            features_drawn = 0
            
            # Render each layer in the MVT
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                
                for feature in features:
                    if self._draw_feature_simple(draw, feature, rgb_color):
                        features_drawn += 1
            
            logger.info(f"Drew {features_drawn} features for {layer.slug} at {z}/{x}/{y}")
            
            # Convert to PNG bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', optimize=True)
            return img_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error rendering MVT to PNG: {e}")
            return self.create_empty_tile()
    
    def combined_mvt_to_png(self, mvt_data, layers, z, x, y):
        """FIXED - Convert combined layers MVT to PNG image"""
        
        try:
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            
            if not decoded_data:
                return self.create_empty_tile()
            
            # Create blank image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            draw = ImageDraw.Draw(img)
            
            # Create layer color mapping - SIMPLIFIED
            layer_colors = {}
            for layer in layers:
                layer_colors[layer.slug] = self._hex_to_rgb(self._get_layer_color_simple(layer))
            
            features_drawn = 0
            
            # Render each layer in the MVT
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                rgb_color = layer_colors.get(layer_name, (102, 102, 102))  # Default gray
                
                for feature in features:
                    if self._draw_feature_simple(draw, feature, rgb_color):
                        features_drawn += 1
            
            logger.info(f"Drew {features_drawn} features for combined tile at {z}/{x}/{y}")
            
            # Convert to PNG bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', optimize=True)
            return img_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error rendering combined MVT to PNG: {e}")
            return self.create_empty_tile()
    
    def _draw_feature_simple(self, draw, feature, rgb_color):
        """SIMPLIFIED - Draw a single feature on the image"""
        
        try:
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type', '')
            coordinates = geometry.get('coordinates', [])
            
            if geom_type == 'Polygon' and coordinates:
                return self._draw_polygon_simple(draw, coordinates, rgb_color)
                
            elif geom_type == 'MultiPolygon' and coordinates:
                drawn = False
                for polygon in coordinates:
                    if self._draw_polygon_simple(draw, polygon, rgb_color):
                        drawn = True
                return drawn
                
            # Skip other geometry types for now
            return False
                    
        except Exception as e:
            logger.warning(f"Error drawing feature: {e}")
            return False
    
    def _draw_polygon_simple(self, draw, coordinates, rgb_color):
        """SIMPLIFIED - Draw polygon on image"""
        
        try:
            if not coordinates or len(coordinates) == 0:
                return False
                
            exterior_ring = coordinates[0]
            
            if len(exterior_ring) < 3:
                return False
            
            # CORRECTED - Scale coordinates from MVT extent (4096) to tile size (256)
            scaled_coords = []
            for coord in exterior_ring:
                # Ensure coord is a valid list/tuple with 2 numbers
                if (isinstance(coord, (list, tuple)) and len(coord) >= 2 and
                        isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float))):
                    
                    # Scale from MVT grid (e.g., 4096) to image size (e.g., 256)
                    x = int((coord[0] / 4096.0) * self.tile_size)
                    y = int((coord[1] / 4096.0) * self.tile_size)
                    scaled_coords.append((x, y)) # Append a tuple
            
            if len(scaled_coords) >= 3:  # A valid polygon needs at least 3 points
                # Create colors with transparency
                fill_color = rgb_color + (120,)  # Semi-transparent fill
                outline_color = rgb_color + (255,)  # Solid outline
                
                # Draw polygon
                draw.polygon(scaled_coords, fill=fill_color, outline=outline_color, width=1)
                return True
                
        except Exception as e:
            logger.warning(f"Error drawing polygon: {e}")
            
        return False
    
    def _get_layer_color_simple(self, layer):
        """SIMPLIFIED - Get color for a layer"""
        
        try:
            # Try to get category code
            category_code = layer.category.code
            return self.category_colors.get(category_code, '#FF0000')  # Default to red for visibility
        except:
            return '#FF0000'  # Bright red fallback
    
    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except:
            pass
            
        return (255, 0, 0)  # Red fallback
    
    def create_empty_tile(self):
        """Create an empty transparent tile"""
        
        img = Image.new('RGBA', (self.tile_size, self.tile_size), (255, 255, 255, 0))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG', optimize=True)
        return img_buffer.getvalue()
    
