---
type: "query"
date: "2026-07-25T08:40:29.652523+00:00"
question: "i have still problam in pakceges 1. flow packeage geometry must be wkt text 2. flow time must be json"
contributor: "graphify"
outcome: "useful"
source_nodes: ["FlowPackageProvider", "FlowPackageSerializer"]
---

# Q: i have still problam in pakceges 1. flow packeage geometry must be wkt text 2. flow time must be json

## Answer

Expanded from original query via graph vocab: [flapi, flow, package, geometry, wkt, time, json, parameter, request, builder]. Fixed Flow Package payload serialization so geometry is emitted as raw WKT text, while time textarea values are parsed and sent as JSON objects. Geometry remains backward-compatible with previously stored lowercase value wrappers. Verified with 32 backend tests, TypeScript, ESLint, and the production frontend build.

## Outcome

- Signal: useful

## Source Nodes

- FlowPackageProvider
- FlowPackageSerializer