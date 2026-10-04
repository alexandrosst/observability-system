"""Apply schema/*.cypher in order. Usage: python scripts/apply_schema.py"""
from common import ROOT, driver, run_file

if __name__ == "__main__":
    drv = driver()
    for f in sorted((ROOT / "schema").glob("*.cypher")):
        print(f"{f.name}: {run_file(drv, f)} statements")
    drv.close()
