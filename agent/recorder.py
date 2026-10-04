"""Trajectory recorder: writes one deliberation cycle into the context graph.

Event -[TRIGGERED]-> Plan -[HAS_ACTION]-> Action -[PRODUCED]-> ConfigVersion
Plan -[RESULTED_IN]-> Outcome -[ABOUT]-> Dataflow ;  ConfigVersion -[SUPERSEDES]-> previous
Optional: (ReasoningTrace)-[PRODUCED]->(Plan) from neo4j-agent-memory.
"""
import sys, uuid, json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.common import driver  # noqa: E402

# v1 thresholds: freshness violation ratio <= 0.20, drop ratio <= 0.05
MIN_GOOD_RATIO = 0.80
MAX_DROP_RATIO = 0.05


def now():
    return datetime.now(timezone.utc).isoformat()


def verdict(after, before, effective, nominal):
    """after/before: {'good': float, 'drop': float}; effective/nominal: {'freshness': s, 'drop': ratio}.
    recovered   - constraints met and SLO not relaxed above nominal
    compromised - constraints met only because an SLO was relaxed above nominal
    degraded    - constraints not met and clearly worse than before
    no_effect   - constraints not met, not clearly worse
    """
    met = after["good"] >= MIN_GOOD_RATIO and after["drop"] <= MAX_DROP_RATIO
    relaxed = (effective["freshness"] > nominal["freshness"]
               or effective["drop"] > nominal["drop"])
    if met:
        return "compromised" if relaxed else "recovered"
    if before and after["good"] < before["good"] - 0.02:
        return "degraded"
    return "no_effect"


class Recorder:
    def __init__(self, drv=None):
        self.drv = drv or driver()

    def _run(self, q, **p):
        with self.drv.session() as s:
            return s.run(q, **p).data()

    def record_event(self, kind, dataflow_id=None, detail=None, ts=None):
        eid = f"event:{uuid.uuid4().hex[:12]}"
        self._run(
            """CREATE (e:Event:Entity {id:$id, name:$kind, kind:$kind, ts:$ts,
                        detail:$detail, type:'EVENT'})
               WITH e OPTIONAL MATCH (d:Dataflow {id:$df})
               FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END |
                        MERGE (e)-[:AFFECTS]->(d))""",
            id=eid, kind=kind, ts=ts or now(), detail=json.dumps(detail or {}), df=dataflow_id)
        return eid

    def record_plan(self, event_id, goal_id, rationale, actions, trace_id=None, status="committed"):
        """actions: list of {'capability': id|None, 'parameter': id|None, 'from':x, 'to':y,
                             'cluster': id, 'new_config': {...}|None}"""
        pid = f"plan:{uuid.uuid4().hex[:12]}"
        self._run(
            """CREATE (p:Plan {id:$pid, ts:$ts, rationale:$why, status:$status})
               WITH p MATCH (e:Event {id:$eid}) MERGE (e)-[:TRIGGERED]->(p)
               WITH p OPTIONAL MATCH (g:Goal {id:$gid})
               FOREACH (_ IN CASE WHEN g IS NULL THEN [] ELSE [1] END | MERGE (p)-[:SERVES]->(g))
               WITH p OPTIONAL MATCH (t:ReasoningTrace {id:$tid})
               FOREACH (_ IN CASE WHEN t IS NULL THEN [] ELSE [1] END | MERGE (t)-[:PRODUCED]->(p))""",
            pid=pid, ts=now(), why=rationale, status=status, eid=event_id, gid=goal_id, tid=trace_id)
        for i, a in enumerate(actions):
            aid = f"{pid}:a{i}"
            self._run(
                """MATCH (p:Plan {id:$pid})
                   CREATE (a:Action {id:$aid, seq:$i, from_value:$frm, to_value:$to, ts:$ts})
                   MERGE (p)-[:HAS_ACTION]->(a)
                   WITH a OPTIONAL MATCH (c:Capability {id:$cap})
                   FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (a)-[:USES]->(c))
                   WITH a OPTIONAL MATCH (pa:Parameter {id:$par})
                   FOREACH (_ IN CASE WHEN pa IS NULL THEN [] ELSE [1] END | MERGE (a)-[:SETS]->(pa))""",
                pid=pid, aid=aid, i=i, frm=_s(a.get("from")), to=_s(a.get("to")), ts=now(),
                cap=a.get("capability"), par=a.get("parameter"))
            if a.get("new_config") is not None:
                self._new_config(aid, a["cluster"], a["new_config"])
        return pid

    def _new_config(self, action_id, cluster_id, cfg):
        self._run(
            """MATCH (a:Action {id:$aid})
               MATCH (old:ConfigVersion {cluster:$cl}) WHERE old.valid_to IS NULL
               WITH a, old ORDER BY old.version DESC LIMIT 1
               SET old.valid_to = $ts
               CREATE (n:ConfigVersion:Entity {id:'configversion:'+$cl+':'+toString(old.version+1),
                       cluster:$cl, version:old.version+1, valid_from:$ts, valid_to:null,
                       exporters:$exp, scrape_interval_s:$si, type:'OBJECT'})
               MERGE (n)-[:SUPERSEDES]->(old)
               MERGE (a)-[:PRODUCED]->(n)""",
            aid=action_id, cl=cluster_id, ts=now(),
            exp=cfg.get("exporters", []), si=cfg.get("scrape_interval_s"))

    def record_outcome(self, plan_id, dataflow_id, after, before, effective, nominal, window_s):
        v = verdict(after, before, effective, nominal)
        oid = f"outcome:{plan_id.split(':',1)[1]}:{dataflow_id.split(':',1)[1]}"
        self._run(
            """MATCH (p:Plan {id:$pid}), (d:Dataflow {id:$df})
               CREATE (o:Outcome {id:$oid, ts:$ts, window_s:$w, verdict:$v,
                       good_ratio:$g, drop_ratio:$dr, good_ratio_before:$gb, drop_ratio_before:$db,
                       effective_freshness_slo:$ef, effective_drop_slo:$ed})
               MERGE (p)-[:RESULTED_IN]->(o) MERGE (o)-[:ABOUT]->(d)""",
            pid=plan_id, df=dataflow_id, oid=oid, ts=now(), w=window_s, v=v,
            g=after["good"], dr=after["drop"],
            gb=(before or {}).get("good"), db=(before or {}).get("drop"),
            ef=effective["freshness"], ed=effective["drop"])
        return v


def _s(x):
    return None if x is None else str(x)
