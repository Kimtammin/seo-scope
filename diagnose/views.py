from rest_framework.response import Response
from rest_framework.views import APIView


class DiagnoseView(APIView):
    """POST /api/diagnose/ — URL을 받아 SEO 기본 항목을 진단한다."""

    def post(self, request):
        url = request.data.get('url')
        return Response({'url': url, 'results': []})
