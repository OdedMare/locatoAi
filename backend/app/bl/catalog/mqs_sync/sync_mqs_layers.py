from uuid import uuid4

from app.bl.catalog.mqs_sync.browse_mqs_layers import browse_mqs_layers
from app.bl.catalog.mqs_sync.mqs_sync_result import MqsSyncResult
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.layers_repository import LayersRepository


class MqsLayerSynchronizer:
    def sync(
        self, repository: LayersRepository, mqs_provider
    ) -> MqsSyncResult:
        result = MqsSyncResult()
        remote_layers, result.skipped = browse_mqs_layers(mqs_provider)
        for remote in remote_layers:
            created = self._upsert(repository, remote)
            if created:
                result.added += 1
            else:
                result.updated += 1
        return result

    @staticmethod
    def _upsert(repository: LayersRepository, remote) -> bool:
        layer = LayerMeta(
            id=str(uuid4()),  # replaced by the repository on insert
            name=remote.name,
            description=remote.description,
            tags=remote.tags,  # only applied on insert; updates preserve tags
            provider=remote.provider,
            source_url=remote.source_url,
        )
        _, created = repository.upsert_layer(layer)
        return created


sync_mqs_layers = MqsLayerSynchronizer().sync
