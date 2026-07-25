# Area summary

**Use when:** The user asks for an area overview or a free-language summary of what exists, happened, or matters inside and immediately around the requested polygon.

**Do not use when:** The user asks one narrow geographic question that a normal single-layer plan answers directly.

## Summary target

Use the polygon received with the request.

## Workflow

1. Check the static house, synagogue, and school layers.
2. [parallel] Check shared arrivals in the friends-arrivals layer.
3. [parallel] Check the events layer for anything important nearby.
4. Summarize the facts in workflow order.

## Summary rules

Follow the workflow order and never invent a layer, field, or entity. Steps marked
`[parallel]` are independent and may run concurrently; wait for all of them before
the next sequential step. Apply the target polygon to every relevant layer. Preserve
the source layer, observation time, and available evidence for every claim. Continue
when one layer fails and report partial coverage. Write the final user-facing summary
in Hebrew.
