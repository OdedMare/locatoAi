# `contains`

**Use when:** Keep input geometries that fully contain a reference geometry.

**Do not use when:** The requested direction is reversed (“features inside X” is not expressible by this input-contains-target operation), the geometries only cross or touch, or the user merely asks for proximity.

Direction is strict: input contains target. Use the latest subject-chain step as input. A named target requires its complete filter. Add the reference layer to `context_layers`.
