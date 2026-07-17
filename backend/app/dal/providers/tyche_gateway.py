"""HTTP and pagination boundary for Tyche."""

from typing import List, Optional, Set

import httpx

from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.tyche_feature_mapper import TycheFeatureMapper


class TycheGateway:
    _PATH = "/coordinate/v1/ourforces"
    _TIMEOUT_SECONDS = 30
    _PAGE_SIZE = 10000
    _MAX_ROWS = 100000

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        mapper: TycheFeatureMapper,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._store = settings_store
        self._mapper = mapper
        self._transport = transport

    def fetch(self, body_factory, limit: Optional[int]) -> List[dict]:
        rows: List[dict] = []
        tracker = None
        seen: Set[str] = set()
        has_more = False
        with self._client() as client:
            while self._can_fetch(rows, limit):
                payload = self._post(client, body_factory(self._page_size(rows, limit), tracker))
                rows = self._mapper.deduplicate(rows + self._page_rows(payload))
                has_more = bool(payload.get("hasMoreResults"))
                if not has_more or self._limit_reached(rows, limit):
                    break
                tracker = self._next_tracker(payload, seen)
        self._validate_cap(rows, limit, has_more)
        return rows[:limit] if limit is not None else rows

    def _client(self) -> httpx.Client:
        settings = self._store.get()
        self._validate_settings(settings)
        return httpx.Client(
            base_url=settings.tyche_base_url,
            headers=self._headers(settings.tyche_username, settings.tyche_token),
            timeout=self._TIMEOUT_SECONDS,
            verify=settings.tyche_verify_tls,
            transport=self._transport,
        )

    @staticmethod
    def _validate_settings(settings) -> None:
        if not settings.tyche_base_url:
            raise ProviderError("Tyche base URL is not configured — set tyche_base_url")
        if not settings.tyche_username:
            raise ProviderError("Tyche username is not configured — set tyche_username")
        if not settings.tyche_token:
            raise ProviderError("Tyche authorization token is not configured — set tyche_token")

    @staticmethod
    def _headers(username: str, token: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "username": username,
            "Authorization": token,
        }

    def _post(self, client: httpx.Client, body: dict) -> dict:
        try:
            response = client.post(self._PATH, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Tyche request failed ({self._PATH}): {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"Tyche returned invalid JSON ({self._PATH}): {exc}") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Tyche response must be a JSON object")
        return payload

    @staticmethod
    def _page_rows(payload: dict) -> List[dict]:
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise ProviderError("Tyche response must contain a results array")
        return [item for item in rows if isinstance(item, dict)]

    def _page_size(self, rows: List[dict], limit: Optional[int]) -> int:
        remaining = (limit - len(rows)) if limit is not None else self._MAX_ROWS - len(rows)
        return min(self._PAGE_SIZE, remaining)

    def _can_fetch(self, rows: List[dict], limit: Optional[int]) -> bool:
        return self._page_size(rows, limit) > 0

    @staticmethod
    def _limit_reached(rows: List[dict], limit: Optional[int]) -> bool:
        return limit is not None and len(rows) >= limit

    @staticmethod
    def _next_tracker(payload: dict, seen: Set[str]) -> str:
        tracker = payload.get("pageTracker")
        if not isinstance(tracker, str) or not tracker:
            raise ProviderError("Tyche reported more results without a pageTracker")
        if tracker in seen:
            raise ProviderError("Tyche returned a repeated pageTracker")
        seen.add(tracker)
        return tracker

    def _validate_cap(
        self, rows: List[dict], limit: Optional[int], has_more: bool
    ) -> None:
        if len(rows) >= self._MAX_ROWS and limit is None and has_more:
            raise ProviderError(
                f"Tyche returned more than the {self._MAX_ROWS} row safety limit; "
                "narrow the time window or map boundary"
            )
