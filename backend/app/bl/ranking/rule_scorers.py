from app.bl.ranking.attribute_scorer import score_attribute
from app.bl.ranking.density_scorer import score_density
from app.bl.ranking.proximity_scorer import score_proximity


def score_rule(kind, subjects, rule_data, layer):
    if kind == "proximity":
        return score_proximity(subjects, rule_data, layer)
    if kind == "density":
        return score_density(subjects, rule_data, layer)
    return score_attribute(subjects, rule_data, layer)
