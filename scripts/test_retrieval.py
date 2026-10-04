import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.retrieval import candidates
from scripts.common import driver

drv = driver()
def show(title, **kw):
    print("\n" + title)
    for c in candidates(drv, **kw):
        print(f"  {c['score']:+.3f}  n={c['support']}  {dict(c['counts'])}  {list(c['signature'])}")
    return candidates(drv, **kw)

a = show("link_degradation 120 ms", kind="link_degradation", detail={"delay_ms": 120})
b = show("link_degradation 450 ms", kind="link_degradation", detail={"delay_ms": 450})
c = show("service_migration", kind="service_migration", detail={})

assert a[0]["signature"] == (("parameter:scrape_interval_s", "30"),), "120ms: scrape 30 should rank first"
assert a[-1]["signature"][0][0] == "parameter:log_level", "120ms: log_level change should rank last"
assert b[0]["signature"] != (("parameter:scrape_interval_s", "30"),), "450ms: scrape 30 alone must not win"
assert c[0]["signature"] == (("parameter:max_pod_count", "3"),)
print("\nretrieval checks OK")
