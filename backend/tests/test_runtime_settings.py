import pytest

from app.common.config import Settings
from app.common.runtime_settings import RuntimeSettingsStore, validate_layers_table


def make_store(tmp_path, **env_overrides) -> RuntimeSettingsStore:
    env = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        **env_overrides,
    )
    return RuntimeSettingsStore(env)


def test_env_defaults_apply(tmp_path):
    store = make_store(tmp_path, llm_model="gpt-x")
    assert store.get().llm_model == "gpt-x"
    assert store.get().layers_table == "public.layers"


def test_update_persists_and_reloads(tmp_path):
    store = make_store(tmp_path)
    store.update({
        "llm_model": "gpt-4o-mini",
        "layers_table": "gis.my_layers",
        "database_user": "gis_user",
        "database_password": "secret",
    })

    reloaded = make_store(tmp_path)  # same file, fresh store
    assert reloaded.get().llm_model == "gpt-4o-mini"
    assert reloaded.get().layers_table == "gis.my_layers"
    assert reloaded.get().database_user == "gis_user"
    assert reloaded.get().database_password == "secret"


def test_unknown_keys_ignored(tmp_path):
    store = make_store(tmp_path)
    store.update({"nope": "x"})
    assert not hasattr(store.get(), "nope")


def test_table_identifier_validation(tmp_path):
    store = make_store(tmp_path)
    for bad in ["a;drop table x", "a.b.c", "1abc", 'x"y', "a b"]:
        with pytest.raises(ValueError):
            store.update({"layers_table": bad})
    validate_layers_table("layers")
    validate_layers_table("public.layers")


def test_quoted_table(tmp_path):
    store = make_store(tmp_path)
    assert store.get().quoted_layers_table() == '"public"."layers"'
