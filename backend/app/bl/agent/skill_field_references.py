"""Resolve stable layer-field references embedded by Agent Studio."""

import re
from urllib.parse import unquote


class SkillFieldReferences:
    _PATTERN = re.compile(r"@field\[([^/\]\s]+)/([^\]\r\n]+)\]")

    def __init__(self, catalog) -> None:
        self._catalog = catalog

    def render(self, content: str) -> str:
        return self._PATTERN.sub(self._resolve, content)

    def validate(self, content: str) -> None:
        self.render(content)

    def _resolve(self, match) -> str:
        layer_id, field_name = map(unquote, match.groups())
        layer = self._catalog.get_layer(layer_id)
        fields = {field.name for field in self._catalog.get_schema(layer_id).fields}
        if field_name not in fields:
            raise ValueError(
                "Skill field reference is unavailable: "
                + layer_id + "/" + field_name
            )
        return "@{} (layer `{}`, id `{}`)".format(
            field_name, layer.name, layer.id
        )
