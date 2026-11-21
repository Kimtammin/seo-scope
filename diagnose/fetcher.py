import logging

import requests
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

TIMEOUT = 5  # 초
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; SeoScopeBot/1.0)'}


class FetchError(APIException):
    """대상 URL 요청 실패. APIException을 상속해서 뷰에서 잡지 않아도 status_code로 응답된다."""

    def __init__(self, detail, status_code=502):
        super().__init__(detail)
        self.status_code = status_code


def fetch(url):
    """GET 요청. 404 같은 응답은 그대로 반환하고, 연결 실패·타임아웃만 FetchError로 바꾼다."""
    try:
        return requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.Timeout:
        logger.warning('요청 시간 초과: %s', url)
        raise FetchError(f'대상 서버가 {TIMEOUT}초 안에 응답하지 않았습니다.', status_code=504)
    except requests.RequestException as e:
        # 응답에는 원인을 노출하지 않고 서버 로그에만 남긴다
        logger.warning('요청 실패: %s (%s)', url, e)
        raise FetchError('대상 서버에 연결할 수 없습니다.')


def fetch_page(url):
    """진단할 HTML 페이지를 가져온다."""
    response = fetch(url)

    if response.status_code >= 400:
        raise FetchError(f'대상 페이지가 HTTP {response.status_code} 응답을 반환했습니다.')
    if 'html' not in response.headers.get('Content-Type', ''):
        raise FetchError('HTML 페이지가 아니라 진단할 수 없습니다.', status_code=422)

    return response
