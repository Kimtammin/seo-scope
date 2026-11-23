import json
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from .fetcher import FetchError, fetch

TITLE_LENGTH = (10, 60)
DESCRIPTION_LENGTH = (50, 160)
OG_TAGS = ('og:title', 'og:description', 'og:image')


def run_checks(page):
    """가져온 페이지로 5개 항목을 점검한다."""
    soup = BeautifulSoup(page.content, 'html.parser')
    robots = parse_robots(fetch_or_none(urljoin(page.url, '/robots.txt')))

    return [
        check_title_meta(soup),
        check_og_tags(soup),
        check_robots(robots, page.url),
        check_sitemap(robots, page.url),
        check_json_ld(soup),
    ]


def check_title_meta(soup):
    title = soup.title.get_text(strip=True) if soup.title else ''
    # name="Description"처럼 대소문자를 섞어 쓰는 사이트도 있어서 소문자로 비교
    tag = soup.find('meta', attrs={'name': lambda name: name and name.lower() == 'description'})
    description = tag.get('content', '').strip() if tag else ''

    if not title or not description:
        missing = [name for name, value in (('title', title), ('description', description)) if not value]
        return make_result('title_meta', 'fail', f'{", ".join(missing)} 없음')

    reason = f'title {len(title)}자, description {len(description)}자'
    if is_in_range(title, TITLE_LENGTH) and is_in_range(description, DESCRIPTION_LENGTH):
        return make_result('title_meta', 'pass', reason)
    return make_result(
        'title_meta', 'warn',
        f'{reason} (권장: title {TITLE_LENGTH[0]}~{TITLE_LENGTH[1]}자, '
        f'description {DESCRIPTION_LENGTH[0]}~{DESCRIPTION_LENGTH[1]}자)',
    )


def check_og_tags(soup):
    missing = []
    for prop in OG_TAGS:
        tag = soup.find('meta', property=prop)
        if not tag or not tag.get('content', '').strip():
            missing.append(prop)

    if not missing:
        return make_result('og_tags', 'pass', 'og:title, og:description, og:image 모두 있음')
    if len(missing) == len(OG_TAGS):
        return make_result('og_tags', 'fail', 'OG 태그 없음')
    return make_result('og_tags', 'warn', f'{", ".join(missing)} 없음')


def check_robots(robots, page_url):
    if robots is None:
        # robots.txt가 없으면 크롤러는 전체 허용으로 본다
        return make_result('robots_txt', 'warn', 'robots.txt 없음 (크롤링 전체 허용 상태)')
    if not robots.can_fetch('*', page_url):
        return make_result('robots_txt', 'fail', 'robots.txt가 이 페이지의 크롤링을 차단함')
    return make_result('robots_txt', 'pass', 'robots.txt 있음, 이 페이지 크롤링 허용')


def check_sitemap(robots, page_url):
    # robots.txt에 Sitemap 위치가 적혀 있으면 그걸 쓰고, 없으면 기본 위치를 확인한다
    sitemaps = robots.site_maps() if robots else None
    sitemap_url = sitemaps[0] if sitemaps else urljoin(page_url, '/sitemap.xml')

    response = fetch_or_none(sitemap_url)
    if response is None:
        return make_result('sitemap_xml', 'fail', f'sitemap 없음 ({sitemap_url})')
    if b'<urlset' not in response.content and b'<sitemapindex' not in response.content:
        return make_result('sitemap_xml', 'warn', f'sitemap 형식이 아님 ({sitemap_url})')
    return make_result('sitemap_xml', 'pass', f'sitemap 있음 ({sitemap_url})')


def check_json_ld(soup):
    scripts = soup.find_all('script', type='application/ld+json')
    if not scripts:
        return make_result('json_ld', 'fail', 'JSON-LD 없음')

    types = []
    for script in scripts:
        try:
            data = json.loads(script.string or '')
        except json.JSONDecodeError:
            return make_result('json_ld', 'warn', 'JSON-LD가 있지만 JSON 형식 오류')
        # JSON-LD는 객체 하나, 객체 리스트, @graph 묶음 형태가 있다
        if isinstance(data, dict):
            items = data.get('@graph', [data])
        elif isinstance(data, list):
            items = data
        else:
            items = []
        types += [str(item.get('@type')) for item in items if isinstance(item, dict) and item.get('@type')]

    return make_result('json_ld', 'pass', f'JSON-LD {len(scripts)}개 ({", ".join(types) or "@type 없음"})')


def make_result(item, status, reason):
    return {'item': item, 'status': status, 'reason': reason}


def is_in_range(text, length_range):
    return length_range[0] <= len(text) <= length_range[1]


def fetch_or_none(url):
    """robots.txt·sitemap용. 요청 실패나 4xx/5xx면 None (없는 것으로 본다)."""
    try:
        response = fetch(url)
    except FetchError:
        return None
    return response if response.status_code < 400 else None


def parse_robots(response):
    if response is None:
        return None
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser
