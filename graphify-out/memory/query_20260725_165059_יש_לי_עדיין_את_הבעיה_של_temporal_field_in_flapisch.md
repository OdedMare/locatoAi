---
type: "query"
date: "2026-07-25T16:50:59.447216+00:00"
question: "יש לי עדיין את הבעיה של temporal_field in FlapiSchemaMapper"
contributor: "graphify"
outcome: "useful"
source_nodes: ["FlowPackageProvider", "FlapiProvider"]
---

# Q: יש לי עדיין את הבעיה של temporal_field in FlapiSchemaMapper

## Answer

Expanded from graph vocabulary: [field, flapi, flow, mapper, package, provider, schema, temporal]. The repository method existed but the available Docker image was stale. To eliminate the attribute failure structurally, FlapiSchemaMapper.infer_schema now computes the preferred known temporal field and date-field fallback inline; _temporal_field no longer exists or gets called. The focused Python 3.8 FLAPI suite passed 18 tests. The local ailocator-backend image is dated 2026-07-15, so it must be rebuilt with private flunks access or run with the current app directory mounted.

## Outcome

- Signal: useful

## Source Nodes

- FlowPackageProvider
- FlapiProvider