"""Callable live accessor for the LLM diet-mode setting."""


class RuntimeDietMode:
    def __init__(self, settings_store) -> None:
        self._store = settings_store

    def __call__(self) -> bool:
        return self._store.get().llm_diet_mode
