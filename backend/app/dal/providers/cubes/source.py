"""Parse Cubes catalog source URLs."""

from typing import Dict
from urllib.parse import parse_qs, urlsplit

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError


class CubesSource:
    PARAMETER_PREFIX = "param_"
    DYNAMIC_PARAM_PREFIX = PARAMETER_PREFIX
    _QUERY_MODES = {"auto", "match_not", "legacy"}

    def database_name(self, layer: LayerMeta) -> str:
        ignored = {"cube", "v1", "db"}
        path = urlsplit(layer.source_url.strip()).path
        segments = [
            part for part in path.split("/")
            if part and part.lower() not in ignored
        ]
        if not segments:
            raise ProviderError(
                f"Layer {layer.id} has no Cubes database name in source_url; "
                "expected cubes://db/<dbname>"
            )
        return segments[-1]

    def query_mode(self, layer: LayerMeta) -> str:
        values = parse_qs(urlsplit(layer.source_url).query).get("query_mode", [])
        value = values[0] if values else "auto"
        return value if value in self._QUERY_MODES else "auto"

    def resolved_parameters(self, layer: LayerMeta) -> Dict[str, str]:
        query = parse_qs(urlsplit(layer.source_url).query)
        resolved = {}
        for key, values in query.items():
            if key.startswith(self.PARAMETER_PREFIX) and values:
                name = key[len(self.PARAMETER_PREFIX):]
                resolved[name] = values[0]
        return resolved
