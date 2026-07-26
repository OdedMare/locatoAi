"""Callable registration decorator for one executor operation."""

from typing import Dict, Type

from app.bl.executor.ops.base.op_handler import OpHandler


class OpRegistration:
    def __init__(self, registry: Dict[str, OpHandler], op_name: str) -> None:
        self._registry = registry
        self._op_name = op_name

    def __call__(self, handler_type: Type[OpHandler]) -> Type[OpHandler]:
        self._registry[self._op_name] = handler_type()
        return handler_type
