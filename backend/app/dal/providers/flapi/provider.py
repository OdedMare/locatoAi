"""FLAPI provider: configure, run, and report one flunks package."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union, get_args

import flunks.flow_models as flunks_models
import geopandas as gpd
from flunks import FlunksRunner
from flunks.config import FlunksConfig
try:
    from flunks.config import FlapiConfig
except ImportError:  # Compatibility with older internal FLUNKS wheels.
    from flunks.config import FlApiConfig as FlapiConfig
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.bl.providers.provider import TEMPORAL_PUSHDOWN
from app.common.errors.provider_error import ProviderError
from app.dal.providers.flapi.mapper import FlunksMapper
from app.dal.providers.flapi.runner_config import (
    build_flapi_config,
    resolve_timeout,
    run_bounded,
)

_ATTEMPTS = 2
_PARTIAL_FIELDS = ("isPartialSuccess", "is_partial_success")
_logger = logging.getLogger(__name__)


def _metadata_field(models: Any) -> Any:
    metadata = getattr(models, "MetaData", None)
    for name, field in getattr(metadata, "model_fields", {}).items():
        if name in _PARTIAL_FIELDS:
            return field
        if getattr(field, "alias", None) in _PARTIAL_FIELDS:
            return field
    return None


def _rebuild_models(models: Any) -> bool:
    metadata = getattr(models, "MetaData", None)
    results = getattr(models, "FlowResults", None)
    if metadata is None or results is None:
        return False
    metadata.model_rebuild(force=True)
    results.model_rebuild(force=True)
    return True


def _patch_metadata(models: Any = None) -> bool:
    models = models or flunks_models
    field = _metadata_field(models)
    if field is None:
        return False
    admitted = get_args(field.annotation) or (field.annotation,)
    if str not in admitted or bool in admitted:
        return False
    field.annotation = Union[bool, field.annotation]
    try:
        return _rebuild_models(models)
    except Exception:
        _logger.exception("FLAPI flunks metadata patch failed")
        return False


def _cube_values(cube: Any) -> str:
    values = getattr(cube, "values", None)
    if values:
        value = str(values[0])
        preview = value if len(value) <= 120 else value[:120] + "…"
        return "values=%d [%s]" % (len(values), preview)
    return "start_time=%s end_time=%s" % (
        getattr(cube, "start_time", None), getattr(cube, "end_time", None),
    )


def _package_summary(package: Any) -> str:
    cube = package.main_input_cube
    return (
        "package_id=%r input_cube=%r parameter=%r %s output_cube=%r"
        % (
            package.package_id, cube.cube_name, cube.cube_parameter,
            _cube_values(cube), package.output_cube.cube_name,
        )
    )


def _fallback_error(exc: BaseException) -> str:
    message = str(exc).replace("\n", " ")
    if len(message) > 160:
        message = message[:160] + "…"
    return "%s: %s" % (type(exc).__name__, message)


def _one_error(error: dict) -> str:
    path = ".".join(str(item) for item in error.get("loc", ())) or "?"
    value = repr(error.get("input"))
    if len(value) > 100:
        value = value[:100] + "…"
    return "%s=%s[got %s]" % (path, error.get("type", "?"), value)


def _error_detail(exc: BaseException) -> str:
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return _fallback_error(exc)
    try:
        details = errors()
    except Exception:
        return _fallback_error(exc)
    rendered = [_one_error(error) for error in details[:3]]
    return "%s: %d error(s) %s" % (
        type(exc).__name__, len(details), "; ".join(rendered),
    )


_logger.info("FLAPI flunks metadata patch applied=%s", _patch_metadata())


class FlapiProvider:
    """Run flunks; all input/output translation lives in ``FlunksMapper``."""

    capabilities = frozenset({TEMPORAL_PUSHDOWN})

    def __init__(self, settings_store) -> None:
        self._store = settings_store
        self._mapper = FlunksMapper()
        self._schemas: Dict[Tuple[str, str], LayerSchema] = {}
        self._logger = logging.getLogger(__name__)
        self.success_chunks = 0
        self.failed_chunks = 0

    def describe_schema(
        self, layer: LayerMeta, geometry: Optional[BaseGeometry] = None,
    ) -> LayerSchema:
        key = self._schema_key(layer)
        if key not in self._schemas:
            self.fetch_features(layer, geometry=geometry)
        return self._schemas[key]

    def fetch_features(
        self, layer: LayerMeta, now=None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        package = self._mapper.package_config(
            layer, geometry=geometry, temporal_range=temporal_range, now=now,
        )
        result = self._run(layer, package)
        output_name = package.output_cube.cube_name
        features, schema, rows = self._mapper.output(
            layer, result, package.package_id, output_name,
        )
        self._schemas[self._schema_key(layer)] = schema
        return self._finish(layer, features, rows, geometry, limit)

    def sample_for_metadata(
        self, layer: LayerMeta, limit: int = 100,
        geometry: Optional[BaseGeometry] = None,
    ):
        features = self.fetch_features(layer, geometry=geometry, limit=limit)
        return features, self._schemas[self._schema_key(layer)]

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20,
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values = [str(value)[:80] for value in features[field].dropna()]
        return list(dict.fromkeys(values))[:limit]

    def _runner(self, package):
        settings = self._settings()
        config = build_flapi_config(FlapiConfig, settings)
        self._logger.info(
            "FLAPI flunks INPUT username=%r token_set=%s %s",
            config.username, bool(config.token), _package_summary(package),
        )
        return FlunksRunner(
            flapi_config=config, package_config=package,
            flunks_config=FlunksConfig(),
        )

    def _run(self, layer: LayerMeta, package):
        timeout = resolve_timeout(self._store.get())
        for attempt in range(_ATTEMPTS):
            try:
                return self._attempt(package, timeout, attempt)
            except Exception as exc:
                self._log_attempt(layer, package, attempt, exc)
                if attempt == _ATTEMPTS - 1:
                    raise self._failure(package, exc) from exc
        raise AssertionError("unreachable: final FLAPI attempt returns or raises")

    def _attempt(self, package, timeout: int, attempt: int):
        runner = self._runner(package)
        started = time.time()
        self._logger.info(
            "FLAPI package RUN id=%s attempt=%d/%d timeout=%ss",
            package.package_id, attempt + 1, _ATTEMPTS, timeout,
        )
        try:
            return run_bounded(runner, timeout, str(package.package_id))
        finally:
            self._remember_chunks(runner, package.package_id)
            self._logger.info(
                "FLAPI package ATTEMPT END id=%s elapsed=%.2fs",
                package.package_id, time.time() - started,
            )

    def _log_attempt(self, layer, package, attempt, exc) -> None:
        self._logger.warning(
            "FLAPI attempt %d/%d failed layer=%s %s -> %s",
            attempt + 1, _ATTEMPTS, layer.id,
            _package_summary(package), _error_detail(exc),
        )

    @staticmethod
    def _failure(package, exc) -> ProviderError:
        return ProviderError(
            "FLAPI %s failed: %s"
            % (_package_summary(package), _error_detail(exc))
        )

    def _settings(self):
        settings = self._store.get()
        if not settings.cubes_token:
            raise ProviderError(
                "FLAPI authorization token is not configured — set cubes_token"
            )
        if not settings.flapi_username:
            raise ProviderError(
                "FLAPI username is not configured — set flapi_username"
            )
        return settings

    def _remember_chunks(self, runner, package_id: str) -> None:
        self.success_chunks = getattr(runner, "success_chunks", 0)
        self.failed_chunks = getattr(runner, "failed_chunks", 0)
        self._logger.info(
            "FLAPI package CHUNKS id=%s success=%s failed=%s",
            package_id, self.success_chunks, self.failed_chunks,
        )

    def _finish(self, layer, features, rows, geometry, limit):
        mapped = len(features)
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
        if limit is not None:
            features = features.iloc[:limit]
        self._logger.info(
            "FLAPI package OK layer=%s rows=%d mapped=%d returned=%d",
            layer.id, rows, mapped, len(features),
        )
        return features.reset_index(drop=True)

    @staticmethod
    def _schema_key(layer: LayerMeta) -> Tuple[str, str]:
        return layer.id, layer.source_url
