"""
Relevance reindex API (without job tracking / pairs endpoint).
"""
from ._imports import *

from ..models import RelevantLayer
from ..relevance_service import get_layer_relevant_data, reindex_layer, resolve_layer_from_payload


@extend_schema_view(
    get=extend_schema(
        summary='Get relevant rows',
        description=(
            'Provide geompapping_layer_id or geompapping_layer_name_slug to fetch '
            'a single layer. Use ?all=true to fetch all relevant rows.'
        ),
        tags=['relevance'],
        parameters=[
            OpenApiParameter(name='geompapping_layer_id', type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name='geompapping_layer_name_slug', type=str, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name='all', type=str, location=OpenApiParameter.QUERY, required=False),
        ],
    ),
    post=extend_schema(
        summary='Trigger relevance reindex for one layer',
        description=(
            'Recompute overlap pairs for the given layer and return that layer relevance output.'
        ),
        tags=['relevance'],
    ),
)
class RelevanceReindexAPIView(APIView):
    def get(self, request):
        if str(request.GET.get('all', '')).lower() in ('1', 'true', 'yes'):
            rows = (
                RelevantLayer.objects
                .select_related('layer', 'lgddivision')
                .order_by('layer_id', 'matched_level', 'lgddivision__name')
            )
            results = [
                {
                    'geomapping_layer_id': row.layer_id,
                    'geomapping_layer_name_slug': row.layer.slug if row.layer_id else None,
                    'lgd_division_id': row.lgddivision.backend_id if row.lgddivision_id else None,
                    'lgd_division_name': row.lgddivision.name if row.lgddivision_id else None,
                    'lgd_division_slug': row.lgddivision.slug if row.lgddivision_id else None,
                    'lgd_division_code': row.lgddivision.code if row.lgddivision_id else None,
                    'lgd_division_type': row.lgddivision.division_type if row.lgddivision_id else None,
                    'matched_level': row.matched_level,
                    'source_state_id': row.source_state_backend_id,
                }
                for row in rows
            ]
            return Response({'success': True, 'count': len(results), 'results': results})

        payload = {
            'geompapping_layer_id': request.GET.get('geompapping_layer_id') or request.GET.get('layer_id_geomapping'),
            'geompapping_layer_name_slug': request.GET.get('geompapping_layer_name_slug') or request.GET.get('layer_slug'),
        }
        layer, err = resolve_layer_from_payload(payload)
        if not layer:
            return Response(
                {
                    **err,
                    'hint': 'Pass geompapping_layer_id/geompapping_layer_name_slug, or use ?all=true',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        relevant_data = get_layer_relevant_data(layer)
        return Response(
            {
                'success': True,
                'layer': {
                    'geomapping_layer_id': layer.id,
                    'geomapping_layer_name_slug': layer.slug,
                    'name': layer.name,
                },
                'count': len(relevant_data),
                'results': relevant_data,
            }
        )

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        layer, err = resolve_layer_from_payload(payload)
        if not layer:
            return Response(err, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = reindex_layer(layer, payload=payload)
        except Exception as exc:
            logger.exception('relevance reindex failed for layer_id=%s', layer.id)
            return Response(
                {'error': 'reindex_failed', 'detail': f'{type(exc).__name__}: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        relevant_data = get_layer_relevant_data(layer)
        return Response(
            {
                'success': True,
                'result': {
                    'pairs_written': result.get('pairs_written', 0),
                    'pairs_updated': result.get('pairs_updated', 0),
                    'pairs_deleted': result.get('pairs_deleted', 0),
                    'total_pairs': result.get('total_pairs', 0),
                    'state_backend_ids': result.get('state_backend_ids', []),
                },
                'layer': {
                    'geompapping_layer_id': layer.id,
                    'geompapping_layer_name_slug': layer.slug,
                    'name': layer.name,
                    'city': layer.city.slug if layer.city_id else None,
                    'state': layer.city.state_ref.slug if layer.city_id and layer.city.state_ref else None,
                },
                'relevant_layers': relevant_data,
            },
            status=status.HTTP_200_OK,
        )
