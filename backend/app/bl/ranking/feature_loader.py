"""Bounded layer loading plus evidence/time preparation shared by rules."""

import pandas as pd

from app.bl.ranking.rule_support import evidence_id_field
from app.common.utils.geo_utils import WGS84, require_crs


class RankingFeatureLoader:
    def __init__(self, catalog, context) -> None:
        self._catalog = catalog
        self._context = context

    def load(self, layer, boundaries, start, end, geometry=None):
        schema = self._catalog.get_schema(layer.id)
        data = self._context.load_layer_features(
            layer.id, geometry_hint=geometry,
            temporal_range=(start.isoformat(), end.isoformat()),
        )
        clip = geometry if geometry is not None else boundaries
        return self._prepare(data, layer, schema, clip, start, end), schema

    def _prepare(self, data, layer, schema, clip, start, end):
        require_crs(data, "ranking")
        prepared = data.to_crs(WGS84) if str(data.crs) != WGS84 else data.copy()
        prepared = prepared[prepared.geometry.intersects(clip)].copy()
        prepared["_ranking_evidence_id"] = self._evidence_ids(prepared, layer.id)
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
        if data.empty:
            filtered = data.copy()
            filtered["_ranking_time"] = pd.Series(
                index=filtered.index, dtype="datetime64[ns, UTC]"
            )
            return filtered
        if field not in data.columns:
            raise ValueError("Ranking temporal field is missing")
        filtered = data.copy()
        filtered["_ranking_time"] = pd.to_datetime(
            filtered[field], utc=True, errors="coerce"
        )
        return filtered[
            (filtered["_ranking_time"] >= start)
            & (filtered["_ranking_time"] <= end)
        ]
