from typing import Dict

from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registration import OpRegistration

_REGISTRY: Dict[str, OpHandler] = {}


class OpRegistry:
    @staticmethod
    def register(op_name: str) -> OpRegistration:
        return OpRegistration(_REGISTRY, op_name)

    @staticmethod
    def get(op_name: str) -> OpHandler:
        handler = _REGISTRY.get(op_name)
        if handler is None:
            raise KeyError(f"No handler registered for op '{op_name}'")
        return handler


register_op = OpRegistry.register
get_op_handler = OpRegistry.get
