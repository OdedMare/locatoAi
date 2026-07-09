"""Agent call 2: plan building — Day 2.

Input: user query + schemas of the selected layers (from CatalogService,
field names/types/descriptions only, truncated to ~200 chars).
Output: GeoQueryPlan JSON, validated by bl.plan.validators. On validation
failure: retry once with the error appended, then fall back to clarify.
"""

# DAY 2: implement build_plan(query, schemas, has_geometry) here.
