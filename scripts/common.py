"""Shared helpers: Neo4j driver and Cypher file runner."""
import os, re
from pathlib import Path
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """Read KEY=VALUE lines from <project>/.env into the environment (real env vars win)."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")
if not PASSWORD:
    raise SystemExit("NEO4J_PASSWORD is not set. Copy .env.example to .env and fill it in, "
                     "or export the variable.")


def driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def split_statements(text: str):
    """Split a .cypher file on ';' at end of line, dropping // comment lines."""
    lines = [l for l in text.splitlines() if not l.strip().startswith("//")]
    stmts = [s.strip() for s in re.split(r";\s*(?:\n|$)", "\n".join(lines))]
    return [s for s in stmts if s]


def run_file(drv, path: Path):
    n = 0
    with drv.session() as s:
        for stmt in split_statements(path.read_text()):
            s.run(stmt).consume()
            n += 1
    return n
