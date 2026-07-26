import re

# schema.table or bare table; identifiers only — this is interpolated into
# SQL, so it must never accept arbitrary strings.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

_JDBC_PREFIX = re.compile(r"^jdbc:", re.IGNORECASE)
_PG_SCHEMES = ("postgresql://", "postgres://")


def normalize_llm_base_url(url: str) -> str:
    cleaned = _strip_suffixes(
        url, ("/chat/completions", "/completions", "/models")
    )
    return _require_http(cleaned, "llm_base_url", "my-server/openai/v1")


def normalize_mqs_base_url(url: str) -> str:
    cleaned = _strip_suffixes(url, ("/services", "/moriaproject"))
    return _require_http(cleaned, "mqs_base_url", "mqs.example/api")


def normalize_cubes_base_url(url: str) -> str:
    cleaned = _strip_suffixes(url, ("/cube/v1",))
    return _require_http(cleaned, "cubes_base_url", "cubes.example/api")


def normalize_tyche_base_url(url: str) -> str:
    cleaned = _strip_suffixes(url, ("/coordinate/v1/ourforces",))
    return _require_http(cleaned, "tyche_base_url", "tyche.example/api")


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


def _strip_suffixes(url: str, suffixes) -> str:
    cleaned = url.strip().rstrip("/")
    suffix = next(
        (item for item in suffixes if cleaned.lower().endswith(item)), None
    )
    return cleaned[:-len(suffix)] if suffix else cleaned


def _require_http(cleaned: str, field: str, example: str) -> str:
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            f"{field} must start with http:// or https:// "
            f"(e.g. https://{example})"
        )
    return cleaned.rstrip("/")
