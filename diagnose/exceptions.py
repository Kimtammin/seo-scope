from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """에러 응답을 {"error": {"status", "message", "fields"}} 형태로 통일한다."""
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(response.data, dict) and 'detail' in response.data:
        message, fields = str(response.data['detail']), None
    else:
        message, fields = '입력값이 올바르지 않습니다.', response.data

    response.data = {'error': {'status': response.status_code, 'message': message, 'fields': fields}}
    return response
