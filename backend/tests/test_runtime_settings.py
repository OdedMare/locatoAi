import pytest

from app.common.config import Settings
from app.common.runtime_settings.normalizers import validate_layers_table
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore


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
    assert store.get().llm_diet_mode is True
    assert store.get().layers_table == "public.layers"


def test_update_persists_and_reloads(tmp_path):
    store = make_store(tmp_path)
    store.update({
        "llm_model": "gpt-4o-mini",
        "llm_diet_mode": False,
        "layers_table": "gis.my_layers",
        "feedback_table": "gis.user_feedback",
        "database_user": "gis_user",
        "database_password": "secret",
        "database_host": "db.internal",
        "database_port": 5433,
        "database_name": "geo_catalog",
    })

    reloaded = make_store(tmp_path)  # same file, fresh store
    assert reloaded.get().llm_model == "gpt-4o-mini"
    assert reloaded.get().llm_diet_mode is False
    assert reloaded.get().layers_table == "gis.my_layers"
    assert reloaded.get().feedback_table == "gis.user_feedback"
    assert reloaded.get().database_user == "gis_user"
    assert reloaded.get().database_password == "secret"
    assert reloaded.get().database_host == "db.internal"
    assert reloaded.get().database_port == 5433
    assert reloaded.get().database_name == "geo_catalog"


def test_unknown_keys_ignored(tmp_path):
    store = make_store(tmp_path)
    store.update({"nope": "x"})
    assert not hasattr(store.get(), "nope")


def test_jdbc_database_url_is_normalized(tmp_path):
    store = make_store(tmp_path)
    store.update({"database_url": "jdbc:postgresql://rnd619-nv-prd1:5324/spear"})
    assert store.get().database_url == "postgresql://rnd619-nv-prd1:5324/spear"


def test_non_postgres_database_url_rejected(tmp_path):
    store = make_store(tmp_path)
    for bad in ["mysql://host/db", "host=x dbname=y", "rnd619-nv-prd1:5324/spear"]:
        with pytest.raises(ValueError, match="postgresql://"):
            store.update({"database_url": bad})


def test_llm_base_url_with_path_is_preserved(tmp_path):
    store = make_store(tmp_path)
    store.update({"llm_base_url": "https://my-gateway/openai/v1"})
    assert store.get().llm_base_url == "https://my-gateway/openai/v1"


def test_llm_base_url_normalization(tmp_path):
    store = make_store(tmp_path)
    # trailing slash + pasted endpoint suffix are cleaned off
    store.update({"llm_base_url": "https://h/openai/v1/chat/completions"})
    assert store.get().llm_base_url == "https://h/openai/v1"
    store.update({"llm_base_url": "http://h:11434/v1/"})
    assert store.get().llm_base_url == "http://h:11434/v1"


def test_llm_base_url_requires_scheme(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="http"):
        store.update({"llm_base_url": "my-gateway/openai/v1"})


def test_llm_base_url_can_be_cleared(tmp_path):
    store = make_store(tmp_path)
    store.update({"llm_base_url": "https://h/v1"})
    store.update({"llm_base_url": None})
    assert store.get().llm_base_url is None
    store.update({"llm_base_url": "https://h/v1"})
    store.update({"llm_base_url": ""})
    assert store.get().llm_base_url is None


def test_mqs_base_url_defaults_to_none(tmp_path):
    store = make_store(tmp_path)
    assert store.get().mqs_base_url is None


def test_mqs_base_url_normalization(tmp_path):
    store = make_store(tmp_path)
    # trailing slash + pasted discovery suffixes are cleaned off
    store.update({"mqs_base_url": "https://mqs.example/api/"})
    assert store.get().mqs_base_url == "https://mqs.example/api"
    store.update({"mqs_base_url": "https://mqs.example/api/Services"})
    assert store.get().mqs_base_url == "https://mqs.example/api"
    store.update({"mqs_base_url": "https://mqs.example/api/MoriaProject/"})
    assert store.get().mqs_base_url == "https://mqs.example/api"


def test_mqs_base_url_requires_scheme(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="http"):
        store.update({"mqs_base_url": "mqs.example/api"})


def test_mqs_base_url_can_be_cleared(tmp_path):
    store = make_store(tmp_path)
    store.update({"mqs_base_url": "https://mqs.example/api"})
    store.update({"mqs_base_url": None})
    assert store.get().mqs_base_url is None
    store.update({"mqs_base_url": "https://mqs.example/api"})
    store.update({"mqs_base_url": ""})
    assert store.get().mqs_base_url is None


def test_mqs_base_url_persists(tmp_path):
    store = make_store(tmp_path)
    store.update({"mqs_base_url": "https://mqs.example/api"})
    reloaded = make_store(tmp_path)
    assert reloaded.get().mqs_base_url == "https://mqs.example/api"


def test_cubes_settings_normalize_persist_and_clear(tmp_path):
    store = make_store(tmp_path)
    store.update({
        "cubes_base_url": "https://cubes.example/api/cube/v1/",
        "cubes_token": "secret-jwt",
    })
    reloaded = make_store(tmp_path)
    assert reloaded.get().cubes_base_url == "https://cubes.example/api"
    assert reloaded.get().cubes_token == "secret-jwt"
    reloaded.update({"cubes_base_url": None})
    assert reloaded.get().cubes_base_url is None


def test_bad_saved_database_url_skipped_on_startup(tmp_path):
    store = make_store(tmp_path)
    # simulate a bad value persisted by an older version
    store._path.write_text('{"database_url": "not-a-url"}', encoding="utf-8")
    reloaded = make_store(tmp_path)
    assert reloaded.get().database_url.startswith("postgresql://")  # env default kept


def test_table_identifier_validation(tmp_path):
    store = make_store(tmp_path)
    for bad in ["a;drop table x", "a.b.c", "1abc", 'x"y', "a b"]:
        with pytest.raises(ValueError):
            store.update({"layers_table": bad})
        with pytest.raises(ValueError):
            store.update({"feedback_table": bad})
    validate_layers_table("layers")
    validate_layers_table("public.layers")


def test_quoted_table(tmp_path):
    store = make_store(tmp_path)
    assert store.get().quoted_layers_table() == '"public"."layers"'
    assert store.get().quoted_feedback_table() == '"public"."feedback"'
