"""Trajectory retrieval: structural similarity + action-effect aggregation, plain Cypher/Python.

Given a new Event, find past trajectories on similar events and rank candidate action
sets by their observed outcomes. Failures are kept: they lower a candidate's score and
are reported as negative evidence. No LLM, no prompt logic; the agent deliberates over
what this returns.
"""
import json, math, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UTILITY = {"recovered": 1.0, "compromised": 0.5, "no_effect": 0.0, "degraded": -1.0}
MAGNITUDE_KEYS = ("delay_ms", "replicas", "node_count")  # numeric event detail fields


def fetch_trajectories(drv, kind):
    q = """MATCH (e:Event {kind:$kind})-[:TRIGGERED]->(p:Plan)-[:RESULTED_IN]->(o:Outcome)
           OPTIONAL MATCH (e)-[:AFFECTS]->(d:Dataflow)
           OPTIONAL MATCH (p)-[:HAS_ACTION]->(a:Action)
           OPTIONAL MATCH (a)-[:SETS]->(par:Parameter)
           WITH e, p, o, d, collect({parameter: par.id, capability: null, to: a.to_value}) AS acts
           RETURN e.id AS event, e.detail AS detail, d.id AS dataflow, p.id AS plan,
                  o.verdict AS verdict, o.good_ratio AS good, o.good_ratio_before AS before, acts"""
    with drv.session() as s:
        return [r.data() for r in s.run(q, kind=kind)]


def similarity(new_detail, new_dataflow, row, sigma=0.5):
    sim = 1.0
    old = json.loads(row["detail"] or "{}")
    for k in MAGNITUDE_KEYS:
        if k in new_detail and k in old and old[k] and new_detail[k]:
            sim *= math.exp(-(math.log(new_detail[k] / old[k]) / sigma) ** 2)  # Gaussian in log-magnitude
    if new_dataflow and row["dataflow"] != new_dataflow:
        sim *= 0.5  # same kind of event on a different dataflow is weaker evidence
    return sim


def signature(acts):
    return tuple(sorted((a["parameter"], str(a["to"])) for a in acts if a["parameter"]))


def candidates(drv, kind, detail=None, dataflow=None, prior_weight=1.0, min_sim=0.05):
    """Ranked candidate action sets: [{signature, score, support, counts, evidence_plans}]."""
    agg = defaultdict(lambda: {"w": 0.0, "u": 0.0, "counts": defaultdict(int), "plans": []})
    for row in fetch_trajectories(drv, kind):
        w = similarity(detail or {}, dataflow, row)
        if w < min_sim or row["verdict"] not in UTILITY:
            continue
        a = agg[signature(row["acts"])]
        a["w"] += w
        a["u"] += w * UTILITY[row["verdict"]]
        a["counts"][row["verdict"]] += 1
        a["plans"].append(row["plan"])
    out = []
    for sig, a in agg.items():
        score = a["u"] / (a["w"] + prior_weight)  # shrink towards 0 when evidence is thin
        out.append({"signature": sig, "score": round(score, 3), "support": len(a["plans"]),
                    "counts": dict(a["counts"]), "evidence_plans": a["plans"]})
    return sorted(out, key=lambda c: -c["score"])
