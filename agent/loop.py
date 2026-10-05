"""BDI control loop. Policy lives in the graph (retrieval) and the validator, not in a prompt.

perceive -> options (retrieval) -> filter (validator) -> deliberate -> act (Provisioner) -> learn (recorder)

Deliberator and Provisioner are plug-in points: the default deliberator is deterministic
(top-ranked candidate above a minimum score); an LLM deliberator can replace it later and
choose among the same grounded, validated candidates. The stub Provisioner only updates
the graph; the real one will render charts and push through Gate A/B.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import retrieval, validator
from agent.recorder import Recorder

SLO_FIELD = {"parameter:freshness_slo_s": "freshness_slo", "parameter:drop_ratio_slo": "drop_ratio_slo"}


def _typed(v):
    try:
        return float(v) if "." in v else int(v)
    except (TypeError, ValueError):
        return v


class TopScoreDeliberator:
    def __init__(self, min_score=0.2):
        self.min_score = min_score

    def choose(self, beliefs, options):
        """options: validated candidates, best first. Return one or None (= escalate)."""
        return options[0] if options and options[0]["score"] >= self.min_score else None


class StubProvisioner:
    """Applies SLO changes to the Dataflow node; other parameters are only recorded."""
    def __init__(self, drv):
        self.drv = drv

    def apply(self, dataflow_id, actions):
        with self.drv.session() as s:
            for a in actions:
                f = SLO_FIELD.get(a.get("parameter"))
                if f:
                    s.run(f"MATCH (d:Dataflow {{id:$id}}) SET d.{f} = $v", id=dataflow_id, v=float(a["to"]))
        return {"applied": len(actions), "ok": True}

    def restore_nominal(self, dataflow_id):
        with self.drv.session() as s:
            s.run("""MATCH (d:Dataflow {id:$id})
                     SET d.freshness_slo = d.nominal_freshness_slo, d.drop_ratio_slo = d.nominal_drop_ratio_slo""",
                  id=dataflow_id)


class Agent:
    def __init__(self, drv, recorder=None, deliberator=None, provisioner=None, goal_id="goal:keep_slos"):
        self.drv = drv
        self.rec = recorder or Recorder(drv)
        self.deliberator = deliberator or TopScoreDeliberator()
        self.prov = provisioner or StubProvisioner(drv)
        self.goal_id = goal_id
        self.catalog = validator.load_catalog(drv)

    # ---- beliefs -----------------------------------------------------------------
    def perceive(self, kind, dataflow_id, detail):
        with self.drv.session() as s:
            d = s.run("""MATCH (d:Dataflow {id:$id})
                         RETURN d.freshness_slo AS fr, d.drop_ratio_slo AS dr,
                                d.nominal_freshness_slo AS nfr, d.nominal_drop_ratio_slo AS ndr""",
                      id=dataflow_id).single()
        return {"kind": kind, "dataflow": dataflow_id, "detail": detail,
                "effective": {"freshness": d["fr"], "drop": d["dr"]},
                "nominal": {"freshness": d["nfr"], "drop": d["ndr"]}}

    # ---- options + filter ----------------------------------------------------------
    def options(self, b):
        out = []
        for c in retrieval.candidates(self.drv, b["kind"], b["detail"], b["dataflow"]):
            actions = [{"parameter": p, "to": _typed(v)} for p, v in c["signature"]]
            res = validator.validate_plan(actions, self.catalog, b["dataflow"])
            if res["ok"]:
                out.append({**c, "actions": actions, "flags": res["flags"]})
        return out

    # ---- one full cycle --------------------------------------------------------------
    def handle(self, kind, dataflow_id, detail, measure, before, window_s=300):
        """measure(plan_actions) -> {'good','drop'} observed after acting (real: Prometheus)."""
        b = self.perceive(kind, dataflow_id, detail)
        event = self.rec.record_event(kind, dataflow_id, detail)
        opts = self.options(b)
        pick = self.deliberator.choose(b, opts)
        if pick is None:
            plan = self.rec.record_plan(event, self.goal_id, "no validated candidate above threshold; escalate",
                                        [], status="escalated", source="agent")
            return {"decision": "escalate", "plan": plan, "options": opts}
        plan = self.rec.record_plan(event, self.goal_id,
                                    f"retrieved candidate score={pick['score']} support={pick['support']}",
                                    pick["actions"], source="agent")
        self.prov.apply(dataflow_id, pick["actions"])
        after = measure(pick["actions"])
        eff = self.perceive(kind, dataflow_id, detail)["effective"]  # SLO as actually in force
        verdict = self.rec.record_outcome(plan, dataflow_id, after, before, eff, b["nominal"], window_s)
        return {"decision": "act", "plan": plan, "actions": pick["actions"], "flags": pick["flags"],
                "verdict": verdict, "options": opts}
