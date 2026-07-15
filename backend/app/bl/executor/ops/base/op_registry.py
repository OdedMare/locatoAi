from typing import Callable, Dict, Type

from app.bl.executor.ops.base.op_handler import OpHandler

_REGISTRY: Dict[str, OpHandler] = {}


def register_op(op_name: str) -> Callable[[Type[OpHandler]], Type[OpHandler]]:
    def decorator(cls: Type[OpHandler]) -> Type[OpHandler]:
        _REGISTRY[op_name] = cls()
        return cls

    return decorator


def get_op_handler(op_name: str) -> OpHandler:
    handler = _REGISTRY.get(op_name)
    if handler is None:
        raise KeyError(f"No handler registered for op '{op_name}'")
    return handler
