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
    FIXED: Eliminates unwanted colors and artifacts at tile boundaries.
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
    
    def _create_pattern_mask(self, size: Tuple[int, int], pattern_config: Dict, polygon_coords: list = None) -> Image.Image:
        """Create a pattern mask for the given configuration - FIXED with proper clipping"""
        pattern_type = pattern_config.get('pattern_type', 'SOLID')
        spacing = pattern_config.get('pattern_spacing', 10)
        angle = pattern_config.get('pattern_angle', 45)
        pattern_size = pattern_config.get('pattern_size', 3)
        
        # Create a mask image
        mask = Image.new('L', size, 0)  # Black background
        draw = ImageDraw.Draw(mask)
        
        if pattern_type == 'SOLID':
            # For solid patterns, create a mask that matches the polygon exactly
            if polygon_coords:
                draw.polygon(polygon_coords, fill=255)
            else:
                draw.rectangle([0, 0, size[0], size[1]], fill=255)
        elif pattern_type == 'HATCHED':
            self._draw_hatched_pattern(draw, size, spacing, angle, pattern_size, polygon_coords)
        elif pattern_type == 'DOTTED':
            self._draw_dotted_pattern(draw, size, spacing, pattern_size, polygon_coords)
        elif pattern_type == 'STRIPED':
            self._draw_striped_pattern(draw, size, spacing, angle, pattern_size, polygon_coords)
        elif pattern_type == 'CROSS_HATCHED':
            self._draw_hatched_pattern(draw, size, spacing, angle, pattern_size, polygon_coords)
            self._draw_hatched_pattern(draw, size, spacing, angle + 90, pattern_size, polygon_coords)
        
        return mask
    
    def _draw_hatched_pattern(self, draw: ImageDraw.Draw, size: Tuple[int, int], 
                              spacing: int, angle: float, line_width: int, polygon_coords: list = None):
        """Draw hatched lines on the mask - FIXED with proper clipping"""
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Calculate the diagonal length to ensure full coverage
        diagonal = int(math.sqrt(size[0]**2 + size[1]**2))
        
        # Create a temporary image for the pattern
        temp_img = Image.new('L', size, 0)
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Draw parallel lines
        for i in range(-diagonal, diagonal, spacing):
            # Calculate line endpoints
            x1 = i * cos_a - diagonal * sin_a + size[0]/2
            y1 = i * sin_a + diagonal * cos_a + size[1]/2
            x2 = i * cos_a + diagonal * sin_a + size[0]/2
            y2 = i * sin_a - diagonal * cos_a + size[1]/2
            
            # Draw the line
            temp_draw.line([(x1, y1), (x2, y2)], fill=255, width=line_width)
        
        # If polygon coordinates are provided, clip the pattern to the polygon
        if polygon_coords:
            # Create a polygon mask
            poly_mask = Image.new('L', size, 0)
            poly_draw = ImageDraw.Draw(poly_mask)
            poly_draw.polygon(polygon_coords, fill=255)
            
            # Apply the polygon mask to the pattern
            temp_img = Image.composite(temp_img, Image.new('L', size, 0), poly_mask)
        
        # Composite onto the main mask
        draw.bitmap((0, 0), temp_img)
    
    def _draw_dotted_pattern(self, draw: ImageDraw.Draw, size: Tuple[int, int], 
                             spacing: int, dot_size: int, polygon_coords: list = None):
        """Draw a grid of dots on the mask - FIXED with proper clipping"""
        # Create a temporary image for the pattern
        temp_img = Image.new('L', size, 0)
        temp_draw = ImageDraw.Draw(temp_img)
        
        for x in range(spacing//2, size[0], spacing):
            for y in range(spacing//2, size[1], spacing):
                temp_draw.ellipse([x-dot_size, y-dot_size, x+dot_size, y+dot_size], fill=255)
        
        # If polygon coordinates are provided, clip the pattern to the polygon
        if polygon_coords:
            # Create a polygon mask
            poly_mask = Image.new('L', size, 0)
            poly_draw = ImageDraw.Draw(poly_mask)
            poly_draw.polygon(polygon_coords, fill=255)
            
            # Apply the polygon mask to the pattern
            temp_img = Image.composite(temp_img, Image.new('L', size, 0), poly_mask)
        
        # Composite onto the main mask
        draw.bitmap((0, 0), temp_img)
    
    def _draw_striped_pattern(self, draw: ImageDraw.Draw, size: Tuple[int, int], 
                              spacing: int, angle: float, stripe_width: int, polygon_coords: list = None):
        """Draw striped pattern (thick lines) on the mask - FIXED with proper clipping"""
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        diagonal = int(math.sqrt(size[0]**2 + size[1]**2))
        
        # Create a temporary image for the pattern
        temp_img = Image.new('L', size, 0)
        temp_draw = ImageDraw.Draw(temp_img)
        
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
            temp_draw.polygon(points, fill=255)
        
        # If polygon coordinates are provided, clip the pattern to the polygon
        if polygon_coords:
            # Create a polygon mask
            poly_mask = Image.new('L', size, 0)
            poly_draw = ImageDraw.Draw(poly_mask)
            poly_draw.polygon(polygon_coords, fill=255)
            
            # Apply the polygon mask to the pattern
            temp_img = Image.composite(temp_img, Image.new('L', size, 0), poly_mask)
        
        # Composite onto the main mask
        draw.bitmap((0, 0), temp_img)
    
    def _apply_pattern_to_polygon(self, img: Image.Image, polygon_coords: list, 
                                 style_config: Dict, no_border: bool = True):
        """Apply pattern fill to a polygon area - FIXED to eliminate edge artifacts"""
        # Get colors
        fill_color = self._hex_to_rgb(style_config.get('fill_color', '#CCCCCC'))
        pattern_color = self._hex_to_rgb(style_config.get('pattern_color', style_config.get('fill_color', '#CCCCCC')))
        secondary_fill = style_config.get('secondary_fill_color', '')
        
        # Create a temporary image for this polygon with proper clipping
        temp_img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Create a polygon mask for clipping
        poly_mask = Image.new('L', (self.tile_size, self.tile_size), 0)
        poly_draw = ImageDraw.Draw(poly_mask)
        poly_draw.polygon(polygon_coords, fill=255)
        
        # Draw secondary fill if specified (solid background)
        if secondary_fill:
            bg_color = self._hex_to_rgb(secondary_fill) + (180,)  # Semi-transparent
            temp_draw.polygon(polygon_coords, fill=bg_color)
        
        # Apply pattern if not solid
        pattern_type = style_config.get('pattern_type', 'SOLID')
        if pattern_type != 'SOLID':
            # Create pattern mask with proper clipping to polygon
            pattern_mask = self._create_pattern_mask((self.tile_size, self.tile_size), style_config, polygon_coords)
            
            # Create pattern layer
            pattern_layer = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            pattern_draw = ImageDraw.Draw(pattern_layer)
            
            # Draw the pattern color where the mask is white
            pattern_draw.polygon(polygon_coords, fill=pattern_color + (200,))
            
            # Apply the pattern mask with proper clipping
            pattern_layer.putalpha(Image.composite(pattern_layer.split()[-1], 
                                                  Image.new('L', (self.tile_size, self.tile_size), 0), 
                                                  pattern_mask))
            
            # Composite onto temp image with polygon clipping
            temp_img = Image.alpha_composite(temp_img, pattern_layer)
        else:
            # Solid fill with proper clipping
            temp_draw.polygon(polygon_coords, fill=fill_color + (180,))
        
        # Draw border if needed (thickness = 0 means no border)
        if not no_border:
            stroke_color = self._hex_to_rgb(style_config.get('stroke_color', '#000000'))
            stroke_width = style_config.get('stroke_width', 1)
            if stroke_width > 0:
                temp_draw.polygon(polygon_coords, outline=stroke_color + (255,), width=stroke_width)
        
        # Apply polygon mask to ensure no artifacts outside the polygon
        temp_img.putalpha(Image.composite(temp_img.split()[-1], 
                                         Image.new('L', (self.tile_size, self.tile_size), 0), 
                                         poly_mask))
        
        # Composite onto main image
        img.alpha_composite(temp_img)
    
    def render_mvt_to_png_with_patterns(self, mvt_data: bytes, layers: list, 
                                       z: int, x: int, y: int, 
                                       city_slug: str) -> bytes:
        """Render MVT to PNG with pattern support - FIXED to eliminate edge artifacts"""
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
            
            # Final edge cleanup to ensure no artifacts at tile boundaries
            if features_drawn > 0:
                self._cleanup_tile_edges(img)
            
            # Save with compression
            return self._save_compressed_png(img)
            
        except Exception as e:
            logger.error(f"Error rendering MVT with patterns: {e}")
            return self.create_empty_tile()
    
    def combined_mvt_to_png(self, mvt_data: bytes, layers: list, z: int, x: int, y: int) -> bytes:
        """Render combined MVT to PNG with per-feature styling for combined layers - FIXED"""
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
            
            # Final edge cleanup to ensure no artifacts at tile boundaries
            if features_drawn > 0:
                self._cleanup_tile_edges(img)
            
            # Save with compression
            return self._save_compressed_png(img)
            
        except Exception as e:
            logger.error(f"Error rendering combined MVT with patterns: {e}")
            return self.create_empty_tile()
    
    def _draw_feature_with_pattern(self, img: Image.Image, feature: Dict, 
                                   style_config: Dict) -> bool:
        """Draw a single feature with pattern support - FIXED to handle all geometry types"""
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
            elif geom_type == 'LineString' and coordinates:
                return self._draw_line_with_pattern(img, coordinates, style_config)
            elif geom_type == 'MultiLineString' and coordinates:
                drawn = False
                for line in coordinates:
                    if self._draw_line_with_pattern(img, line, style_config):
                        drawn = True
                return drawn
            
            return False
            
        except Exception as e:
            logger.warning(f"Error drawing feature with pattern: {e}")
            return False
    
    def _draw_polygon_with_pattern(self, img: Image.Image, coordinates: list, 
                                   style_config: Dict) -> bool:
        """Draw polygon with pattern fill - FIXED coordinate handling"""
        try:
            if not coordinates or len(coordinates) == 0:
                return False
            
            exterior_ring = coordinates[0]
            if len(exterior_ring) < 3:
                return False
            
            # Scale coordinates from MVT extent to tile size with proper bounds checking
            scaled_coords = []
            for coord in exterior_ring:
                if (isinstance(coord, (list, tuple)) and len(coord) >= 2 and
                    isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float))):
                    # Ensure coordinates are within valid range
                    x = max(0, min(self.tile_size - 1, int((coord[0] / 4096.0) * self.tile_size)))
                    y = max(0, min(self.tile_size - 1, int((coord[1] / 4096.0) * self.tile_size)))
                    scaled_coords.append((x, y))
            
            if len(scaled_coords) >= 3:
                # Apply pattern to polygon (no borders as requested)
                self._apply_pattern_to_polygon(img, scaled_coords, style_config, no_border=True)
                return True
                
        except Exception as e:
            logger.warning(f"Error drawing polygon with pattern: {e}")
        
        return False
    
    def _draw_line_with_pattern(self, img: Image.Image, coordinates: list, 
                                style_config: Dict) -> bool:
        """Draw line with pattern support - FIXED coordinate handling with precise bounds"""
        try:
            if not coordinates or len(coordinates) < 2:
                return False
            
            # Scale coordinates from MVT extent to tile size with precise bounds checking
            scaled_coords = []
            for coord in coordinates:
                if (isinstance(coord, (list, tuple)) and len(coord) >= 2 and
                    isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float))):
                    # More precise coordinate scaling to prevent edge artifacts
                    x = (coord[0] / 4096.0) * self.tile_size
                    y = (coord[1] / 4096.0) * self.tile_size
                    
                    # Only include coordinates that are within or very close to tile bounds
                    # This prevents drawing lines that are completely outside the tile
                    if -1 <= x <= self.tile_size and -1 <= y <= self.tile_size:
                        # Clamp to exact tile bounds
                        x = max(0, min(self.tile_size - 1, int(x)))
                        y = max(0, min(self.tile_size - 1, int(y)))
                        scaled_coords.append((x, y))
            
            if len(scaled_coords) >= 2:
                # Draw line with proper styling
                self._apply_line_to_image(img, scaled_coords, style_config)
                return True
                
        except Exception as e:
            logger.warning(f"Error drawing line with pattern: {e}")
        
        return False
    
    def _apply_line_to_image(self, img: Image.Image, line_coords: list, style_config: Dict):
        """Apply line styling to image with proper edge handling - FIXED to eliminate edge artifacts"""
        try:
            # Get line color and width
            line_color = self._hex_to_rgb(style_config.get('fill_color', '#14e098'))
            line_width = style_config.get('line_width', 3)
            
            # Create a temporary image for this line
            temp_img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            
            # Filter coordinates to only include those that are actually within the tile bounds
            # This prevents drawing lines that extend beyond the tile boundaries
            valid_coords = []
            for coord in line_coords:
                x, y = coord
                # Only include coordinates that are within the tile bounds
                if 0 <= x < self.tile_size and 0 <= y < self.tile_size:
                    valid_coords.append(coord)
                elif len(valid_coords) > 0:
                    # If we have valid coords and encounter an invalid one, 
                    # clip the line to the tile boundary
                    last_valid = valid_coords[-1]
                    # Calculate intersection with tile boundary
                    clipped_coord = self._clip_line_to_boundary(last_valid, coord)
                    if clipped_coord:
                        valid_coords.append(clipped_coord)
                    break
            
            # Draw the line only if we have valid coordinates
            if len(valid_coords) >= 2:
                temp_draw.line(valid_coords, fill=line_color + (255,), width=line_width)
            
            # Composite onto main image
            img.alpha_composite(temp_img)
            
        except Exception as e:
            logger.warning(f"Error applying line to image: {e}")
    
    def _clip_line_to_boundary(self, inside_coord, outside_coord):
        """Clip a line segment to the tile boundary"""
        try:
            x1, y1 = inside_coord
            x2, y2 = outside_coord
            
            # Calculate intersection with tile boundaries
            intersections = []
            
            # Check intersection with left boundary (x = 0)
            if x2 < 0:
                if x1 != x2:  # Avoid division by zero
                    t = (0 - x1) / (x2 - x1)
                    if 0 <= t <= 1:
                        y_intersect = y1 + t * (y2 - y1)
                        if 0 <= y_intersect < self.tile_size:
                            intersections.append((0, int(y_intersect)))
            
            # Check intersection with right boundary (x = tile_size - 1)
            if x2 >= self.tile_size:
                if x1 != x2:  # Avoid division by zero
                    t = (self.tile_size - 1 - x1) / (x2 - x1)
                    if 0 <= t <= 1:
                        y_intersect = y1 + t * (y2 - y1)
                        if 0 <= y_intersect < self.tile_size:
                            intersections.append((self.tile_size - 1, int(y_intersect)))
            
            # Check intersection with top boundary (y = 0)
            if y2 < 0:
                if y1 != y2:  # Avoid division by zero
                    t = (0 - y1) / (y2 - y1)
                    if 0 <= t <= 1:
                        x_intersect = x1 + t * (x2 - x1)
                        if 0 <= x_intersect < self.tile_size:
                            intersections.append((int(x_intersect), 0))
            
            # Check intersection with bottom boundary (y = tile_size - 1)
            if y2 >= self.tile_size:
                if y1 != y2:  # Avoid division by zero
                    t = (self.tile_size - 1 - y1) / (y2 - y1)
                    if 0 <= t <= 1:
                        x_intersect = x1 + t * (x2 - x1)
                        if 0 <= x_intersect < self.tile_size:
                            intersections.append((int(x_intersect), self.tile_size - 1))
            
            # Return the closest intersection point
            if intersections:
                # Find the intersection closest to the inside point
                min_dist = float('inf')
                closest = None
                for intersection in intersections:
                    dist = ((intersection[0] - x1) ** 2 + (intersection[1] - y1) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        closest = intersection
                return closest
            
            return None
            
        except Exception as e:
            logger.warning(f"Error clipping line to boundary: {e}")
            return None
    
    def _cleanup_tile_edges(self, img: Image.Image):
        """Clean up tile edges to ensure no artifacts at boundaries"""
        try:
            width, height = img.size
            
            # Check if there's any legitimate data near the edges
            edge_has_data = False
            
            # Sample a few pixels from each edge to check for legitimate data
            edge_samples = []
            
            # Top edge samples
            for x in range(0, width, 10):
                pixel = img.getpixel((x, 0))
                if pixel[3] > 10:  # Non-transparent
                    edge_samples.append(pixel)
            
            # Bottom edge samples
            for x in range(0, width, 10):
                pixel = img.getpixel((x, height-1))
                if pixel[3] > 10:  # Non-transparent
                    edge_samples.append(pixel)
            
            # Left edge samples
            for y in range(0, height, 10):
                pixel = img.getpixel((0, y))
                if pixel[3] > 10:  # Non-transparent
                    edge_samples.append(pixel)
            
            # Right edge samples
            for y in range(0, height, 10):
                pixel = img.getpixel((width-1, y))
                if pixel[3] > 10:  # Non-transparent
                    edge_samples.append(pixel)
            
            # If we have edge samples, check if they're legitimate data
            if edge_samples:
                # Check if the edge colors are consistent with center colors
                center_x, center_y = width // 2, height // 2
                center_pixels = []
                for x in range(center_x - 20, center_x + 20):
                    for y in range(center_y - 20, center_y + 20):
                        if 0 <= x < width and 0 <= y < height:
                            pixel = img.getpixel((x, y))
                            if pixel[3] > 10:  # Non-transparent
                                center_pixels.append(pixel)
                
                # If we have center data, check if edge colors match
                if center_pixels:
                    center_colors = set(p[:3] for p in center_pixels)
                    edge_colors = set(p[:3] for p in edge_samples)
                    
                    # If edge colors don't match center colors, they're likely artifacts
                    if not edge_colors.intersection(center_colors):
                        # Clear the edges
                        self._clear_tile_edges(img)
                else:
                    # No center data, clear edges
                    self._clear_tile_edges(img)
            else:
                # No edge data, ensure edges are transparent
                self._clear_tile_edges(img)
                
        except Exception as e:
            logger.warning(f"Error cleaning up tile edges: {e}")
    
    def _clear_tile_edges(self, img: Image.Image):
        """Clear tile edges to make them transparent - ENHANCED to eliminate all artifacts"""
        try:
            width, height = img.size
            
            # Clear top and bottom edges (4 pixel border for more aggressive cleanup)
            for x in range(width):
                for y in range(4):  # Top edge
                    img.putpixel((x, y), (0, 0, 0, 0))
                for y in range(height-4, height):  # Bottom edge
                    img.putpixel((x, y), (0, 0, 0, 0))
            
            # Clear left and right edges (4 pixel border for more aggressive cleanup)
            for y in range(height):
                for x in range(4):  # Left edge
                    img.putpixel((x, y), (0, 0, 0, 0))
                for x in range(width-4, width):  # Right edge
                    img.putpixel((x, y), (0, 0, 0, 0))
            
            # Also clear any isolated pixels that might be artifacts
            # Check for isolated non-transparent pixels near edges
            for x in range(width):
                for y in range(height):
                    pixel = img.getpixel((x, y))
                    if pixel[3] > 10:  # Non-transparent
                        # Check if this pixel is isolated (no nearby non-transparent pixels)
                        isolated = True
                        for dx in range(-2, 3):
                            for dy in range(-2, 3):
                                nx, ny = x + dx, y + dy
                                if (0 <= nx < width and 0 <= ny < height and 
                                    (dx != 0 or dy != 0)):
                                    neighbor = img.getpixel((nx, ny))
                                    if neighbor[3] > 10:  # Neighbor is also non-transparent
                                        isolated = False
                                        break
                            if not isolated:
                                break
                        
                        # If isolated and near edge, clear it
                        if isolated and (x < 8 or x >= width - 8 or y < 8 or y >= height - 8):
                            img.putpixel((x, y), (0, 0, 0, 0))
                    
        except Exception as e:
            logger.warning(f"Error clearing tile edges: {e}")
    
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