"""Parse FLAPI Flow Package source URLs."""

from typing import Optional
from urllib.parse import parse_qs, urlsplit

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError


class FlapiSource:
    """Reads the package id and cube configuration out of ``source_url``.

    A package source is ``flapi://package/<id>`` plus the four cube settings the
    catalog UI persists: ``input_cube_name``, ``input_cube_parameter``,
    ``input_cube_kind`` (``time`` | ``geo``), and ``output_cube_name``. Every
    other package parameter is fixed inside the package itself, and flunks owns
    the request, so nothing else is parsed here.
    """

    def package_id(self, layer: LayerMeta) -> str:
        parsed = urlsplit(layer.source_url.strip())
        ignored = {"id", "package"}
        parts = [
            part for part in parsed.path.split("/")
            if part and part.casefold() not in ignored
        ]
        if not parts:
            raise ProviderError(
                "Flow Package source must be flapi://package/<packageId>"
            )
        return parts[-1]

    @staticmethod
    def package_input_cube_name(layer: LayerMeta) -> Optional[str]:
        return FlapiSource._option(layer, "input_cube_name")

    @staticmethod
    def package_input_cube_parameter(layer: LayerMeta) -> Optional[str]:
        return FlapiSource._option(layer, "input_cube_parameter")

    @staticmethod
    def package_output_cube_name(layer: LayerMeta) -> Optional[str]:
        return FlapiSource._option(layer, "output_cube_name")

    @staticmethod
    def package_input_cube_kind(layer: LayerMeta) -> str:
        value = (FlapiSource._option(layer, "input_cube_kind") or "").lower()
        return "geo" if value == "geo" else "time"

    @staticmethod
    def _option(layer: LayerMeta, key: str) -> Optional[str]:
        query = parse_qs(urlsplit(layer.source_url).query)
        value = query.get(key, [None])[0]
        return value.strip() if value else None
