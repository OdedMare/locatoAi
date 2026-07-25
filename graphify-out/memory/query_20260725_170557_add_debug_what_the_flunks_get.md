---
type: "query"
date: "2026-07-25T17:05:57.175121+00:00"
question: "add debug what the flunks get"
contributor: "graphify"
outcome: "useful"
source_nodes: ["FlowPackageGateway", "FlowPackageProvider", "FlapiProvider"]
---

# Q: add debug what the flunks get

## Answer

Expanded from graph vocabulary: [config, configuration, debug, flapi, flow, gateway, input, package, request]. Added one consolidated INFO log immediately before FlunksRunner construction: 'FLAPI flunks INPUT'. It renders the final FlapiConfig and FlunksPackageConfig values actually passed to flunks: base URL, username, token presence, package ID, input cube name, cube parameter, time range or bounded WKT values, and output cube name. The raw token is never logged. The focused Python 3.8 FLAPI suite passed 19 tests, including an assertion that the JWT value is absent.

## Outcome

- Signal: useful

## Source Nodes

- FlowPackageGateway
- FlowPackageProvider
- FlapiProvider