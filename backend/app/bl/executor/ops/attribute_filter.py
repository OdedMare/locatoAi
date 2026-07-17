import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.attribute_filter_step import AttributeFilterStep
from app.common.errors.execution_error import ExecutionError
from app.common.text_normalize import normalize_text

# Below this rapidfuzz partial_ratio score, two normalized strings are
# treated as unrelated — chosen to tolerate a handful of typos/spelling
# variants in a short place name without matching genuinely different text
# (an acronym like "ת״א" for "תל אביב" still scores well under this; that
# is a different problem — alias/synonym expansion — not fuzzy distance).
_FUZZY_CONTAINS_THRESHOLD = 80


@register_op("attribute_filter")
class AttributeFilterOp(OpHandler):
    def run(self, step: AttributeFilterStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if gdf.empty:
            return gdf
        self._validate_field(gdf, step.field)
        return gdf[self._mask(gdf[step.field], step)]

    @staticmethod
    def _validate_field(gdf, field: str) -> None:
        if field not in gdf.columns:
            raise ExecutionError(
                f"attribute_filter: field '{field}' not in layer "
                f"(available: {sorted(c for c in gdf.columns if c != 'geometry')})"
            )

    def _mask(self, column, step):
        if step.operator == "eq":
            return column == step.value
        if step.operator == "neq":
            return column != step.value
        if step.operator in ("gt", "lt"):
            numeric = pd.to_numeric(column, errors="coerce")
            value = float(step.value)
            return numeric > value if step.operator == "gt" else numeric < value
        target = normalize_text(str(step.value))
        values = [self._text_match(cell, target, step.operator)
                  for cell in column.astype(str)]
        return pd.Series(values, index=column.index)

    @staticmethod
    def _text_match(cell: str, target: str, operator: str) -> bool:
        normalized = normalize_text(cell)
        if operator == "fuzzy_contains":
            return fuzz.partial_ratio(normalized, target) >= _FUZZY_CONTAINS_THRESHOLD
        return target in normalized
