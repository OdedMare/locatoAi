import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import AttributeFilterStep
from app.common.errors import ExecutionError


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
            mask = column > step.value
        elif step.operator == "lt":
            mask = column < step.value
        else:  # "contains" — operators are closed by the Literal type
            mask = column.astype(str).str.contains(str(step.value), na=False)
        return gdf[mask]
