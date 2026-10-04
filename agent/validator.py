"""Deterministic validator: the only gate between a deliberated plan and the Provisioner.

It holds no policy about WHICH plan is good (that is learned from the graph). It only
rejects plans that are impossible or unsafe: unknown capabilities/parameters, values
outside the system bounds, malformed actions. SLO relaxations above nominal are allowed
but flagged, so the recorder/evaluator can label the result 'compromised'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_catalog(drv):
    with drv.session() as s:
        params = {r["id"]: r.data() for r in s.run(
            "MATCH (p:Parameter) RETURN p.id AS id, p.unit AS unit, p.min AS min, p.max AS max, p.allowed AS allowed")}
        caps = {r["id"] for r in s.run("MATCH (c:Capability) RETURN c.id AS id")}
        nominal = {r["id"]: r.data() for r in s.run(
            "MATCH (d:Dataflow) RETURN d.id AS id, d.nominal_freshness_slo AS freshness, d.nominal_drop_ratio_slo AS drop")}
    return {"parameters": params, "capabilities": caps, "nominal": nominal}


SLO_PARAMS = {"parameter:freshness_slo_s": "freshness", "parameter:drop_ratio_slo": "drop"}


def validate_action(a, catalog, dataflow_id=None):
    """Returns (violations, flags)."""
    v, flags = [], []
    par, cap = a.get("parameter"), a.get("capability")
    if not par and not cap:
        return ["action names neither a parameter nor a capability"], flags
    if cap and cap not in catalog["capabilities"]:
        v.append(f"unknown capability {cap}")
    if par:
        spec = catalog["parameters"].get(par)
        if spec is None:
            return v + [f"unknown parameter {par}"], flags
        val = a.get("to")
        if spec.get("allowed"):
            if val not in spec["allowed"]:
                v.append(f"{par}: {val!r} not in {spec['allowed']}")
        elif spec.get("min") is not None:
            try:
                x = float(val)
            except (TypeError, ValueError):
                return v + [f"{par}: value {val!r} is not numeric"], flags
            if not (spec["min"] <= x <= spec["max"]):
                v.append(f"{par}: {x} outside system bounds [{spec['min']}, {spec['max']}]")
            elif par in SLO_PARAMS and dataflow_id:
                nom = catalog["nominal"].get(dataflow_id, {}).get(SLO_PARAMS[par])
                if nom is not None and x > nom:
                    flags.append(f"{par}: {x} relaxes SLO above nominal {nom}")
    return v, flags


def validate_plan(actions, catalog, dataflow_id=None):
    """Returns {'ok': bool, 'violations': [...], 'flags': [...]}. Empty plans are rejected."""
    if not actions:
        return {"ok": False, "violations": ["empty plan"], "flags": []}
    viol, flags = [], []
    for i, a in enumerate(actions):
        v, f = validate_action(a, catalog, dataflow_id)
        viol += [f"action {i}: {x}" for x in v]
        flags += [f"action {i}: {x}" for x in f]
    return {"ok": not viol, "violations": viol, "flags": flags}
