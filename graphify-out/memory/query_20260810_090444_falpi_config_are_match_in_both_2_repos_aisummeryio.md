---
type: "query"
date: "2026-08-10T09:04:44.863578+00:00"
question: "falpi config are match in both 2 repos aisummeryio and locato"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Settings", "RuntimeSettingsStore", "FlapiProvider"]
---

# Q: falpi config are match in both 2 repos aisummeryio and locato

## Answer

Expanded from original query via graph vocab: [flapi, config, configuration, provider, package, runtime, settings, token, username]. Verified against live code because the checked-in graph includes stale removed FLAPI modules. LocatoAI and AiSummryIO produce the same FLUNKS credential configuration: username, token, TLS verification, 120-second timeout, and FlunksRunner named arguments. LocatoAI intentionally sources token and TLS from cubes_token/cubes_verify_tls because Cubes and Flow Packages share FLAPI credentials; AiSummryIO calls the equivalent fields flapi_token/flapi_verify_tls. Local effective runtime values match after this mapping, and focused tests passed in both repositories. No code change was needed.

## Outcome

- Signal: useful

## Source Nodes

- Settings
- RuntimeSettingsStore
- FlapiProvider