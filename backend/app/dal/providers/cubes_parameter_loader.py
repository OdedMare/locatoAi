"""Discover Cubes parameter names and hydrate their full definitions."""

from typing import Callable, List, Optional
from urllib.parse import quote

from app.common.errors.provider_error import ProviderError


class CubesParameterLoader:
    def load(
        self,
        database: str,
        embedded: object,
        fetch_json: Callable[[str, str], object],
    ) -> List[dict]:
        summaries = self._summaries(database, embedded, fetch_json)
        return [
            self._definition(database, summary, fetch_json)
            for summary in summaries
        ]

    def _summaries(self, database, embedded, fetch_json) -> List[object]:
        if isinstance(embedded, list):
            return embedded
        path = f"/cube/v1/{database}/parameters"
        payload = fetch_json(path, "parameters")
        if isinstance(payload, dict):
            payload = payload.get("Parameters") or payload.get("parameters")
        if not isinstance(payload, list):
            raise ProviderError("Cubes parameters response must be a JSON array")
        return payload

    def _definition(self, database, summary, fetch_json) -> dict:
        name = self._name(summary)
        if name is None:
            raise ProviderError("Cubes returned a parameter without a name")
        if self._is_complete(summary):
            return dict(summary)
        parameter = quote(name, safe="")
        path = f"/cube/v1/{database}/parameters/{parameter}"
        detail = self._detail(fetch_json(path, f"parameter '{name}'"), name)
        base = dict(summary) if isinstance(summary, dict) else {"Name": name}
        return {**base, **detail, "Name": name}

    @staticmethod
    def _name(summary: object) -> Optional[str]:
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        if not isinstance(summary, dict):
            return None
        value = summary.get("Name") or summary.get("name")
        return str(value).strip() if value not in (None, "") else None

    @staticmethod
    def _is_complete(summary: object) -> bool:
        if not isinstance(summary, dict):
            return False
        return any(
            key in summary
            for key in ("IsRequired", "isRequired", "is_required", "required")
        )

    @staticmethod
    def _detail(payload: object, name: str) -> dict:
        if isinstance(payload, list):
            payload = next((item for item in payload if isinstance(item, dict)), None)
        if isinstance(payload, dict):
            nested = payload.get("Parameter") or payload.get("parameter")
            if isinstance(nested, dict):
                payload = nested
            else:
                values = payload.get("Parameters") or payload.get("parameters")
                if isinstance(values, list):
                    payload = next(
                        (item for item in values if isinstance(item, dict)), None
                    )
        if not isinstance(payload, dict):
            raise ProviderError(
                f"Cubes parameter '{name}' response must be a JSON object"
            )
        return payload
