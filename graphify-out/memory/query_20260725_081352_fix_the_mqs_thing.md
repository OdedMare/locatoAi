---
type: "query"
date: "2026-07-25T08:13:52.056465+00:00"
question: "fix the mqs thing"
contributor: "graphify"
outcome: "useful"
source_nodes: [".entities_page_with_meta()", "Generate editable catalog metadata from a bounded provider sample."]
---

# Q: fix the mqs thing

## Answer

Expanded from the MQS metadata failure via graph vocab: [mqs, metadata, generate, layer, schema, sample, provider, gateway, catalog, field, entities, property]. The inventory GET route worked, but metadata sampling incorrectly used GET for the distinct Entities route. MQS documents Entities retrieval as POST with a filter body. Fixed MqsGateway so unfiltered sampling sends {filter:{}} via POST; spatial and attribute filters continue using their existing POST bodies. The MQS and metadata regression suites pass (65 tests).

## Outcome

- Signal: useful

## Source Nodes

- .entities_page_with_meta()
- Generate editable catalog metadata from a bounded provider sample.