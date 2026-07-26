import pytest
from pydantic import ValidationError

from app.bl.query_orchestrator.query_outcome import QueryOutcome
from app.service.query.request import QueryRequest
from app.service.query.response import QueryResponse


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


def test_count_response_omits_redundant_feature_collection():
    response = QueryResponse.from_outcome(QueryOutcome(
        status="ok", features=None, scalar_result=123456,
    ))

    assert response.scalar_result == 123456
    assert response.features is None
