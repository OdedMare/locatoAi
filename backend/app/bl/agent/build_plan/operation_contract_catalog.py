"""Render compact operation contracts from the authoritative Pydantic models."""

import json
from typing import get_args, get_origin, Literal, Union

from pydantic import BaseModel

from app.bl.plan.models.step import STEP_MODELS


class OperationContractCatalog:
    def render(self) -> str:
        return "\n".join(self._model_contract(model) for model in STEP_MODELS)

    def _model_contract(self, model) -> str:
        fields = model.model_fields
        operation = get_args(fields["op"].annotation)[0]
        required, optional = {}, {}
        for name, field in fields.items():
            target = required if field.is_required() else optional
            target[field.alias or name] = self._field_contract(field)
        sections = ["required=" + self._mapping(required)]
        if optional:
            sections.append("optional=" + self._mapping(optional))
        return f"- {operation}: " + "; ".join(sections)

    def _field_contract(self, field):
        contract = self._annotation(field.annotation)
        limits = self._limits(field)
        if limits:
            contract += " " + " ".join(limits)
        if not field.is_required():
            contract += " default=" + self._json(field.default)
        return contract

    def _annotation(self, annotation) -> str:
        origin, arguments = get_origin(annotation), get_args(annotation)
        if origin is Literal:
            return "|".join(self._json(value) for value in arguments)
        if origin is Union:
            return "|".join(self._annotation(item) for item in arguments)
        if origin in (list, tuple):
            return "[" + self._annotation(arguments[0]) + "]"
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return self._nested_model(annotation)
        return {
            str: "string", int: "integer", float: "number",
            bool: "boolean", type(None): "null",
        }.get(annotation, getattr(annotation, "__name__", str(annotation)))

    def _nested_model(self, model) -> str:
        values = (
            (field.alias or name) + ":" + self._annotation(field.annotation)
            + ("" if field.is_required() else "?")
            for name, field in model.model_fields.items()
        )
        return "{" + ",".join(values) + "}"

    @staticmethod
    def _limits(field) -> list:
        names = (("gt", ">"), ("ge", ">="), ("lt", "<"), ("le", "<="),
                 ("min_length", "min_items="), ("max_length", "max_items="))
        return [
            label + str(getattr(item, name))
            for item in field.metadata for name, label in names
            if getattr(item, name, None) is not None
        ]

    @staticmethod
    def _mapping(values: dict) -> str:
        return "{" + ",".join(
            f"{name}:{contract}" for name, contract in values.items()
        ) + "}"

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
