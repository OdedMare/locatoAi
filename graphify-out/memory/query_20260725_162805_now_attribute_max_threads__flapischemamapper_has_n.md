---
type: "query"
date: "2026-07-25T16:28:05.190250+00:00"
question: "now attribute max_threads; FlapiSchemaMapper has no attribute max_threads"
contributor: "graphify"
outcome: "useful"
source_nodes: ["FlowPackageProvider", "FlapiProvider"]
---

# Q: now attribute max_threads; FlapiSchemaMapper has no attribute max_threads

## Answer

Expanded from graph vocabulary: [attribute, config, configuration, flapi, flow, gateway, max, package]. FlowPackageProvider constructed FlowPackageGateway, and an obsolete positional/config seam allowed FlapiSchemaMapper to be treated as flunks_config. FlunksRunner then read max_threads from the mapper. FlowPackageGateway now accepts only clients and source and passes only flapi_config plus package_config to FlunksRunner, leaving internal flunks defaults to the library. Tests assert that flunks_config and exceptions_config are not injected. 302 Python 3.8 backend tests passed.

## Outcome

- Signal: useful

## Source Nodes

- FlowPackageProvider
- FlapiProvider