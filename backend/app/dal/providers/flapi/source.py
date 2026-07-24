"""Parse FLAPI resource URLs and persisted package inputs."""

import json
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlsplit

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError


class FlapiSource:
    PACKAGE_INPUT_PREFIX = "input_"

    def resource_type(self, layer: LayerMeta) -> str:
        parsed = urlsplit(layer.source_url.strip())
        if parsed.scheme.casefold() == "package":
            return "package"
        if (
            parsed.scheme.casefold() == "flapi"
            and parsed.netloc.casefold() == "package"
        ):
            return "package"
        return "cube"

    def package_id(self, layer: LayerMeta) -> str:
        if self.resource_type(layer) != "package":
            raise ProviderError("FLAPI source is not a Flow Package")
        parsed = urlsplit(layer.source_url.strip())
        ignored = {"id", "package", "v1", "v3"}
        parts = [
            part for part in parsed.path.split("/")
            if part and part.casefold() not in ignored
        ]
        if not parts:
            raise ProviderError(
                "Flow Package source must be flapi://package/<packageId>"
            )
        return parts[-1]

    def package_inputs(self, layer: LayerMeta) -> Dict[str, Any]:
        query = parse_qs(urlsplit(layer.source_url).query)
        values: Dict[str, Any] = {}
        for key, items in query.items():
            if not key.startswith(self.PACKAGE_INPUT_PREFIX) or not items:
                continue
            name = key[len(self.PACKAGE_INPUT_PREFIX):]
            try:
                values[name] = json.loads(items[0])
            except (TypeError, ValueError) as exc:
                raise ProviderError(
                    f"Flow Package input '{name}' is not valid JSON"
                ) from exc
        return values

    @staticmethod
    def package_queries(layer: LayerMeta) -> List[str]:
        query = parse_qs(urlsplit(layer.source_url).query)
        return [value for value in query.get("query", []) if value]

    def execution_params(self, layer: LayerMeta):
        query = parse_qs(urlsplit(layer.source_url).query)
        params = [
            ("queries", value)
            for value in query.get("query", [])
            if value
        ]
        for name in (
            "allQueries", "lastQueries", "executeContinuedProcess",
            "isPartialSuccess",
        ):
            if name not in query:
                continue
            value = query[name][0].casefold()
            if value not in ("true", "false"):
                raise ProviderError(
                    f"FLAPI package option '{name}' must be true or false"
                )
            params.append((name, value))
        if not params:
            params.append(("lastQueries", "true"))
        return params
