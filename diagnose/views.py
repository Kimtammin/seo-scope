from rest_framework.response import Response
from rest_framework.views import APIView

from .checks import run_checks
from .fetcher import fetch_page
from .serializers import DiagnoseRequestSerializer


class DiagnoseView(APIView):
    """POST /api/diagnose/ — URL을 받아 SEO 기본 항목을 진단한다."""

    def post(self, request):
        # 검증 실패 시 400 (에러 형식은 exceptions.py에서 통일)
        serializer = DiagnoseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.validated_data['url']

        # 요청 실패 시 FetchError → 502/504/422
        page = fetch_page(url)

        return Response({'url': url, 'final_url': page.url, 'results': run_checks(page)})
