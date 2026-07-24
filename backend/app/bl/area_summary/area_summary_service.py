"""Load eligible catalog layers and derive evidence-backed area facts."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from app.bl.area_summary.extractor_support import evidence_id_field
from app.bl.area_summary.fact_extractors import extract_facts
from app.bl.area_summary.layer_config import is_summary_layer, summary_kind
from app.bl.area_summary.models.layer_failure import AreaSummaryLayerFailure
from app.bl.area_summary.models.result import AreaSummaryResult
from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.common.utils.geo_utils import WGS84, require_crs


class AreaSummaryService:
    def __init__(self, catalog, providers) -> None:
        self._catalog = catalog
        self._providers = providers

    def summarize(
        self, boundaries, window_start=None, window_end=None,
        encounter_distance_m=30, encounter_time_tolerance_minutes=10,
        now: Optional[datetime] = None,
    ) -> AreaSummaryResult:
        generated_at = now or datetime.now(timezone.utc)
        end = window_end or generated_at
        start = window_start or end - timedelta(hours=24)
        if start > end:
            raise ValueError("Area summary window_start must not exceed window_end")
        layers = [
            layer for layer in self._catalog.list_queryable_layers()
            if is_summary_layer(layer)
        ]
        return self._summarize_layers(
            layers, boundaries, start, end, generated_at,
            encounter_distance_m, encounter_time_tolerance_minutes,
        )

    def _summarize_layers(
        self, layers, boundaries, start, end, generated_at,
        encounter_distance_m, encounter_time_tolerance_minutes,
    ):
        context = ExecutionContext(
            catalog=self._catalog, providers=self._providers,
            user_geometry=boundaries, now=generated_at,
        )
        facts, failures, successful = [], [], 0
        for layer in layers:
            try:
                facts.extend(self._layer_facts(
                    context, layer, boundaries, start, end,
                    encounter_distance_m, encounter_time_tolerance_minutes,
                ))
                successful += 1
            except Exception as exc:
                failures.append(self._failure(layer, exc))
        return AreaSummaryResult(
            generated_at=generated_at, window_start=start, window_end=end,
            queried_layer_count=len(layers), successful_layer_count=successful,
            facts=facts, failures=failures,
        )

    def _layer_facts(
        self, context, layer, boundaries, start, end,
        encounter_distance_m, encounter_time_tolerance_minutes,
    ):
        kind = summary_kind(layer)
        schema = self._catalog.get_schema(layer.id)
        data = context.load_layer_features(
            layer.id, temporal_range=(start.isoformat(), end.isoformat())
        )
        prepared = self._prepare(data, layer, schema, boundaries, start, end)
        return extract_facts(
            kind, prepared, layer, schema, encounter_distance_m,
            encounter_time_tolerance_minutes,
        )

    def _prepare(self, data, layer, schema, boundaries, start, end):
        require_crs(data, "area_summary")
        prepared = data.to_crs(WGS84) if str(data.crs) != WGS84 else data.copy()
        prepared = prepared[prepared.geometry.intersects(boundaries)].copy()
        prepared["_summary_evidence_id"] = self._evidence_ids(prepared, layer.id)
        if schema.temporal_field:
            prepared = self._time_filter(
                prepared, schema.temporal_field, start, end
            )
        return prepared

    @staticmethod
    def _evidence_ids(data, layer_id):
        field = evidence_id_field(data)
        return [
            str(row[field])
            if field and row.get(field) is not None and not pd.isna(row[field])
            else "{}:{}".format(layer_id, index)
            for index, row in data.iterrows()
        ]

    @staticmethod
    def _time_filter(data, field, start, end):
        if field not in data.columns:
            raise ValueError("Area summary temporal field is missing")
        filtered = data.copy()
        filtered["_summary_time"] = pd.to_datetime(
            filtered[field], utc=True, errors="coerce"
        )
        return filtered[
            (filtered["_summary_time"] >= start)
            & (filtered["_summary_time"] <= end)
        ]

    @staticmethod
    def _failure(layer, error):
        return AreaSummaryLayerFailure(
            layer_id=layer.id, layer_name=layer.name,
            error_type=type(error).__name__,
            message=(str(error) or type(error).__name__)[:240],
        )
