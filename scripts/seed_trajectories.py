"""Hand-written trajectories for testing retrieval (Plan.source = 'handwritten'). Idempotent."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.recorder import Recorder

r = Recorder()
r._run("""MATCH (p:Plan {source:'handwritten'})
          OPTIONAL MATCH (e:Event)-[:TRIGGERED]->(p)
          OPTIONAL MATCH (p)-[:HAS_ACTION]->(a:Action) OPTIONAL MATCH (p)-[:RESULTED_IN]->(o:Outcome)
          DETACH DELETE p, e, a, o""")
r._run("""MATCH (e:Event) WHERE e.detail CONTAINS 'synthetic'
          OPTIONAL MATCH (e)-[:TRIGGERED]->(p:Plan)
          OPTIONAL MATCH (p)-[:HAS_ACTION]->(a:Action) OPTIONAL MATCH (p)-[:RESULTED_IN]->(o:Outcome)
          DETACH DELETE e, p, a, o""")  # earlier recorder-test data would pollute retrieval
r._run("MERGE (g:Goal {id:'goal:keep_slos'}) SET g.name='keep dataflow SLOs'")
dfs = [x["id"] for x in r._run("MATCH (d:Dataflow) RETURN d.id AS id ORDER BY id")]
NOM = {"freshness": 30.0, "drop": 0.02}
RELAX = {"freshness": 60.0, "drop": 0.02}
BEFORE = {"good": 0.45, "drop": 0.08}
S, F, L, P = "parameter:scrape_interval_s", "parameter:freshness_slo_s", "parameter:log_level", "parameter:max_pod_count"

# (event kind, detail, dataflow idx, actions, after, effective slo)
T = [
 ("link_degradation", {"delay_ms": 100}, 0, [(S, 30)], {"good": .93, "drop": .01}, NOM),
 ("link_degradation", {"delay_ms": 120}, 1, [(S, 30)], {"good": .91, "drop": .02}, NOM),
 ("link_degradation", {"delay_ms": 80},  0, [(S, 30)], {"good": .95, "drop": .01}, NOM),
 ("link_degradation", {"delay_ms": 100}, 0, [(L, "DEBUG")], {"good": .44, "drop": .08}, NOM),
 ("link_degradation", {"delay_ms": 110}, 1, [(L, "DEBUG")], {"good": .30, "drop": .09}, NOM),
 ("link_degradation", {"delay_ms": 100}, 1, [(F, 60)], {"good": .96, "drop": .01}, RELAX),
 ("link_degradation", {"delay_ms": 400}, 0, [(S, 30)], {"good": .50, "drop": .06}, NOM),
 ("link_degradation", {"delay_ms": 400}, 1, [(S, 60), (F, 90)], {"good": .90, "drop": .02}, {"freshness": 90.0, "drop": .02}),
 ("service_migration", {}, 0, [(P, 3)], {"good": .92, "drop": .01}, NOM),
 ("service_migration", {}, 1, [(P, 3)], {"good": .90, "drop": .02}, NOM),
 ("service_migration", {}, 0, [(S, 30)], {"good": .46, "drop": .08}, NOM),
]
for kind, detail, di, acts, after, eff in T:
    df = dfs[di % len(dfs)]
    ev = r.record_event(kind, df, detail)
    pl = r.record_plan(ev, "goal:keep_slos", "handwritten",
                       [{"parameter": p, "to": v} for p, v in acts])
    r._run("MATCH (p:Plan {id:$id}) SET p.source='handwritten'", id=pl)
    r.record_outcome(pl, df, after, BEFORE, eff, NOM, 300)
print(f"seeded {len(T)} handwritten trajectories over {len(dfs)} dataflows")
