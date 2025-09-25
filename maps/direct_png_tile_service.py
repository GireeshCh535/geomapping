# maps/direct_png_tile_service.py
"""
Direct PNG Tile Rendering Service
Bypasses MVT encoding/decoding for direct GeoJSON to PNG rendering
"""

import mercantile
from PIL import Image, ImageDraw
import io
import logging
from typing import Dict, Tuple, Optional, List, Any
from django.contrib.gis.geos import Point, LineString, Polygon, MultiPolygon, MultiLineString
import math

logger = logging.getLogger(__name__)

class DirectPNGTileService:
    """
    Service for rendering tiles directly from GeoFeatures to PNG without MVT intermediate step.
    This eliminates precision loss and artifacts from coordinate transformations.
    """
    
    def __init__(self):
        self.tile_size = 256  # Standard tile size
        self.background_color = (255, 255, 255, 0)  # Transparent background
    
    def generate_png_tile(self, features, z: int, x: int, y: int, 
                          style_config: Dict[str, Any]) -> Optional[bytes]:
        """
        Generate a PNG tile directly from GeoFeatures
        
        Args:
            features: QuerySet of GeoFeature objects
            z, x, y: Tile coordinates
            style_config: Style configuration dict with colors and patterns
            
        Returns:
            PNG bytes or None if no features
        """
        try:
            # Get tile bounds in lat/lon
            tile_bounds = mercantile.bounds(x, y, z)
            
            # Create image
            img = Image.new('RGBA', (self.tile_size, self.tile_size), self.background_color)
            draw = ImageDraw.Draw(img)
            
            features_drawn = False
            
            for feature in features:
                if self._draw_feature(draw, feature, tile_bounds, style_config, z):
                    features_drawn = True
            
            if not features_drawn:
                return None
            
            # Clean up tile edges to prevent artifacts
            self._cleanup_tile_edges(img)
            
            # Convert to PNG bytes
            buffer = io.BytesIO()
            img.save(buffer, 'PNG', optimize=True, compress_level=6)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating PNG tile {z}/{x}/{y}: {e}")
            return None
    
    def _draw_feature(self, draw: ImageDraw, feature, tile_bounds, 
                     style_config: Dict, zoom: int) -> bool:
        """
        Draw a single feature on the tile
        
        Returns:
            True if feature was drawn, False otherwise
        """
        try:
            geometry = feature.geometry
            if not geometry:
                return False
            
            # Get feature properties for styling
            properties = feature.properties if hasattr(feature, 'properties') else {}
            
            # Get color from style config based on feature properties
            fill_color = self._get_feature_color(properties, style_config)
            stroke_color = style_config.get('stroke_color', '#000000')
            line_width = self._get_line_width(zoom, geometry.geom_type)
            
            # Convert colors from hex to RGB
            fill_rgb = self._hex_to_rgb(fill_color)
            stroke_rgb = self._hex_to_rgb(stroke_color)
            
            # Draw based on geometry type
            if geometry.geom_type == 'Polygon':
                return self._draw_polygon(draw, geometry, tile_bounds, fill_rgb, stroke_rgb)
            elif geometry.geom_type == 'MultiPolygon':
                drawn = False
                for poly in geometry:
                    if self._draw_polygon(draw, poly, tile_bounds, fill_rgb, stroke_rgb):
                        drawn = True
                return drawn
            elif geometry.geom_type == 'LineString':
                return self._draw_linestring(draw, geometry, tile_bounds, stroke_rgb, line_width)
            elif geometry.geom_type == 'MultiLineString':
                drawn = False
                for line in geometry:
                    if self._draw_linestring(draw, line, tile_bounds, stroke_rgb, line_width):
                        drawn = True
                return drawn
            elif geometry.geom_type == 'Point':
                return self._draw_point(draw, geometry, tile_bounds, fill_rgb, zoom)
            
            return False
            
        except Exception as e:
            logger.warning(f"Error drawing feature: {e}")
            return False
    
    def _draw_polygon(self, draw: ImageDraw, polygon, tile_bounds, 
                     fill_color: Tuple, stroke_color: Tuple) -> bool:
        """Draw a polygon on the tile"""
        try:
            # Convert exterior ring to pixel coordinates
            exterior_pixels = []
            for coord in polygon.exterior_ring.coords:
                pixel_coord = self._latlon_to_pixel(coord[0], coord[1], tile_bounds)
                if pixel_coord:  # Only add if within reasonable bounds
                    exterior_pixels.append(pixel_coord)
            
            if len(exterior_pixels) >= 3:  # Need at least 3 points for a polygon
                # Draw filled polygon
                draw.polygon(exterior_pixels, fill=fill_color + (128,), outline=stroke_color)
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error drawing polygon: {e}")
            return False
    
    def _draw_linestring(self, draw: ImageDraw, linestring, tile_bounds, 
                        stroke_color: Tuple, line_width: int) -> bool:
        """Draw a linestring on the tile"""
        try:
            # Convert coordinates to pixel positions
            pixel_coords = []
            for coord in linestring.coords:
                pixel_coord = self._latlon_to_pixel(coord[0], coord[1], tile_bounds)
                if pixel_coord:
                    pixel_coords.append(pixel_coord)
            
            # Draw line segments
            if len(pixel_coords) >= 2:
                for i in range(len(pixel_coords) - 1):
                    p1, p2 = pixel_coords[i], pixel_coords[i + 1]
                    
                    # Check if segment is visible (with margin for thick lines)
                    margin = line_width + 10
                    if self._segment_visible(p1, p2, margin):
                        draw.line([p1, p2], fill=stroke_color, width=line_width)
                
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error drawing linestring: {e}")
            return False
    
    def _draw_point(self, draw: ImageDraw, point, tile_bounds, 
                   fill_color: Tuple, zoom: int) -> bool:
        """Draw a point on the tile"""
        try:
            pixel_coord = self._latlon_to_pixel(point.x, point.y, tile_bounds)
            if pixel_coord and self._point_visible(pixel_coord):
                radius = self._get_point_radius(zoom)
                bbox = [pixel_coord[0] - radius, pixel_coord[1] - radius,
                       pixel_coord[0] + radius, pixel_coord[1] + radius]
                draw.ellipse(bbox, fill=fill_color, outline=fill_color)
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error drawing point: {e}")
            return False
    
    def _latlon_to_pixel(self, lon: float, lat: float, 
                        tile_bounds) -> Optional[Tuple[float, float]]:
        """
        Convert lat/lon to pixel coordinates within tile
        
        Returns:
            (x, y) pixel coordinates or None if way outside bounds
        """
        try:
            # Calculate pixel position within tile
            x_pixel = ((lon - tile_bounds.west) / 
                      (tile_bounds.east - tile_bounds.west)) * self.tile_size
            y_pixel = ((tile_bounds.north - lat) / 
                      (tile_bounds.north - tile_bounds.south)) * self.tile_size
            
            # Filter out coordinates that are way outside the tile (optimization)
            if (x_pixel < -1000 or x_pixel > self.tile_size + 1000 or 
                y_pixel < -1000 or y_pixel > self.tile_size + 1000):
                return None
            
            return (x_pixel, y_pixel)
            
        except Exception:
            return None
    
    def _segment_visible(self, p1: Tuple, p2: Tuple, margin: int) -> bool:
        """Check if a line segment is visible within tile bounds"""
        return any(-margin <= coord <= self.tile_size + margin 
                  for coord in [p1[0], p1[1], p2[0], p2[1]])
    
    def _point_visible(self, pixel_coord: Tuple) -> bool:
        """Check if a point is visible within tile bounds"""
        margin = 20
        return (-margin <= pixel_coord[0] <= self.tile_size + margin and
                -margin <= pixel_coord[1] <= self.tile_size + margin)
    
    def _get_feature_color(self, properties: Dict, style_config: Dict) -> str:
        """Get color for feature based on properties and style config"""
        # Try different property keys that might contain zone/category info
        zone_keys = ['zone_category', 'Zone_Categ', 'Category', 'PLU_CODE', 
                    'plu_code', 'symbology', 'plot_category']
        
        zone_value = None
        for key in zone_keys:
            if key in properties and properties[key]:
                zone_value = properties[key]
                break
        
        if zone_value and 'zone_colors' in style_config:
            # Look up color in zone_colors mapping
            return style_config['zone_colors'].get(
                zone_value, 
                style_config.get('fill_color', '#CCCCCC')
            )
        
        return style_config.get('fill_color', '#CCCCCC')
    
    def _get_line_width(self, zoom: int, geom_type: str) -> int:
        """Get line width based on zoom level"""
        if geom_type in ['LineString', 'MultiLineString']:
            # Scale line width with zoom
            if zoom <= 10:
                return 1
            elif zoom <= 12:
                return 2
            elif zoom <= 14:
                return 3
            elif zoom <= 16:
                return 4
            else:
                return 5
        else:
            # Border width for polygons
            return 1
    
    def _get_point_radius(self, zoom: int) -> int:
        """Get point radius based on zoom level"""
        if zoom <= 10:
            return 2
        elif zoom <= 14:
            return 3
        elif zoom <= 16:
            return 4
        else:
            return 5
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _cleanup_tile_edges(self, img: Image):
        """Clean up artifacts at tile edges"""
        # Create a mask for the tile area
        mask = Image.new('L', (self.tile_size, self.tile_size), 255)
        draw = ImageDraw.Draw(mask)
        
        # Clear 1-pixel border
        draw.rectangle([0, 0, self.tile_size-1, 0], fill=0)  # Top edge
        draw.rectangle([0, self.tile_size-1, self.tile_size-1, self.tile_size-1], fill=0)  # Bottom
        draw.rectangle([0, 0, 0, self.tile_size-1], fill=0)  # Left edge
        draw.rectangle([self.tile_size-1, 0, self.tile_size-1, self.tile_size-1], fill=0)  # Right
        
        # Apply mask to alpha channel
        img.putalpha(mask)


class EnhancedS3TileService:
    """
    Enhanced S3 tile service that uses direct PNG generation
    """
    
    def __init__(self):
        self.direct_png_service = DirectPNGTileService()
        # ... existing S3 configuration ...
    
    def generate_tile_direct(self, layer, z: int, x: int, y: int, 
                            city_slug: str, upload_to_s3: bool = True) -> Dict[str, Any]:
        """
        Generate tile directly from GeoFeatures without MVT intermediate step
        """
        try:
            # Get tile bounds
            bounds = mercantile.bounds(x, y, z)
            
            # Create bounding box for spatial query (with small buffer)
            buffer = 0.001
            from django.contrib.gis.geos import Polygon
            bbox = Polygon.from_bbox((
                bounds.west - buffer,
                bounds.south - buffer,
                bounds.east + buffer,
                bounds.north + buffer
            ))
            
            # Get features that intersect tile
            from maps.models import GeoFeature
            features = GeoFeature.objects.filter(
                layer=layer,
                geometry__intersects=bbox
            ).select_related('layer')
            
            if not features.exists():
                return {'success': True, 'empty': True}
            
            # Get style config for the layer
            style_config = self._get_layer_style_config(layer, city_slug)
            
            # Generate PNG directly
            png_data = self.direct_png_service.generate_png_tile(
                features, z, x, y, style_config
            )
            
            if not png_data:
                return {'success': True, 'empty': True}
            
            # Upload to S3 if requested
            if upload_to_s3:
                s3_key = f"{city_slug}/{layer.slug}/{z}/{x}/{y}.png"
                result = self.upload_bytes_to_s3(png_data, s3_key, 'image/png')
                return {
                    'success': result['success'],
                    'size': len(png_data),
                    's3_key': s3_key,
                    'empty': False
                }
            
            return {
                'success': True,
                'data': png_data,
                'size': len(png_data),
                'empty': False
            }
            
        except Exception as e:
            logger.error(f"Error generating direct tile: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_layer_style_config(self, layer, city_slug: str) -> Dict[str, Any]:
        """Get style configuration for a layer"""
        from maps.config import get_city_style_config
        
        # Get city-specific styles
        city_config = get_city_style_config(city_slug)
        
        # Get layer category
        category = layer.category.name if layer.category else 'default'
        
        # Build style config
        style_config = {
            'fill_color': city_config.get(category, {}).get('color', '#CCCCCC'),
            'stroke_color': '#000000',
            'zone_colors': {}
        }
        
        # Add zone-based colors if available
        if 'zone_colors' in city_config:
            style_config['zone_colors'] = city_config['zone_colors']
        
        return style_config