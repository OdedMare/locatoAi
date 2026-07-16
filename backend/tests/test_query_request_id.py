from starlette.requests import Request

from app.service.query_router import _request_id


def request_with_id(value: str) -> Request:
    return Request({
        "type": "http",
        "headers": [(b"x-request-id", value.encode("utf-8"))],
    })


def test_query_reuses_valid_client_request_id():
    assert _request_id(request_with_id("browser-request_123")) == "browser-request_123"


def test_query_replaces_unsafe_client_request_id():
    generated = _request_id(request_with_id("unsafe id with spaces"))
    assert generated != "unsafe id with spaces"
    assert len(generated) == 32
