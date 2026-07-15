import re

# schema.table or bare table; identifiers only — this is interpolated into
# SQL, so it must never accept arbitrary strings.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

_JDBC_PREFIX = re.compile(r"^jdbc:", re.IGNORECASE)
_PG_SCHEMES = ("postgresql://", "postgres://")


def normalize_llm_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/models"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            "llm_base_url must start with http:// or https:// "
            "(e.g. https://my-server/openai/v1)"
        )
    return cleaned


def normalize_mqs_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    for suffix in ("/services", "/moriaproject"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            "mqs_base_url must start with http:// or https:// "
            "(e.g. https://mqs.example/api)"
        )
    return cleaned


def normalize_cubes_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    suffix = "/cube/v1"
    if cleaned.lower().endswith(suffix):
        cleaned = cleaned[: -len(suffix)]
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            "cubes_base_url must start with http:// or https:// "
            "(e.g. https://cubes.example/api)"
        )
    return cleaned.rstrip("/")


def normalize_database_url(url: str) -> str:
    cleaned = _JDBC_PREFIX.sub("", url.strip())
    if not cleaned.lower().startswith(_PG_SCHEMES):
        raise ValueError(
            "database_url must start with postgresql:// "
            "(jdbc:postgresql://... is accepted and converted automatically)"
        )
    return cleaned


def validate_layers_table(name: str) -> None:
    if not _TABLE_RE.match(name):
        raise ValueError(
            "layers_table must be a plain identifier like 'layers' or 'public.layers'"
        )
