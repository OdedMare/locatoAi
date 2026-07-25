from types import SimpleNamespace
from typing import Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.dal.providers.flapi.flunks_metadata_patch import FlunksMetadataPatch
from app.dal.providers.flapi.package_debug import FlowPackageDebug


def response_models():
    class MetaData(BaseModel):
        isPartialSuccess: Optional[str] = None

    class FlowResults(BaseModel):
        metadata: MetaData

    return SimpleNamespace(MetaData=MetaData, FlowResults=FlowResults)


def test_patch_rebuilds_metadata_before_flow_results():
    models = response_models()
    payload = {"metadata": {"isPartialSuccess": False}}

    with pytest.raises(ValidationError):
        models.FlowResults.model_validate(payload)

    assert FlunksMetadataPatch.apply(models) is True
    result = models.FlowResults.model_validate(payload)

    assert result.metadata.isPartialSuccess is False
    assert models.FlowResults.model_validate(
        {"metadata": {"isPartialSuccess": "false"}}
    ).metadata.isPartialSuccess == "false"
    assert models.FlowResults.model_validate(
        {"metadata": {"isPartialSuccess": None}}
    ).metadata.isPartialSuccess is None


def test_patch_finds_snake_case_field_by_alias():
    class MetaData(BaseModel):
        is_partial_success: Optional[str] = Field(
            default=None, alias="isPartialSuccess"
        )

    class FlowResults(BaseModel):
        metadata: MetaData

    models = SimpleNamespace(MetaData=MetaData, FlowResults=FlowResults)

    assert FlunksMetadataPatch.apply(models) is True
    result = FlowResults.model_validate(
        {"metadata": {"isPartialSuccess": False}}
    )
    assert result.metadata.is_partial_success is False


def test_validation_error_preview_is_bounded():
    class TextResult(BaseModel):
        value: str

    with pytest.raises(ValidationError) as caught:
        TextResult.model_validate({"value": ["x" * 1000]})

    message = FlowPackageDebug.exception(caught.value)

    assert "value=string_type" in message
    assert len(message) < 300
