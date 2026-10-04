"""Prototype: does neo4j-agent-memory v0.6.0 work against our v2 world graph?

Questions answered (printed at the end):
  Q1. Can a ReasoningStep TOUCH our domain nodes (they carry the :Entity label)?
  Q2. Can we join a ReasoningTrace to our Plan / Outcome with a plain edge?
  Q3. What does get_similar_traces return with a deterministic offline embedder?
Run after scripts/apply_schema.py. Uses an offline hashing embedder (no API key).
"""
import asyncio, hashlib, math, re, sys, uuid
from pathlib import Path
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from common import URI, USER, PASSWORD, driver  # noqa: E402

from neo4j_agent_memory import MemoryClient, MemorySettings, Neo4jConfig  # noqa: E402
from neo4j_agent_memory.config.settings import EmbeddingConfig, EmbeddingProvider  # noqa: E402
from neo4j_agent_memory.schema.models import EntityRef  # noqa: E402

DIM = 128


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder (offline stand-in)."""
    dimensions = DIM

    async def embed(self, text: str) -> list[float]:
        v = [0.0] * DIM
        for tok in re.findall(r"[a-z0-9_]+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % DIM] += 1.0 if (h >> 8) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    async def embed_batch(self, texts):
        return [await self.embed(t) for t in texts]


async def main():
    settings = MemorySettings(
        neo4j=Neo4jConfig(uri=URI, username=USER, password=SecretStr(PASSWORD)),
        embedding=EmbeddingConfig(provider=EmbeddingProvider.CUSTOM, model="hash", dimensions=DIM),
    )
    async with MemoryClient(settings, embedder=HashEmbedder()) as mem:
        session = f"proto-{uuid.uuid4().hex[:8]}"

        async def run(task, entity_id, tool, args, ok):
            tr = await mem.reasoning.start_trace(session_id=session, task=task)
            st = await mem.reasoning.add_step(
                tr.id, thought=f"Plan for: {task}", action=tool)
            await mem.reasoning.record_tool_call(
                st.id, tool, args, result="ok" if ok else "violation persists",
                touched_entities=[EntityRef(id=entity_id)])
            await mem.reasoning.complete_trace(tr.id, outcome="slo_met" if ok else "slo_missed",
                                               success=ok)
            return tr.id

        t1 = await run("freshness SLO violated after migrating object-detector to greg cluster",
                       "microservice:object-detector", "set_parameter",
                       {"parameter": "scrape_interval_s", "value": 10}, True)
        t2 = await run("energy budget exceeded on alex cluster operator",
                       "operator:alex_k8s_cluster", "disable_capability",
                       {"capability": "energy_metrics"}, True)
        t3 = await run("freshness SLO violated after link latency increase local to central",
                       "dataflow:greg_k8s_cluster->central:telemetry", "set_parameter",
                       {"parameter": "scrape_interval_s", "value": 20}, False)

        # Q2: join a trace to our own Plan / Outcome nodes with plain Cypher
        drv = driver()
        with drv.session() as s:
            s.run("""MATCH (rt:ReasoningTrace {id:$t})
                     MERGE (p:Plan {id:$p}) SET p.status='completed'
                     MERGE (o:Outcome {id:$o}) SET o.slo_met=true
                     MERGE (rt)-[:PRODUCED]->(p)-[:RESULTED_IN]->(o)""",
                  t=str(t1), p=f"plan:{uuid.uuid4().hex[:8]}", o=f"outcome:{uuid.uuid4().hex[:8]}")
            touched = s.run("""MATCH (:ReasoningStep)-[:TOUCHED]->(e)
                               RETURN labels(e) AS labels, e.id AS id ORDER BY id""").data()
            n_entities = s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
            joined = s.run("""MATCH (rt:ReasoningTrace)-[:PRODUCED]->(p:Plan)-[:RESULTED_IN]->(o:Outcome)
                              RETURN rt.task AS task, o.slo_met AS slo_met""").data()
            paths = s.run("""MATCH (rt:ReasoningTrace)-[:HAS_STEP]->(:ReasoningStep)-[:TOUCHED]->(e)
                             RETURN rt.task AS task, e.id AS touched, rt.success AS success
                             ORDER BY task""").data()
        drv.close()

        print("Q1 TOUCHED targets:")
        for t in touched:
            print("  ", t["id"], t["labels"])
        print("Entity nodes in graph (should still be 16, no duplicates created):", n_entities)
        print("Q2 trace -> Plan -> Outcome join:", joined)
        print("Trace -> touched entity paths:")
        for p in paths:
            print("  ", p["success"], "|", p["task"], "->", p["touched"])

        q = "freshness SLO violated after migrating a microservice to another cluster"
        sims = await mem.reasoning.get_similar_traces(q, limit=5, success_only=False, threshold=0.0)
        print("Q3 get_similar_traces for:", q)
        for t in sims:
            print("  ", t.success, "|", t.task)


asyncio.run(main())
