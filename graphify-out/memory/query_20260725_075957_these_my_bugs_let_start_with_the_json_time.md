---
type: "query"
date: "2026-07-25T07:59:57.604016+00:00"
question: "these my bugs let start with the json time"
contributor: "graphify"
outcome: "useful"
source_nodes: ["FlowPackageMetadata", "FlowPackageProvider"]
---

# Q: these my bugs let start with the json time

## Answer

Expanded from original query via graph vocab: [flow, package, time, parameter, json, value, metadata, request, flapi, generate]. The Flow Package time control selected scalar options before checking the time type, so FLAPI time metadata with Options sent a string to FlowPackageSerializer, which correctly requires a JSON object. Fixed by rendering the JSON textarea for time parameters before the options branch.

## Outcome

- Signal: useful

## Source Nodes

- FlowPackageMetadata
- FlowPackageProvider