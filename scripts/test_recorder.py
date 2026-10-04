"""Writes 3 synthetic trajectories (recovered, compromised, no_effect) and reads them back."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.recorder import Recorder, verdict

# pure-logic checks (no DB)
nom = {"freshness": 30.0, "drop": 0.02}
assert verdict({"good": .95, "drop": .01}, {"good": .4, "drop": .1}, nom, nom) == "recovered"
assert verdict({"good": .95, "drop": .01}, {"good": .4, "drop": .1}, {"freshness": 60.0, "drop": .02}, nom) == "compromised"
assert verdict({"good": .50, "drop": .01}, {"good": .6, "drop": .1}, nom, nom) == "degraded"
assert verdict({"good": .50, "drop": .01}, {"good": .5, "drop": .1}, nom, nom) == "no_effect"
print("verdict logic OK")

r = Recorder()
r._run("MERGE (g:Goal {id:'goal:test'}) SET g.name='keep freshness'")
DF = r._run("MATCH (d:Dataflow) RETURN d.id AS id LIMIT 1")[0]["id"]
op = r._run("MATCH (o:Operator)-[:HAS_CONFIGURATION]->(c:ConfigVersion) WHERE c.valid_to IS NULL RETURN o.id AS id LIMIT 1")[0]["id"]

def run(kind, actions, after, eff):
    ev = r.record_event(kind, DF, {"synthetic": True})
    pl = r.record_plan(ev, "goal:test", f"synthetic {kind}", actions)
    return r.record_outcome(pl, DF, after, {"good": .4, "drop": .1}, eff, nom, 300)

print(run("link_degradation", [{"parameter": "parameter:scrape_interval_s", "from": 15, "to": 30,
      "operator": op, "new_config": {"scrape_interval_s": 30, "exporters": ["kepler"]}}],
      {"good": .93, "drop": .01}, nom))
print(run("link_degradation", [{"parameter": "parameter:freshness_slo_s", "from": 30, "to": 60}],
      {"good": .96, "drop": .01}, {"freshness": 60.0, "drop": .02}))
print(run("service_migration", [{"parameter": "parameter:log_level", "from": "info", "to": "error"}],
      {"good": .31, "drop": .09}, nom))  # worse than before (.4) -> degraded

for row in r._run("""MATCH (e:Event)-[:TRIGGERED]->(p:Plan)-[:RESULTED_IN]->(o:Outcome)
                     WHERE e.detail CONTAINS 'synthetic'
                     RETURN e.kind AS event, o.verdict AS verdict, o.effective_freshness_slo AS slo
                     ORDER BY o.ts DESC LIMIT 3"""):
    print(row)

chain = r._run("""MATCH (o:Operator {id:$op})-[:HAS_CONFIGURATION]->(c:ConfigVersion)
                  OPTIONAL MATCH (c)-[:SUPERSEDES]->(prev)
                  RETURN c.id AS id, c.version AS v, c.valid_to IS NULL AS current, prev.id AS supersedes
                  ORDER BY c.version""", op=op)
for row in chain: print(row)
assert any(x["current"] and x["supersedes"] for x in chain), "no versioned config chain written"
