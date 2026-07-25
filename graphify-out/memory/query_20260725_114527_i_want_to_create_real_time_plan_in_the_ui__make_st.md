---
type: "query"
date: "2026-07-25T11:45:27.600906+00:00"
question: "i want to create real time plan in the ui; make stream mode and enable this mode at the ui"
contributor: "graphify"
outcome: "useful"
source_nodes: ["QueryOrchestrator", "QueryEventSink", "AppShell", "AgentTrace", "geoQueryService.ts"]
---

# Q: i want to create real time plan in the ui; make stream mode and enable this mode at the ui

## Answer

Expanded from original query via graph vocabulary: app, shell, query, service, orchestrator, stage, step, event, stream, status, trace, execute. The existing QueryEventSink and QueryOrchestrator stage/execute_step events were exposed through POST /api/query/stream as SSE. AppShell owns a live-updates toggle, enabled by default; geoQueryService selects SSE or the existing JSON endpoint, and AgentTrace renders loading, filtering, clustering, counts, errors, and completion live.

## Outcome

- Signal: useful

## Source Nodes

- QueryOrchestrator
- QueryEventSink
- AppShell
- AgentTrace
- geoQueryService.ts