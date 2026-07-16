from pydantic import BaseModel


class LayerParameterOption(BaseModel):
    """One selectable value for a dynamic (autocomplete-backed) parameter."""

    value: str
    name: str = ""
