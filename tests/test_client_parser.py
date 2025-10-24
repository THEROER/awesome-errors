from datetime import datetime

from awesome_errors import ErrorResponseParser


class TestErrorResponseParser:
    def test_parse_legacy_envelope(self):
        payload = {
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "Missing user",
                "details": {"resource": "user"},
                "timestamp": datetime.now().isoformat(),
                "request_id": "req-123",
            }
        }

        error = ErrorResponseParser.parse_response(payload, status_code=404)

        assert error.code == "RESOURCE_NOT_FOUND"
        assert error.status_code == 404
        assert error.details["resource"] == "user"

    def test_parse_problem_detail(self):
        payload = {
            "type": "about:blank",
            "title": "Session expired",
            "status": 401,
            "detail": "Session expired",
            "instance": "/sessions/1",
            "code": "SESSION_EXPIRED",
            "timestamp": datetime.now().isoformat(),
            "request_id": "req-456",
            "details": {"session": 1},
        }

        error = ErrorResponseParser.parse_response(payload, status_code=401)

        assert error.code == "SESSION_EXPIRED"
        assert error.status_code == 401
        assert error.details["session"] == 1

    def test_parse_invalid_payload_fallback(self):
        error = ErrorResponseParser.parse_response({}, status_code=500)

        assert error.code == "UNKNOWN_ERROR"
        assert error.status_code == 500
