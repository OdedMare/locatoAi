"""Score subject features by one of their own numeric or matching fields."""

import pandas as pd

from app.bl.ranking.models.contribution import RankingContribution
from app.bl.ranking.rule_config import (
    configured_field,
    numeric_field,
    required_field,
    weight,
)
from app.bl.ranking.rule_support import (
    clamp_unit,
    clean_value,
    evidence_for,
    require_field,
)


def score_attribute(subjects, _rule_data, layer):
    """Return {subject index: RankingContribution} for an attribute rule."""
    field = require_field(subjects, required_field(layer, "field"), "attribute")
    match_value = configured_field(layer, "equals")
    if match_value is not None:
        return _match_scores(subjects, layer, field, match_value)
    return _range_scores(subjects, layer, field)


def _match_scores(subjects, layer, field, match_value):
    rule_weight = weight(layer)
    target = match_value.casefold()
    return {
        index: _contribution(
            row, layer, 1.0, rule_weight,
            "{} = {}.".format(field, clean_value(row[field])),
        )
        for index, row in subjects.iterrows()
        if clean_value(row[field]).casefold() == target
    }


def _range_scores(subjects, layer, field):
    minimum = numeric_field(layer, "min", 0.0)
    maximum = numeric_field(layer, "max", 1.0)
    # max < min is a deliberate inversion (older/lower scores higher); only an
    # empty range is unusable.
    if maximum == minimum:
        raise ValueError("Ranking rank:max must differ from rank:min")
    rule_weight = weight(layer)
    values = pd.to_numeric(subjects[field], errors="coerce")
    return {
        index: _range_contribution(
            subjects.loc[index], layer, field, value, minimum, maximum,
            rule_weight,
        )
        for index, value in values.items()
        if not pd.isna(value)
    }


def _range_contribution(
    row, layer, field, value, minimum, maximum, rule_weight
):
    raw = clamp_unit((float(value) - minimum) / (maximum - minimum))
    return _contribution(
        row, layer, raw, rule_weight, "{} = {}.".format(field, value)
    )


def _contribution(row, layer, raw, rule_weight, text):
    return RankingContribution(
        kind="attribute", rule_layer_id=layer.id, rule_layer_name=layer.name,
        text=text, weight=rule_weight, raw_score=raw,
        weighted_score=raw * rule_weight, evidence=[evidence_for(row)],
    )
