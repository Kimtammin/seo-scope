from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .checks import run_checks
from .fetcher import fetch_page
from .serializers import DiagnoseRequestSerializer

# Swagger UI(/api/docs/)에 표시할 요청·응답 예시
REQUEST_EXAMPLES = [
    OpenApiExample('스마일코리아', value={'url': 'https://smilekoreacorp.com/'}, request_only=True),
    OpenApiExample('Books to Scrape', value={'url': 'https://books.toscrape.com/'}, request_only=True),
    OpenApiExample('응답 지연 (504)', value={'url': 'https://httpbin.org/delay/10'}, request_only=True),
]


def error_example(status, message, fields=None):
    return OpenApiExample(
        f'{status} 에러',
        value={'error': {'status': status, 'message': message, 'fields': fields}},
        response_only=True,
    )


RESPONSES = {
    200: OpenApiResponse(
        OpenApiTypes.OBJECT,
        description='진단 성공',
        examples=[OpenApiExample('진단 결과', response_only=True, value={
            'url': 'https://smilekoreacorp.com/',
            'final_url': 'https://www.smilekoreacorp.com/',
            'results': [
                {'item': 'title_meta', 'status': 'pass', 'reason': 'title 41자, description 76자'},
                {'item': 'og_tags', 'status': 'pass', 'reason': 'og:title, og:description, og:image 모두 있음'},
                {'item': 'robots_txt', 'status': 'pass', 'reason': 'robots.txt 있음, 이 페이지 크롤링 허용'},
                {'item': 'sitemap_xml', 'status': 'pass', 'reason': 'sitemap 있음 (https://www.smilekoreacorp.com/sitemap.xml)'},
                {'item': 'json_ld', 'status': 'fail', 'reason': 'JSON-LD 없음'},
            ],
        })],
    ),
    400: OpenApiResponse(OpenApiTypes.OBJECT, description='입력값 오류', examples=[
        error_example(400, '입력값이 올바르지 않습니다.', {'url': ['http 또는 https URL만 진단할 수 있습니다.']}),
    ]),
    422: OpenApiResponse(OpenApiTypes.OBJECT, description='HTML 페이지가 아님', examples=[
        error_example(422, 'HTML 페이지가 아니라 진단할 수 없습니다.'),
    ]),
    502: OpenApiResponse(OpenApiTypes.OBJECT, description='대상 서버 연결 실패 또는 4xx/5xx 응답', examples=[
        error_example(502, '대상 서버에 연결할 수 없습니다.'),
    ]),
    504: OpenApiResponse(OpenApiTypes.OBJECT, description='대상 서버 응답 시간 초과', examples=[
        error_example(504, '대상 서버가 5초 안에 응답하지 않았습니다.'),
    ]),
}


class DiagnoseView(APIView):
    """POST /api/diagnose/ — URL을 받아 SEO 기본 항목을 진단한다."""

    @extend_schema(
        summary='SEO 진단',
        request=DiagnoseRequestSerializer,
        responses=RESPONSES,
        examples=REQUEST_EXAMPLES,
    )
    def post(self, request):
        # 검증 실패 시 400 (에러 형식은 exceptions.py에서 통일)
        serializer = DiagnoseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.validated_data['url']

        # 요청 실패 시 FetchError → 502/504/422
        page = fetch_page(url)

        return Response({'url': url, 'final_url': page.url, 'results': run_checks(page)})
