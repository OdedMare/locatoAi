import pytest
from pydantic import ValidationError

from app.service.dto import QueryRequest


def test_query_request_requires_boundaries():
    with pytest.raises(ValidationError):
        QueryRequest.model_validate({"query": "בתי ספר"})


def test_query_request_accepts_multipolygon_boundaries():
    request = QueryRequest.model_validate({
        "query": "בתי ספר",
        "boundaries": {
            "type": "MultiPolygon",
            "coordinates": [[[[34.0, 32.0], [34.1, 32.0], [34.1, 32.1],
                               [34.0, 32.1], [34.0, 32.0]]]],
        },
    })
    assert request.boundaries.to_shapely().is_valid
