"""Normalize Flow Package parameter metadata."""

from typing import Any, Dict, List, Optional

from app.bl.catalog.models.layer_parameter import LayerParameter


class FlowPackageMetadata:
    _PARAMETER_KEYS = ("Parameters", "parameters", "PackageParameters")

    def definitions(self, payload: object) -> List[dict]:
        found = self._find_definitions(payload)
        unique: Dict[str, dict] = {}
        for item in found:
            name = self.value(item, "Name", "name")
            if name not in (None, ""):
                unique.setdefault(str(name), item)
        return list(unique.values())

    def parameters(
        self, definitions: List[dict], resolved: Dict[str, Any]
    ) -> List[LayerParameter]:
        return [self._parameter(item, resolved) for item in definitions]

    def is_geometry(self, item: dict) -> bool:
        values = (
            self.value(item, "Name", "name"),
            self.value(item, "Type", "type"),
            self.value(item, "OntologyType", "ontologyType"),
            self.value(item, "Category", "category"),
        )
        text = " ".join(str(value or "").casefold() for value in values)
        return any(word in text for word in ("geometry", "polygon", "wkt"))

    def is_time(self, item: dict) -> bool:
        ontology = str(self.value(
            item, "OntologyType", "ontologyType", "ontology_type"
        ) or "").casefold()
        kind = str(self.value(item, "Type", "type") or "").casefold()
        return ontology == "time" or kind in ("time", "datetime", "date")

    def _find_definitions(self, payload: object) -> List[dict]:
        if isinstance(payload, list):
            direct = [item for item in payload if self._is_definition(item)]
            if direct:
                return direct
            return self._from_children(payload)
        if isinstance(payload, dict):
            for key in self._PARAMETER_KEYS:
                if key in payload:
                    found = self._find_definitions(payload[key])
                    if found:
                        return found
            return self._from_children(list(payload.values()))
        return []

    def _from_children(self, values: List[object]) -> List[dict]:
        found: List[dict] = []
        for value in values:
            found.extend(self._find_definitions(value))
        return found

    @staticmethod
    def _is_definition(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        return "Name" in item or "name" in item

    def _parameter(
        self, item: dict, resolved: Dict[str, Any]
    ) -> LayerParameter:
        name = str(self.value(item, "Name", "name"))
        return LayerParameter(
            name=name,
            type=str(self.value(item, "Type", "type") or "unknown").lower(),
            display_name=str(self.value(
                item, "DisplayName", "displayName", "display_name"
            ) or ""),
            description=str(self.value(item, "Description", "description") or ""),
            required=self.bool_value(item, False, "IsRequired", "isRequired"),
            single_value=self.bool_value(
                item, True, "IsSingleValue", "isSingleValue"
            ),
            ontology_type=str(self.value(
                item, "OntologyType", "ontologyType", "ontology_type"
            ) or ""),
            options=self._options(item),
            resolved_value=resolved.get(name),
            configured_value=self.value(item, "Value", "value"),
        )

    def _options(self, item: dict) -> List[str]:
        raw = self.value(item, "Options", "options") or []
        if not isinstance(raw, list):
            return []
        values = []
        for option in raw:
            value = (
                self.value(option, "Value", "value")
                if isinstance(option, dict) else option
            )
            if value not in (None, ""):
                values.append(str(value))
        return values

    @staticmethod
    def value(item: dict, *keys: str) -> Optional[Any]:
        return next((item[key] for key in keys if key in item), None)

    @classmethod
    def bool_value(cls, item: dict, default: bool, *keys: str) -> bool:
        value = cls.value(item, *keys)
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().casefold() in ("true", "1", "yes")
        return bool(value)
