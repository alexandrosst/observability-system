"""Seed the Capability layer from the v1 YAML level files.

Exporters become Capability nodes (PROVIDES -> Signal). Parameters and
resource dimensions are created explicitly. v1 levels are kept as ConfigPreset
nodes (reference points), so they are data, not code or prompt text.

AFFECTS edges carry only a qualitative `direction` and `source: "prior"`.
They are placeholders to be replaced by effects learned from trajectories.
"""
import yaml
from common import ROOT, driver

DIMENSIONS = ["freshness", "completeness", "energy", "network_load", "compute_load"]

# name -> (unit, min, max); bounds come from v1 tuning_levels.yaml and tools
PARAMETERS = {
    "scrape_interval_s": ("s", 5, 60),
    "freshness_slo_s":   ("s", 5, 120),
    "drop_ratio_slo":    ("ratio", 0.001, 0.10),
    "log_level":         ("enum", None, None),
    "max_pod_count":     ("count", 1, 10),
}

ENUM_LOG_LEVELS = ["INFO", "DEBUG"]  # values used by v1 tuning levels

# qualitative priors: (parameter, dimension, direction) where direction is the
# sign of the dimension change when the parameter value INCREASES
PRIORS = [
    ("scrape_interval_s", "freshness", "worsens"),
    ("scrape_interval_s", "energy", "reduces"),
    ("scrape_interval_s", "network_load", "reduces"),
    ("max_pod_count", "compute_load", "increases"),
    ("max_pod_count", "completeness", "improves"),
]


def seconds(s: str) -> int:
    return int(str(s).rstrip("s"))


def main():
    cov = yaml.safe_load((ROOT / "seed/coverage_levels.yaml").read_text())
    tun = yaml.safe_load((ROOT / "seed/tuning_levels.yaml").read_text())
    drv = driver()
    with drv.session() as s:
        for d in DIMENSIONS:
            s.run("MERGE (n:ResourceDimension {id:$id}) SET n.name=$n",
                  id=f"dimension:{d}", n=d)
        for name, (unit, lo, hi) in PARAMETERS.items():
            s.run("MERGE (p:Parameter {id:$id}) SET p.name=$n, p.unit=$u, p.min=$lo, p.max=$hi",
                  id=f"parameter:{name}", n=name, u=unit, lo=lo, hi=hi)
        s.run("MATCH (p:Parameter {id:'parameter:log_level'}) SET p.allowed = $a", a=ENUM_LOG_LEVELS)
        for p, d, direction in PRIORS:
            s.run("""MATCH (p:Parameter {id:$p}), (d:ResourceDimension {id:$d})
                     MERGE (p)-[a:AFFECTS]->(d) SET a.direction=$dir, a.source='prior'""",
                  p=f"parameter:{p}", d=f"dimension:{d}", dir=direction)
        for e in cov["exporters"]:
            s.run("""MERGE (sg:Signal {id:$sid}) SET sg.name=$sig
                     MERGE (c:Capability {id:$cid})
                       SET c.name=$n, c.kind='exporter', c.description=$desc
                     MERGE (c)-[:PROVIDES]->(sg)""",
                  sid=f"signal:{e['signal']}", sig=e["signal"],
                  cid=f"capability:{e['name']}", n=e["name"], desc=e["description"])
        for i, lv in enumerate(cov["levels"]):
            s.run("""MERGE (pr:ConfigPreset {id:$id})
                       SET pr.kind='coverage', pr.name=$n, pr.level=$i, pr.source='v1'""",
                  id=f"preset:coverage:{lv['name']}", n=lv["name"], i=i)
            for ex in lv["exporters"]:
                s.run("""MATCH (pr:ConfigPreset {id:$pid}), (c:Capability {id:$cid})
                         MERGE (pr)-[:ENABLES]->(c)""",
                      pid=f"preset:coverage:{lv['name']}", cid=f"capability:{ex}")
        for i, lv in enumerate(tun["levels"]):
            pid = f"preset:tuning:{lv['name']}"
            s.run("""MERGE (pr:ConfigPreset {id:$id})
                       SET pr.kind='tuning', pr.name=$n, pr.level=$i, pr.source='v1'""",
                  id=pid, n=lv["name"], i=i)
            vals = {
                "scrape_interval_s": seconds(lv["scrape_interval"]),
                "freshness_slo_s": lv["freshness_slo"],
                "drop_ratio_slo": lv["drop_ratio_slo"],
                "log_level": lv["log_level"],
                "max_pod_count": lv["pod_multiplier"],  # v1: BASE_POD_COUNT(1) * multiplier
            }
            for pname, val in vals.items():
                s.run("""MATCH (pr:ConfigPreset {id:$pid}), (p:Parameter {id:$par})
                         MERGE (pr)-[r:SETS]->(p) SET r.value=$v""",
                      pid=pid, par=f"parameter:{pname}", v=val)
        print(s.run("MATCH (c:Capability) RETURN count(c) AS c").single()["c"], "capabilities;",
              s.run("MATCH (p:ConfigPreset) RETURN count(p) AS c").single()["c"], "presets")
    drv.close()


if __name__ == "__main__":
    main()
