# seo-scope

URL을 받아 해당 페이지의 SEO 기본 항목 5개를 점검하고, 항목별 pass / warn / fail 판정을 JSON으로 돌려주는 API입니다.

## 기술 스택

| 구분 | 사용 |
|---|---|
| 언어 | Python 3.12 |
| 프레임워크 | Django 5.2 (LTS), Django REST Framework 3.16 |
| HTTP 요청 | requests |
| HTML 파싱 | BeautifulSoup4 |
| API 문서 | drf-spectacular (Swagger UI) |
| 테스트 | Django test runner, unittest.mock |

## 설치 및 실행

```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 기본 테이블 생성 (Django 기본 앱용)
python manage.py migrate

# 4. 서버 실행
python manage.py runserver
```

## 사용 방법

### Swagger UI

1. `http://127.0.0.1:8000/api/docs/` 접속
2. `POST /api/diagnose/` 펼치기 → **Try it out**
3. **Examples**에서 `스마일코리아` / `Books to Scrape` / `응답 지연 (504)` 중 선택
4. **Execute**

### 직접 요청

```bash
curl -X POST http://127.0.0.1:8000/api/diagnose/ \
  -H "Content-Type: application/json" \
  -d '{"url": "https://smilekoreacorp.com/"}'
```

## 요청 / 응답

**요청**

```json
{ "url": "https://smilekoreacorp.com/" }
```

**성공 (200)**

```json
{
  "url": "https://smilekoreacorp.com/",
  "final_url": "https://www.smilekoreacorp.com/",
  "results": [
    { "item": "title_meta",  "status": "pass", "reason": "title 41자, description 76자" },
    { "item": "og_tags",     "status": "pass", "reason": "og:title, og:description, og:image 모두 있음" },
    { "item": "robots_txt",  "status": "pass", "reason": "robots.txt 있음, 이 페이지 크롤링 허용" },
    { "item": "sitemap_xml", "status": "pass", "reason": "sitemap 있음 (https://www.smilekoreacorp.com/sitemap.xml)" },
    { "item": "json_ld",     "status": "fail", "reason": "JSON-LD 없음" }
  ]
}
```

- `final_url`: 리다이렉트를 따라간 뒤 실제로 진단한 주소

**에러**

```json
{
  "error": {
    "status": 400,
    "message": "입력값이 올바르지 않습니다.",
    "fields": { "url": ["http 또는 https URL만 진단할 수 있습니다."] }
  }
}
```

- `fields`: 입력 검증 에러일 때만 필드별 상세, 그 외에는 `null`

## 응답 코드

| 코드 | 상황 |
|---|---|
| 200 | 진단 완료 |
| 400 | 잘못된 입력 (URL 형식 오류, http/https 아님, 2048자 초과, JSON 형식 오류) |
| 405 | POST 외 메서드 |
| 422 | 대상이 HTML 페이지가 아님 |
| 502 | 대상 서버 연결 실패, 또는 대상 페이지가 4xx/5xx 응답 |
| 504 | 대상 서버가 5초 안에 응답하지 않음 |

## 판정 기준

| 항목 | pass | warn | fail |
|---|---|---|---|
| title / description | 둘 다 있고 권장 길이 이내 | 길이가 권장 범위 밖 | 하나라도 없음 (빈 값 포함) |
| OG 태그 | og:title, og:description, og:image 모두 있음 | 일부만 있음 | 하나도 없음 |
| robots.txt | 있고 이 페이지 크롤링 허용 | 없음 (전체 허용 상태) | 이 페이지 크롤링 차단 |
| sitemap.xml | 있고 sitemap 형식 | 응답은 있지만 sitemap 형식 아님 | 없음 |
| JSON-LD | 있고 JSON 파싱 성공 | 있지만 JSON 형식 오류 | 없음 |

- 권장 길이: title 10~60자, description 50~160자 (상한은 검색 결과에서 잘리지 않는 일반적인 권장값, 하한은 지나치게 짧은 값을 거르기 위한 자체 기준)
- robots.txt가 없으면 크롤러는 전체 허용으로 보기 때문에 fail이 아닌 warn
- sitemap 위치는 robots.txt의 `Sitemap:` 지시문을 먼저 확인하고, 없으면 `/sitemap.xml`

## 프로젝트 구조

```
config/
  settings.py        DRF·Swagger·에러 핸들러 설정
  urls.py            /api/, /api/docs/ 라우팅
diagnose/
  views.py           POST /api/diagnose/ (검증 → 요청 → 점검 → 응답)
  serializers.py     입력 검증
  fetcher.py         외부 요청, 타임아웃·연결 실패 처리
  checks.py          점검 5개와 판정
  exceptions.py      에러 응답 형식 통일
  tests.py           테스트
```

## 설계 이유

### 기술 선택

| 결정 | 이유 |
|---|---|
| requests + BeautifulSoup | 페이지 1개와 robots.txt, sitemap.xml을 가져오는 작업이라, 크롤링 프레임워크(Scrapy)나 브라우저 도구(Playwright)는 과하다고 판단 |
| APIView + Serializer | 저장할 모델이 없는 단일 POST 엔드포인트. Generic View와 ViewSet은 모델(queryset)과 ModelSerializer 기반의 CRUD를 전제로 해서 맞지 않아, 가장 단순한 APIView 사용 |
| Django 5.2 LTS, 의존성 버전 고정 | 장기 지원 버전을 쓰고, 언제 설치해도 같은 환경이 되도록 고정 |

### 구조

| 결정 | 이유 |
|---|---|
| 검증 / 요청 / 판정 / 에러 형식을 파일로 분리 | 요청 방식과 판정 기준은 바뀌는 이유가 다름. 판정 함수는 HTML만 받아서 네트워크 없이 테스트 가능 |
| models, admin, migrations 제거 | 결과를 저장하지 않는 API라는 의도를 구조로 표현 |

### 외부 요청

| 결정 | 이유 |
|---|---|
| 타임아웃 5초 | 진단 1회에 페이지, robots.txt, sitemap.xml을 순서대로 요청해서 전체 대기 시간을 제한 |
| 재시도 없음 | 사용자가 응답을 기다리는 동기 API라 대기만 늘고, 느린 서버는 다시 요청해도 느림 |
| 최종 URL 기준으로 robots.txt, sitemap 확인 | 리다이렉트로 도메인이 바뀌는 경우(smilekoreacorp.com → www) 실제 페이지의 도메인을 봐야 정확 |

### 응답과 에러

| 결정 | 이유 |
|---|---|
| 502 / 504 / 422 구분 | 우리 서버 오류(500)와 대상 서버 문제를 구분 |
| `FetchError`가 `APIException` 상속 | 뷰에 try/except 없이 DRF가 상태 코드에 맞게 응답 |
| 에러 형식 `{"error": {...}}` 통일 | DRF 기본은 입력 검증(`{"url": [...]}`)과 그 외(`{"detail": ...}`)의 형식이 달라서, 클라이언트가 한 가지 형식만 처리하도록 |

## 테스트

```bash
python manage.py test
```

- 14개 테스트: 판정 기준, 타임아웃(504)·연결 실패(502) 변환, API 전체 흐름
- 외부 요청은 `unittest.mock`으로 대체해 네트워크 없이 항상 같은 결과로 실행됩니다.

## 한계 및 개선 방향

과제 범위에 맞춰 아래 항목은 의도적으로 넣지 않았습니다.

- **SSRF 방지**: 내부망·사설 IP로의 요청을 막지 않습니다. 운영 시 DNS 조회 결과 검사와 네트워크 레벨 차단이 필요합니다.
- **JS 렌더링**: 서버가 보낸 원본 HTML만 진단합니다. SPA는 결과가 다를 수 있으며, 필요하면 `fetcher`만 Playwright로 교체할 수 있습니다.
- **길이 기준**: 글자 수 기준이라 실제 검색 결과의 픽셀 폭, 한글 폭과는 차이가 있습니다.
- **noindex**: `<meta name="robots" content="noindex">`, `X-Robots-Tag` 헤더는 점검하지 않습니다.
- **요청 처리**: 페이지, robots.txt, sitemap.xml을 순차로 요청하고 응답 크기를 제한하지 않습니다. 동시 요청과 크기 제한으로 개선할 수 있습니다.
- **운영 설정**: `SECRET_KEY`, `DEBUG=True`는 로컬 실행용입니다. 운영 시 환경변수로 분리하고 gunicorn 등으로 실행해야 합니다.
