import json

import geopandas as gpd
from shapely.geometry import Point

from app.bl.agent.generate_layer_metadata import LayerMetadataGenerator
from app.bl.ports import LayerField, LayerSchema
from app.dal.providers.registry import InMemoryProviderRegistry


class SampleProvider:
    def fetch_features(self, layer, now=None):
        return gpd.GeoDataFrame(
            {
                "entity_name": [f"school-{index}" for index in range(15)],
                "city": ["Tel Aviv"] * 15,
            },
            geometry=[Point(index, index) for index in range(15)],
            crs="EPSG:4326",
        )

    def describe_schema(self, layer):
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Point",
            fields=[
                LayerField(name="entity_name", type="string"),
                LayerField(name="city", type="string"),
            ],
        )

    def sample_field_values(self, layer, field, limit=20):
        return []


class CapturingLlm:
    def __init__(self):
        self.user = None

    def complete_json(self, system, user):
        self.user = json.loads(user)
        return {
            "description": " שכבת מוסדות חינוך לפי שם ועיר ",
            "tags": ["חינוך", "Education", "חינוך", "", 7],
            "_usage": {"total_tokens": 10},
        }


def test_generates_editable_metadata_from_ten_random_entities():
    providers = InMemoryProviderRegistry()
    providers.register("sample", SampleProvider())
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="בתי ספר", provider_name="sample", source_url="sample://schools"
    )

    assert result.sample_count == 10
    assert len(llm.user["random_entity_sample"]) == 10
    assert all("geometry" not in row for row in llm.user["random_entity_sample"])
    assert llm.user["geometry_type"] == "Point"
    assert result.description == "שכבת מוסדות חינוך לפי שם ועיר"
    assert result.tags == ["חינוך", "Education"]
