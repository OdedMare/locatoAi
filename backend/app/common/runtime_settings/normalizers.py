import re

# schema.table or bare table; identifiers only — this is interpolated into
# SQL, so it must never accept arbitrary strings.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

_JDBC_PREFIX = re.compile(r"^jdbc:", re.IGNORECASE)
_PG_SCHEMES = ("postgresql://", "postgres://")


class RuntimeSettingsNormalizer:
    @classmethod
    def llm_base_url(cls, url: str) -> str:
        cleaned = cls._strip_suffixes(
            url, ("/chat/completions", "/completions", "/models")
        )
        return cls._require_http(cleaned, "llm_base_url", "my-server/openai/v1")

    @classmethod
    def mqs_base_url(cls, url: str) -> str:
        cleaned = cls._strip_suffixes(url, ("/services", "/moriaproject"))
        return cls._require_http(cleaned, "mqs_base_url", "mqs.example/api")

    @classmethod
    def cubes_base_url(cls, url: str) -> str:
        cleaned = cls._strip_suffixes(url, ("/cube/v1",))
        return cls._require_http(cleaned, "cubes_base_url", "cubes.example/api")

    @classmethod
    def tyche_base_url(cls, url: str) -> str:
        cleaned = cls._strip_suffixes(url, ("/coordinate/v1/ourforces",))
        return cls._require_http(cleaned, "tyche_base_url", "tyche.example/api")

    @staticmethod
    def database_url(url: str) -> str:
        cleaned = _JDBC_PREFIX.sub("", url.strip())
        if not cleaned.lower().startswith(_PG_SCHEMES):
            raise ValueError(
                "database_url must start with postgresql:// "
                "(jdbc:postgresql://... is accepted and converted automatically)"
            )
        return cleaned

    @staticmethod
    def layers_table(name: str) -> None:
        if not _TABLE_RE.match(name):
            raise ValueError(
                "layers_table must be a plain identifier like 'layers' or 'public.layers'"
            )

    @staticmethod
    def _strip_suffixes(url: str, suffixes) -> str:
        cleaned = url.strip().rstrip("/")
        suffix = next(
            (item for item in suffixes if cleaned.lower().endswith(item)), None
        )
        return cleaned[:-len(suffix)] if suffix else cleaned

    @staticmethod
    def _require_http(cleaned: str, field: str, example: str) -> str:
        if not cleaned.lower().startswith(("http://", "https://")):
            raise ValueError(
                f"{field} must start with http:// or https:// "
                f"(e.g. https://{example})"
            )
        return cleaned.rstrip("/")


normalize_llm_base_url = RuntimeSettingsNormalizer.llm_base_url
normalize_mqs_base_url = RuntimeSettingsNormalizer.mqs_base_url
normalize_cubes_base_url = RuntimeSettingsNormalizer.cubes_base_url
normalize_tyche_base_url = RuntimeSettingsNormalizer.tyche_base_url
normalize_database_url = RuntimeSettingsNormalizer.database_url
validate_layers_table = RuntimeSettingsNormalizer.layers_table
