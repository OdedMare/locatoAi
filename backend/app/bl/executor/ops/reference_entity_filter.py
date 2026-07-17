"""Shared optional filtering for proximity reference layers."""

from app.common.errors.execution_error import ExecutionError


class ReferenceEntityFilter:
    @staticmethod
    def apply(target, field, operator, value):
        target_filter = (field, operator, value)
        if not any(item is not None for item in target_filter):
            return target
        if not all(item is not None for item in target_filter):
            raise ExecutionError(
                "proximity: target_field, target_operator and target_value "
                "must be supplied together"
            )
        if field not in target.columns:
            raise ExecutionError(f"proximity: target field '{field}' not in layer")
        column = target[field]
        if operator == "eq":
            return target[column == value]
        return target[column.astype(str).str.contains(
            str(value), case=False, na=False, regex=False
        )]
