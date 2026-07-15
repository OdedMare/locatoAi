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
        if step.field not in gdf.columns:
            raise ExecutionError(
                f"attribute_filter: field '{step.field}' not in layer "
                f"(available: {sorted(c for c in gdf.columns if c != 'geometry')})"
            )

        column = gdf[step.field]
        if step.operator == "eq":
            mask = column == step.value
        elif step.operator == "neq":
            mask = column != step.value
        elif step.operator == "gt":
            mask = pd.to_numeric(column, errors="coerce") > float(step.value)
        elif step.operator == "lt":
            mask = pd.to_numeric(column, errors="coerce") < float(step.value)
        elif step.operator == "fuzzy_contains":
            target = normalize_text(str(step.value))
            mask = column.astype(str).map(
                lambda cell: fuzz.partial_ratio(normalize_text(cell), target)
                >= _FUZZY_CONTAINS_THRESHOLD
            )
        else:  # "contains" — operators are closed by the Literal type
            target = normalize_text(str(step.value))
            mask = column.astype(str).map(
                lambda cell: target in normalize_text(cell)
            )
        return gdf[mask]
