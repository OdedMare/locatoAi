# Ranking

**Use when:** The user asks which features are the most or least something — most
vulnerable, most exposed, highest risk, best or worst candidates — across one subject
layer inside the requested polygon. The answer is an ordered list with a score, not a
plain filter.

**Do not use when:** The user asks for a plain overview of an area (use the
`area-summary` profile) or one narrow geographic question a normal single-layer plan
answers directly.

## Ranking target

Rank the features of the requested subject layer inside the polygon received with the
request. Every other eligible layer contributes rule scores; never rank a layer the
user did not ask about.

## Workflow

1. Load the subject layer inside the polygon.
2. [parallel] Score each proximity rule against its hazard or reference layer.
3. [parallel] Score each density rule by how many rule features surround each subject.
4. [parallel] Score each attribute rule from the subject's own fields.
5. Sum the weighted contributions per feature and order them from highest to lowest.

## Ranking rules

Every rule is declared in the catalog, never invented at query time. A rule layer opts
in with the `ranking` profile and exactly one `rank:<kind>` tag — `rank:proximity`,
`rank:density`, or `rank:attribute`. Steps marked `[parallel]` are independent and may
run concurrently; wait for all of them before the next sequential step.

Each rule produces a raw score in `[0, 1]` multiplied by its `rank:weight` (default
`1.0`). A feature's total is the sum of its weighted contributions, and
`normalized_score` divides that total by the sum of every successful rule's weight.
Never invent a layer, field, entity, weight, or score. Preserve the source layer,
observation time, and available evidence for every contribution. Continue when one rule
fails and report partial coverage. Write the final user-facing summary in Hebrew.

## Rule tag vocabulary

| Tag | Applies to | Meaning |
|---|---|---|
| `rank:proximity` | rule layer | Score by distance from each subject to the nearest rule feature |
| `rank:density` | rule layer | Score by how many rule features fall within the radius |
| `rank:attribute` | rule layer | Score from a field on the subject features themselves |
| `rank:weight:<number>` | any rule | Relative importance, positive, default `1.0` |
| `rank:distance_m:<meters>` | proximity, density | Radius, default `500` |
| `rank:direction:closer_is_worse` | proximity | Default — nearer scores higher |
| `rank:direction:closer_is_better` | proximity | Inverted — farther scores higher |
| `rank:saturation_count:<number>` | density | Count that reaches a full score, default `10` |
| `rank:field:<name>` | attribute | Subject field to read, required |
| `rank:equals:<value>` | attribute | Exact match scores `1.0`, otherwise no contribution |
| `rank:min:<number>` / `rank:max:<number>` | attribute | Numeric range normalized to `[0, 1]`, defaults `0` and `1` |

## Worked example

"Which houses are most vulnerable to earthquakes?" ranks the houses layer with rules
such as a `rank:proximity` fault-line layer (`rank:weight:0.4`,
`rank:distance_m:1000`), a `rank:attribute` construction-year field
(`rank:field:build_year`, `rank:min:1980`, `rank:max:1920`, `rank:weight:0.4` — an
inverted range makes older score higher), and a `rank:density` soil-liquefaction layer
(`rank:weight:0.2`). Each house receives a total score plus the per-rule breakdown that
produced it.
