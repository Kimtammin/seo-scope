from urllib.parse import urlparse

from rest_framework import serializers


class DiagnoseRequestSerializer(serializers.Serializer):
    """진단 요청 본문 { "url": "..." } 검증."""

    # URLField: Django URLValidator로 형식 검사 + 앞뒤 공백 자동 제거
    # 2048: 브라우저·검색엔진이 사실상 다루는 URL 길이 상한으로 흔히 쓰는 값
    url = serializers.URLField(max_length=2048)

    def validate_url(self, value):
        # URLField는 ftp/ftps도 통과시키므로, 웹 페이지 진단에 맞게 http/https만 허용
        if urlparse(value).scheme not in ('http', 'https'):
            raise serializers.ValidationError('http 또는 https URL만 진단할 수 있습니다.')
        return value
