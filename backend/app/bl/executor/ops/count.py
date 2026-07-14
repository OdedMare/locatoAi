from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import CountStep


@register_op("count")
class CountOp(OpHandler):
    """Terminal aggregation: row count of the upstream step's result.

    No grouping/aggregation by attribute — a plain integer. Always the
    plan's `output` (enforced by validate_plan) and never stored for
    another step to consume as `input` — engine.py short-circuits on a
    CountStep instead of writing into ctx.results.
    """

    def run(self, step: CountStep, ctx: ExecutionContext) -> int:
        return len(ctx.results[step.input])
