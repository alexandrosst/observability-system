"""Shared helpers: Neo4j driver and Cypher file runner."""
import os, re
from pathlib import Path
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword123")


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
