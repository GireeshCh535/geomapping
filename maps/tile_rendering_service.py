# maps/tile_rendering_service.py - CORRECTED VERSION
"""
TileRenderingService: Converts Mapbox Vector Tiles (MVT) to PNG images for raster map rendering.
Handles per-layer and per-category color assignment, and supports combined tiles for multiple layers.
"""

import mapbox_vector_tile
from PIL import Image, ImageDraw
import io
import logging
from .config import get_city_config

logger = logging.getLogger(__name__)

class TileRenderingService:
    """
    Service for rendering vector tiles (MVT) as PNG raster images.
    - Used for anti-scraping, static tile generation, and fallback rendering.
    - Handles both single-layer and combined multi-layer tiles.
    """
    def __init__(self):
        self.tile_size = 256  # Standard tile size in pixels
        self.background_color = (255, 255, 255, 0)  # Transparent background
        # Default color mapping for categories (used as fallback)
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
        """
        Convert a single-layer MVT tile to a PNG image.
        - Decodes the MVT data.
        - Draws all features using the layer's color.
        - Returns PNG bytes.
        """
        try:
            # Decode MVT data
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                logger.warning(f"No decoded data for {layer.slug} at {z}/{x}/{y}")
                return self.create_empty_tile()
            # Create blank image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            draw = ImageDraw.Draw(img)
            # Get layer color
            layer_color = self._get_layer_color_simple(layer)
            rgb_color = self._hex_to_rgb(layer_color)
            features_drawn = 0
            # Render each feature in the MVT
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
        """
        Convert a combined MVT tile (multiple layers) to a PNG image.
        - Assigns a unique color to each layer based on config or fallback.
        - Draws all features for all layers.
        - Returns PNG bytes.
        """
        try:
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self.create_empty_tile()
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            draw = ImageDraw.Draw(img)
            # Build a mapping from MVT layer name (slug) to color
            if layers:
                city_slug = layers[0].city.slug
            else:
                city_slug = None
            layer_colors = {}
            for layer in layers:
                layer_colors[layer.slug] = self._get_layer_color_simple(layer)
            # Also allow fallback for any slug in decoded_data
            for layer_name in decoded_data.keys():
                if layer_name not in layer_colors:
                    layer_colors[layer_name] = self._get_layer_color_simple(layer_name, city_slug)
            features_drawn = 0
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                rgb_color = layer_colors.get(layer_name, (102, 102, 102))
                if isinstance(rgb_color, str):
                    rgb_color = self._hex_to_rgb(rgb_color)
                for feature in features:
                    if self._draw_feature_simple(draw, feature, rgb_color):
                        features_drawn += 1
            logger.info(f"Drew {features_drawn} features for combined tile at {z}/{x}/{y}")
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
    
    def _get_layer_color_simple(self, layer_or_slug, city_slug=None):
        """Get color for a layer or slug: prefer per-layer color from config using slug or file, else category color, else fallback."""
        try:
            # Accept either a DataLayer or a slug string
            if hasattr(layer_or_slug, 'slug'):
                slug = layer_or_slug.slug
                city_slug = layer_or_slug.city.slug
                category_code = layer_or_slug.category.code
                original_filename = getattr(layer_or_slug, 'original_filename', None)
            else:
                slug = str(layer_or_slug)
                original_filename = None
                # city_slug must be provided if only slug is given
                if not city_slug:
                    return '#FF0000'
                # Find the DataLayer for this slug and city
                from maps.models import DataLayer, City
                city = City.objects.get(slug=city_slug)
                layer = DataLayer.objects.filter(city=city, slug=slug).first()
                category_code = layer.category.code if layer else None
                if layer:
                    original_filename = getattr(layer, 'original_filename', None)
            config = get_city_config(city_slug)
            # Try per-layer color by matching slug or file
            if config and 'layer_groups' in config:
                for group in config['layer_groups'].values():
                    for lyr in group.get('layers', {}).values():
                        # Match by slug, or by file (case-insensitive)
                        if (
                            lyr.get('slug') == slug or
                            (original_filename and lyr.get('file', '').lower() == original_filename.lower()) or
                            slug == lyr.get('file', '').replace('.geojson','').replace('.shp','').lower()
                        ):
                            color = lyr.get('color')
                            if color:
                                return color
            # Fallback to category color from config
            if config and 'colors' in config and category_code:
                color = config['colors'].get(category_code)
                if color:
                    return color
            # Fallback to hardcoded category colors
            if category_code:
                return self.category_colors.get(category_code, '#FF0000')
            return '#FF0000'
        except Exception as e:
            return '#FF0000'
    
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
    
