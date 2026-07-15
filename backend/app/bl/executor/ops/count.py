from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.count_step import CountStep


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
