# maps/enhanced_tile_rendering.py
"""
Enhanced tile rendering that uses feature-specific colors stored during import
"""

import io
import json
from PIL import Image, ImageDraw
import mapbox_vector_tile
from django.contrib.gis.geos import GEOSGeometry

class EnhancedTileRenderer:
    """Renders tiles with proper colors based on feature properties"""
    
    TILE_SIZE = 256
    
    def render_mvt_to_png(self, mvt_data, default_color='#CCCCCC'):
        """
        Render MVT tile to PNG using colors stored in feature properties
        
        Args:
            mvt_data: Raw MVT tile data
            default_color: Default color if none specified
        
        Returns:
            PNG image bytes
        """
        # Create image with transparent background
        img = Image.new('RGBA', (self.TILE_SIZE, self.TILE_SIZE), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            # Decode MVT tile
            tile = mapbox_vector_tile.decode(mvt_data)
            
            # Process each layer in the tile
            for layer_name, layer_data in tile.items():
                features = layer_data.get('features', [])
                
                # Sort features by area (draw larger features first)
                features_with_area = []
                for feature in features:
                    area = self._calculate_feature_area(feature)
                    features_with_area.append((area, feature))
                
                # Sort by area descending (largest first)
                features_with_area.sort(key=lambda x: x[0], reverse=True)
                
                # Draw each feature
                for _, feature in features_with_area:
                    self._draw_feature(draw, feature, default_color)
                    
        except Exception as e:
            print(f"Error rendering tile: {e}")
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        return img_bytes.getvalue()
    
    def _calculate_feature_area(self, feature):
        """Calculate approximate area of a feature for sorting"""
        geometry = feature.get('geometry')
        if not geometry:
            return 0
        
        geom_type = geometry.get('type')
        coords = geometry.get('coordinates', [])
        
        if geom_type in ['Polygon', 'MultiPolygon']:
            # Rough area calculation using bounding box
            if geom_type == 'Polygon' and coords:
                return self._polygon_area(coords[0])
            elif geom_type == 'MultiPolygon' and coords:
                total_area = 0
                for polygon in coords:
                    if polygon:
                        total_area += self._polygon_area(polygon[0])
                return total_area
        
        return 0  # Lines and points have no area
    
    def _polygon_area(self, coords):
        """Calculate rough area using bounding box"""
        if not coords or len(coords) < 3:
            return 0
        
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        return width * height
    
    def _draw_feature(self, draw, feature, default_color):
        """Draw a single feature with its specific color"""
        
        geometry = feature.get('geometry')
        properties = feature.get('properties', {})
        
        if not geometry:
            return
        
        # Get color from properties
        fill_color = self._get_feature_color(properties, default_color)
        
        geom_type = geometry.get('type')
        coords = geometry.get('coordinates', [])
        
        if geom_type == 'Polygon' and coords:
            self._draw_polygon(draw, coords[0], fill_color, properties)
        elif geom_type == 'MultiPolygon' and coords:
            for polygon in coords:
                if polygon:
                    self._draw_polygon(draw, polygon[0], fill_color, properties)
        elif geom_type == 'LineString' and coords:
            self._draw_line(draw, coords, fill_color)
        elif geom_type == 'MultiLineString' and coords:
            for line in coords:
                self._draw_line(draw, line, fill_color)
        elif geom_type == 'Point' and coords:
            self._draw_point(draw, coords, fill_color)
    
    def _get_feature_color(self, properties, default_color):
        """Extract color from feature properties"""
        
        # Check for color in properties (set during import)
        if '_fill_color' in properties:
            return properties['_fill_color']
        
        # Check for pattern style
        if '_pattern_style' in properties:
            pattern = properties['_pattern_style']
            if isinstance(pattern, dict):
                return pattern.get('solid', pattern.get('color', default_color))
        
        # Check for layer name and use config colors
        if '_layer_name' in properties:
            # You could map layer names to colors here
            layer_colors = {
                'Residential Mixed': '#FFC400',
                'Residential Main': '#FFEB4F',
                'Commercial Central': '#004DA8',
                'Commercial Business': '#73B2FF',
                'Industrial': '#AA66B2',
                'High Tech': '#C29ED7',
                'Public & Semi Public': '#E60000',
                'Defense': '#E0B8FC',
                'Parks Green Spaces': '#98E600',
                'Lake Tank': '#BEE8FF',
                'Agricultural Land': '#9DC1CB',
                'Drains': '#267300',
                # Add more mappings as needed
            }
            layer_name = properties.get('_layer_name', '')
            if layer_name in layer_colors:
                return layer_colors[layer_name]
        
        return default_color
    
    def _draw_polygon(self, draw, coordinates, fill_color, properties):
        """Draw a polygon with the specified color"""
        
        if not coordinates or len(coordinates) < 3:
            return
        
        # Convert coordinates to pixel space
        points = [(self._lon_to_pixel(x), self._lat_to_pixel(y)) 
                  for x, y in coordinates]
        
        # Ensure polygon is closed
        if points[0] != points[-1]:
            points.append(points[0])
        
        # Parse color
        color = self._parse_color(fill_color)
        
        # Check for pattern rendering
        pattern_style = properties.get('_pattern_style', {})
        if isinstance(pattern_style, dict) and pattern_style.get('type') == 'pattern':
            # Draw with pattern
            if 'hatch' in pattern_style:
                self._draw_with_hatch(draw, points, color, pattern_style.get('hatch'))
            elif 'dot' in pattern_style:
                self._draw_with_dots(draw, points, color, pattern_style.get('dot'))
            else:
                # Solid fill
                try:
                    # Add transparency for overlapping features - no outline to remove borders between features
                    fill_with_alpha = (*color[:3], 200)  # 78% opacity
                    draw.polygon(points, fill=fill_with_alpha, outline=None)
                except:
                    pass
        else:
            # Regular solid fill
            try:
                # Add transparency for overlapping features - no outline to remove borders between features
                fill_with_alpha = (*color[:3], 200)  # 78% opacity
                draw.polygon(points, fill=fill_with_alpha, outline=None)
            except:
                pass
    
    def _draw_with_hatch(self, draw, points, base_color, hatch_color):
        """Draw polygon with hatched pattern"""
        # First draw solid base
        try:
            fill_with_alpha = (*base_color[:3], 180)
            draw.polygon(points, fill=fill_with_alpha)
        except:
            pass
        
        # Then add hatch lines
        # (Simplified - you can enhance this with actual hatching)
        hatch_rgba = self._parse_color(hatch_color) if hatch_color else base_color
        try:
            draw.polygon(points, outline=hatch_rgba)
        except:
            pass
    
    def _draw_with_dots(self, draw, points, base_color, dot_color):
        """Draw polygon with dotted pattern"""
        # First draw solid base
        try:
            fill_with_alpha = (*base_color[:3], 180)
            draw.polygon(points, fill=fill_with_alpha)
        except:
            pass
        
        # Add dot pattern (simplified)
        # You can enhance this with actual dot pattern
    
    def _draw_line(self, draw, coordinates, color):
        """Draw a line with specified color"""
        
        if not coordinates or len(coordinates) < 2:
            return
        
        points = [(self._lon_to_pixel(x), self._lat_to_pixel(y)) 
                  for x, y in coordinates]
        
        rgba_color = self._parse_color(color)
        
        try:
            draw.line(points, fill=rgba_color, width=2)
        except:
            pass
    
    def _draw_point(self, draw, coordinates, color):
        """Draw a point with specified color"""
        
        if not coordinates:
            return
        
        x = self._lon_to_pixel(coordinates[0])
        y = self._lat_to_pixel(coordinates[1])
        
        rgba_color = self._parse_color(color)
        radius = 3
        
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=rgba_color,
            outline=rgba_color
        )
    
    def _lon_to_pixel(self, lon):
        """Convert longitude to pixel coordinate"""
        return int((lon + 180.0) / 360.0 * self.TILE_SIZE)
    
    def _lat_to_pixel(self, lat):
        """Convert latitude to pixel coordinate"""
        return int((90.0 - lat) / 180.0 * self.TILE_SIZE)
    
    def _parse_color(self, color_str):
        """Parse color string to RGBA tuple"""
        
        if not color_str:
            return (204, 204, 204, 255)
        
        # Handle hex colors
        if isinstance(color_str, str):
            if color_str.startswith('#'):
                color_str = color_str[1:]
            
            try:
                if len(color_str) == 3:
                    r = int(color_str[0] * 2, 16)
                    g = int(color_str[1] * 2, 16)
                    b = int(color_str[2] * 2, 16)
                elif len(color_str) == 6:
                    r = int(color_str[0:2], 16)
                    g = int(color_str[2:4], 16)
                    b = int(color_str[4:6], 16)
                else:
                    return (204, 204, 204, 255)
                
                return (r, g, b, 255)
            except:
                return (204, 204, 204, 255)
        
        return (204, 204, 204, 255)


def get_feature_style_for_mvt(feature_properties):
    """
    Helper function to get style information for MVT encoding
    This can be used when creating MVT tiles to include style properties
    """
    style = {}
    
    if '_fill_color' in feature_properties:
        style['fill'] = feature_properties['_fill_color']
    
    if '_pattern_style' in feature_properties:
        pattern = feature_properties['_pattern_style']
        if isinstance(pattern, dict):
            style['pattern_type'] = pattern.get('type', 'solid')
            if pattern.get('hatch'):
                style['hatch'] = pattern['hatch']
            if pattern.get('dot'):
                style['dot'] = pattern['dot']
    
    if '_layer_name' in feature_properties:
        style['layer'] = feature_properties['_layer_name']
    
    return style