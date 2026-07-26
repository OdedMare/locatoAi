---
type: "query"
date: "2026-07-25T08:32:48.228715+00:00"
question: "in tyche theres sometimes that theres requierd params to fetch and cases of timeFrom timeTo so i need to config them in the ui make sure we suitable to this"
contributor: "graphify"
outcome: "useful"
source_nodes: ["TycheSource", "TycheQueryBuilder", "CatalogRouter", "LayersPanel"]
---

# Q: in tyche theres sometimes that theres requierd params to fetch and cases of timeFrom timeTo so i need to config them in the ui make sure we suitable to this

## Answer

Expanded from original query via graph vocab: [tyche, catalog, configuration, parameter, required, time, from, event, mapping, fetch, layer, provider]. TycheSource persists and validates typed fixed request parameters plus optional split time fields; TycheQueryBuilder emits either nested match bounds or separate timeFrom/timeTo values; CatalogRouter carries the configuration from the layer DTO into source_url; LayersPanel exposes labeled RTL controls for both modes and key/value parameters.

## Outcome

- Signal: useful

## Source Nodes

- TycheSource
- TycheQueryBuilder
- CatalogRouter
- LayersPanel