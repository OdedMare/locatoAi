"""Render sanitized catalog metadata for layer selection."""

import re


class LayerCatalogFormatter:
    def format(self, layers, diet: bool = False) -> str:
        renderer = self._diet_line if diet else self._full_line
        return "\n".join(renderer(layer) for layer in layers)

    def _diet_line(self, layer) -> str:
        return "{id}|{name}|{tags}|{desc}".format(
            id=layer.id,
            name=self.sanitize(layer.name, 60),
            tags=",".join(layer.tags[:6]),
            desc=self.sanitize(layer.description, 100),
        )

    def _full_line(self, layer) -> str:
        return "- id: {id} | name: {name} | tags: {tags} | description: {desc}".format(
            id=layer.id,
            name=self.sanitize(layer.name, 80),
            tags=",".join(layer.tags[:10]),
            desc=self.sanitize(layer.description, 200),
        )

    @staticmethod
    def sanitize(text: str, limit: int) -> str:
        return re.sub(r"\s+", " ", text or "").strip()[:limit]
