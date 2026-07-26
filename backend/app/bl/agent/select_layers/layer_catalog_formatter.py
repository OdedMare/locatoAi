"""Render sanitized catalog metadata for layer selection."""

import re


class LayerCatalogFormatter:
    def format(self, layers, diet: bool = False) -> str:
        renderer = self._diet_line if diet else self._full_line
        return "\n".join(renderer(layer) for layer in layers)

    def _diet_line(self, layer) -> str:
        return "{id}|{provider}|{name}|{tags}|profiles={profiles}|{desc}".format(
            id=layer.id,
            provider=layer.provider,
            name=self.sanitize(layer.name, 60),
            tags=",".join(layer.tags[:6]),
            profiles=",".join(layer.profiles[:4]),
            desc=self.sanitize(layer.description, 100),
        )

    def _full_line(self, layer) -> str:
        return "- id: {id} | provider: {provider} | name: {name} | tags: {tags} | profiles: {profiles} | description: {desc}".format(
            id=layer.id,
            provider=layer.provider,
            name=self.sanitize(layer.name, 80),
            tags=",".join(layer.tags[:10]),
            profiles=",".join(layer.profiles[:6]),
            desc=self.sanitize(layer.description, 200),
        )

    @staticmethod
    def sanitize(text: str, limit: int) -> str:
        return re.sub(r"\s+", " ", text or "").strip()[:limit]
