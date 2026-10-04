import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.validator import load_catalog, validate_plan
from scripts.common import driver

cat = load_catalog(driver())
df = next(iter(cat["nominal"]))
cases = [
    ("ok: scrape 30",          [{"parameter": "parameter:scrape_interval_s", "to": 30}], True, 0),
    ("ok but relaxes SLO",     [{"parameter": "parameter:freshness_slo_s", "to": 60}], True, 1),
    ("SLO above bounds",       [{"parameter": "parameter:freshness_slo_s", "to": 500}], False, 0),
    ("scrape below min",       [{"parameter": "parameter:scrape_interval_s", "to": 1}], False, 0),
    ("bad enum",               [{"parameter": "parameter:log_level", "to": "TRACE"}], False, 0),
    ("ok enum",                [{"parameter": "parameter:log_level", "to": "DEBUG"}], True, 0),
    ("unknown parameter",      [{"parameter": "parameter:nominal_freshness_slo", "to": 99}], False, 0),
    ("unknown capability",     [{"capability": "capability:made_up"}], False, 0),
    ("non-numeric",            [{"parameter": "parameter:max_pod_count", "to": "many"}], False, 0),
    ("empty plan",             [], False, 0),
]
bad = 0
for name, acts, ok, nflags in cases:
    r = validate_plan(acts, cat, df)
    good = r["ok"] == ok and len(r["flags"]) == nflags
    bad += not good
    print(("PASS " if good else "FAIL "), name, "->", r["ok"], r["violations"] or r["flags"])
sys.exit(1 if bad else 0)
