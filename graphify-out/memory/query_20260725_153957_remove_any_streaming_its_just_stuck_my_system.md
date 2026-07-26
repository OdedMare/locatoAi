---
type: "query"
date: "2026-07-25T15:39:57.043190+00:00"
question: "remove any streaming its just stuck my system "
contributor: "graphify"
outcome: "useful"
source_nodes: ["submitQuery()", "QueryRouter", "QueryEventSink", "AgentTrace()"]
---

# Q: remove any streaming its just stuck my system 

## Answer

Expanded from original query via graph vocab: [stream, query, submit, event, sink, trace, live, mode, response, router]. Removed query SSE end to end: submitQuery now posts only to /api/query, QueryRouter exposes only the JSON route, QueryEventSink retains final-response diagnostics without forwarding, and AgentTrace shows a loading state followed by the completed trace. Frontend build and lint passed; focused Python 3.8 query tests passed.

## Outcome

- Signal: useful

## Source Nodes

- submitQuery()
- QueryRouter
- QueryEventSink
- AgentTrace()