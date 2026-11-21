from unittest.mock import Mock, patch
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from .checks import check_json_ld, check_og_tags, check_robots, check_sitemap, check_title_meta
from .fetcher import FetchError, fetch

PAGE_URL = 'https://example.com/'

GOOD_HTML = '''
<html><head>
<title>스마일코리아 SEO 진단 테스트 페이지입니다</title>
<meta name="description" content="SEO 진단 API 테스트를 위한 페이지입니다. title, description, OG 태그, JSON-LD가 모두 들어 있습니다.">
<meta property="og:title" content="테스트">
<meta property="og:description" content="테스트 설명">
<meta property="og:image" content="https://example.com/og.png">
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Organization"}</script>
</head><body></body></html>
'''


def make_soup(html):
    return BeautifulSoup(html, 'html.parser')


def make_robots(*lines):
    parser = RobotFileParser()
    parser.parse(lines)
    return parser


def fake_response(url, status_code=200, content=b'', content_type='text/html'):
    """requests.get()이 돌려주는 응답을 흉내 낸 객체."""
    return Mock(
        url=url,
        status_code=status_code,
        headers={'Content-Type': content_type},
        content=content,
        text=content.decode(),
    )


class HtmlCheckTests(SimpleTestCase):
    """title/description, OG, JSON-LD 판정 (HTML 문자열만으로 확인)."""

    def test_all_pass_with_good_html(self):
        soup = make_soup(GOOD_HTML)
        self.assertEqual(check_title_meta(soup)['status'], 'pass')
        self.assertEqual(check_og_tags(soup)['status'], 'pass')
        self.assertEqual(check_json_ld(soup)['status'], 'pass')

    def test_all_fail_with_empty_html(self):
        soup = make_soup('<html></html>')
        self.assertEqual(check_title_meta(soup)['status'], 'fail')
        self.assertEqual(check_og_tags(soup)['status'], 'fail')
        self.assertEqual(check_json_ld(soup)['status'], 'fail')

    def test_empty_description_is_fail(self):
        # books.toscrape.com처럼 태그는 있지만 내용이 빈 경우
        html = '<title>제목이 충분히 긴 페이지입니다</title><meta name="description" content="  ">'
        self.assertEqual(check_title_meta(make_soup(html))['status'], 'fail')

    def test_invalid_json_ld_is_warn(self):
        html = '<script type="application/ld+json">{"@type": </script>'
        self.assertEqual(check_json_ld(make_soup(html))['status'], 'warn')


class RobotsCheckTests(SimpleTestCase):
    def test_allowed_is_pass(self):
        robots = make_robots('User-agent: *', 'Allow: /')
        self.assertEqual(check_robots(robots, PAGE_URL)['status'], 'pass')

    def test_blocked_path_is_fail(self):
        robots = make_robots('User-agent: *', 'Disallow: /admin/')
        self.assertEqual(check_robots(robots, PAGE_URL)['status'], 'pass')
        self.assertEqual(check_robots(robots, PAGE_URL + 'admin/page')['status'], 'fail')

    def test_missing_robots_is_warn(self):
        self.assertEqual(check_robots(None, PAGE_URL)['status'], 'warn')


@patch('diagnose.checks.fetch')
class SitemapCheckTests(SimpleTestCase):
    def test_uses_location_from_robots(self, mock_fetch):
        mock_fetch.return_value = fake_response('https://example.com/map.xml', content=b'<sitemapindex>')
        robots = make_robots('User-agent: *', 'Allow: /', 'Sitemap: https://example.com/map.xml')

        self.assertEqual(check_sitemap(robots, PAGE_URL)['status'], 'pass')
        mock_fetch.assert_called_once_with('https://example.com/map.xml')

    def test_not_found_is_fail(self, mock_fetch):
        mock_fetch.return_value = fake_response(PAGE_URL + 'sitemap.xml', status_code=404)
        self.assertEqual(check_sitemap(None, PAGE_URL)['status'], 'fail')


@patch('diagnose.fetcher.requests.get')
class FetcherTests(SimpleTestCase):
    def test_timeout_becomes_504(self, mock_get):
        mock_get.side_effect = requests.Timeout()
        with self.assertRaises(FetchError) as ctx:
            fetch(PAGE_URL)
        self.assertEqual(ctx.exception.status_code, 504)

    def test_connection_error_becomes_502(self, mock_get):
        mock_get.side_effect = requests.ConnectionError()
        with self.assertRaises(FetchError) as ctx:
            fetch(PAGE_URL)
        self.assertEqual(ctx.exception.status_code, 502)


@patch('diagnose.fetcher.requests.get')
class DiagnoseApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def post(self, data):
        return self.client.post('/api/diagnose/', data, format='json')

    def test_diagnose_all_pass(self, mock_get):
        responses = {
            PAGE_URL: fake_response(PAGE_URL, content=GOOD_HTML.encode()),
            PAGE_URL + 'robots.txt': fake_response(
                PAGE_URL + 'robots.txt', content=b'User-agent: *\nAllow: /', content_type='text/plain'),
            PAGE_URL + 'sitemap.xml': fake_response(
                PAGE_URL + 'sitemap.xml', content=b'<urlset></urlset>', content_type='application/xml'),
        }
        mock_get.side_effect = lambda url, **kwargs: responses[url]

        response = self.post({'url': PAGE_URL})

        self.assertEqual(response.status_code, 200)
        statuses = [r['status'] for r in response.json()['results']]
        self.assertEqual(statuses, ['pass'] * 5)

    def test_invalid_url_returns_400_without_request(self, mock_get):
        response = self.post({'url': 'ftp://example.com'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('url', response.json()['error']['fields'])
        mock_get.assert_not_called()

    def test_timeout_returns_504(self, mock_get):
        mock_get.side_effect = requests.Timeout()

        response = self.post({'url': 'https://httpbin.org/delay/10'})

        self.assertEqual(response.status_code, 504)
        self.assertIn('응답하지 않았습니다', response.json()['error']['message'])
