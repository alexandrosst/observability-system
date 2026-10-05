"""Runs the BDI loop against a toy environment (stub Provisioner, simulated metrics)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.loop import Agent, PriorExplorer
from scripts.common import driver

drv = driver()
agent = Agent(drv)
DF = agent.rec._run("MATCH (d:Dataflow) RETURN d.id AS id ORDER BY id LIMIT 1")[0]["id"]
BEFORE = {"good": 0.45, "drop": 0.08}

def env(actions):
    """Toy world for a 120 ms link degradation: scrape 30 s fixes it; relaxing SLOs hides it; rest does nothing."""
    p = {a["parameter"]: a["to"] for a in actions}
    if p.get("parameter:scrape_interval_s", 0) >= 30: return {"good": .93, "drop": .01}
    if p.get("parameter:freshness_slo_s", 0) >= 60:  return {"good": .96, "drop": .01}
    return {"good": .44, "drop": .08}

def show(title, r):
    print(f"\n{title}\n  decision={r['decision']}  verdict={r.get('verdict')}  actions={r.get('actions')}  flags={r.get('flags')}")
    for o in r["options"]: print(f"    option {o['score']:+.3f} n={o['support']} {list(o['signature'])}")

try:
    show("1) link_degradation 120 ms", agent.handle("link_degradation", DF, {"delay_ms": 120}, env, BEFORE))
    show("2) unseen event kind, no explorer (escalates)", agent.handle("node_failure", DF, {}, env, BEFORE))
    agent.explorer = PriorExplorer(drv)
    show("3) unseen event kind, with explorer", agent.handle("node_failure", DF, {}, env, BEFORE))
finally:
    agent.prov.restore_nominal(DF)
    print("\nSLOs restored to nominal; demo plans are tagged source='agent'.")
