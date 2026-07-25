"""Tyche HTTP provider."""

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.bl.providers.provider import TEMPORAL_PUSHDOWN
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.common.utils.geo_utils import empty_features_gdf
from app.dal.providers.tyche.mapper import TycheMapper


class TycheProvider:
    capabilities = frozenset({TEMPORAL_PUSHDOWN})
    _MAX_SAMPLE_CHARS = 80
    _PAGE_SIZE = 10000
    _MAX_ROWS = 100000

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._store = settings_store
        self._transport = transport
        self._mapper = TycheMapper()
        self._samples: Dict[str, List[dict]] = {}

    def describe_schema(self, layer: LayerMeta, geometry=None) -> LayerSchema:
        source = self._mapper.source(layer.source_url)
        rows = self._samples.get(layer.id)
        if rows is None and not source["is_our_forces"]:
            rows = self._fetch_rows(source, None, None, 100, None)
            self._samples[layer.id] = rows
        return self._mapper.schema(layer, rows or [], source)

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        source = self._mapper.source(layer.source_url)
        if limit is not None and limit < 1:
            return empty_features_gdf()
        rows = self._fetch_rows(source, now, geometry, limit, temporal_range)
        self._samples[layer.id] = rows[:100]
        return self._features_in_boundary(rows, geometry, source)

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20,
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values = [str(value)[:self._MAX_SAMPLE_CHARS]
                  for value in features[field].dropna()]
        return list(dict.fromkeys(values))[:limit]

    def _fetch_rows(
        self, source: dict, now: Optional[datetime],
        geometry: Optional[BaseGeometry], limit: Optional[int],
        temporal_range: Optional[Tuple[str, str]],
    ) -> List[dict]:
        rows: List[dict] = []
        tracker = None
        seen: Set[str] = set()
        has_more = False
        with self._client() as client:
            while self._page_size(rows, limit) > 0:
                body = self._mapper.request(
                    source, now, geometry, temporal_range,
                    self._page_size(rows, limit), tracker,
                )
                payload = self._post(client, source["route"], body)
                rows = self._mapper.deduplicate(rows + self._page_rows(payload))
                has_more = bool(payload.get("hasMoreResults"))
                if not has_more or self._limit_reached(rows, limit):
                    break
                tracker = self._next_tracker(payload, seen)
        self._validate_cap(rows, limit, has_more)
        return rows[:limit] if limit is not None else rows

    def _features_in_boundary(
        self, rows: List[dict], geometry: Optional[BaseGeometry], source: dict,
    ) -> gpd.GeoDataFrame:
        features = self._mapper.to_gdf(rows, source["geometry_field"])
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
        return features.reset_index(drop=True)

    def _client(self) -> httpx.Client:
        settings = self._store.get()
        self._validate_settings(settings)
        return httpx.Client(
            base_url=settings.tyche_base_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "username": settings.tyche_username,
                "Authorization": settings.tyche_token,
            },
            timeout=None, verify=settings.tyche_verify_tls,
            transport=self._transport,
        )

    @staticmethod
    def _validate_settings(settings) -> None:
        if not settings.tyche_base_url:
            raise ProviderError(
                "Tyche base URL is not configured — set tyche_base_url")
        if not settings.tyche_username:
            raise ProviderError(
                "Tyche username is not configured — set tyche_username")
        if not settings.tyche_token:
            raise ProviderError(
                "Tyche authorization token is not configured — set tyche_token")

    @staticmethod
    def _post(client: httpx.Client, path: str, body: dict) -> dict:
        try:
            response = client.post(path, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Tyche request failed (%s): %s" % (path, exc)) from exc
        except ValueError as exc:
            raise ProviderError(
                "Tyche returned invalid JSON (%s): %s" % (path, exc)) from exc
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
        remaining = (
            limit - len(rows) if limit is not None
            else self._MAX_ROWS - len(rows)
        )
        return min(self._PAGE_SIZE, remaining)

    @staticmethod
    def _limit_reached(rows: List[dict], limit: Optional[int]) -> bool:
        return limit is not None and len(rows) >= limit

    @staticmethod
    def _next_tracker(payload: dict, seen: Set[str]) -> str:
        tracker = payload.get("pageTracker")
        if not isinstance(tracker, str) or not tracker:
            raise ProviderError(
                "Tyche reported more results without a pageTracker")
        if tracker in seen:
            raise ProviderError("Tyche returned a repeated pageTracker")
        seen.add(tracker)
        return tracker

    def _validate_cap(
        self, rows: List[dict], limit: Optional[int], has_more: bool,
    ) -> None:
        if len(rows) >= self._MAX_ROWS and limit is None and has_more:
            raise ProviderError(
                "Tyche returned more than the %s row safety limit; "
                "narrow the time window or map boundary" % self._MAX_ROWS
            )
