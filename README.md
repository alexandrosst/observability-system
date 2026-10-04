# agentic-observability-2

v2 of the observability control plane: a temporal context graph in Neo4j
(world, capabilities, intents, trajectories) plus agent memory from
`neo4j-agent-memory`. Design notes live in the "Context-Graph Control Plane (v2)"
doc. Status: draft v0, schema and a library prototype only (no agent yet).

## Layout

| Path | Purpose |
| --- | --- |
| `schema/01_constraints.cypher` | Uniqueness constraints and indexes for all domain labels |
| `schema/02_seed_world.cypher` | The v1 LORCA topology in the v2 model (temporal edges, Dataflow, ConfigVersion) |
| `seed/*.yaml` | Copies of the v1 coverage and tuning level files, used only to seed Capability and ConfigPreset nodes |
| `scripts/apply_schema.py` | Applies `schema/*.cypher` in order |
| `scripts/seed_capabilities.py` | Seeds Capability, Signal, Parameter, ResourceDimension, ConfigPreset from `seed/` |
| `k8s/neo4j/` | Kustomize manifests for Neo4j 5.26 Community with APOC and GDS (see its README) |
| `prototype/proto_memory.py` | Checks `neo4j-agent-memory` against this schema (see findings) |

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # then set NEO4J_PASSWORD (the same one as in k8s/neo4j/neo4j-auth.env)
python scripts/apply_schema.py
python scripts/seed_capabilities.py
python prototype/proto_memory.py
```

Needs Neo4j 5.20+ (vector indexes) and Python 3.10+.

## Conventions

* Every domain node has a unique string `id` of the form `<kind>:<name>`.
* World nodes also carry the library's `:Entity` label and a POLE+O `type`
  (OBJECT, LOCATION, EVENT) so reasoning steps can `TOUCH` them.
* Placement edges (`DEPLOYED_IN`, `RUNS_ON`, `OBSERVED_BY`) carry `valid_from` and
  `valid_to` (null = still valid). A migration closes one edge and opens another.
* SLOs belong to `Dataflow` nodes. v1's two SLO vocabularies are not carried over.
* `AFFECTS` edges seeded here are qualitative priors only, to be replaced by effects
  learned from trajectories.

## Prototype findings (neo4j-agent-memory 0.6.0, Neo4j 5.26, offline hash embedder)

1. `ReasoningStep -[:TOUCHED]-> ` works on our nodes when they carry `:Entity` and a
   unique `id`; no duplicate Entity nodes were created.
2. A `ReasoningTrace` joins our `Plan` and `Outcome` nodes with plain edges.
3. `get_similar_traces` ranks by task-text similarity only. A trace about a link-latency
   problem ranked second for a migration query because both mention "freshness SLO
   violated". Structure-blind retrieval is the gap to fill.

## Known gaps

* No `SENDS_TO` (call-graph) edges: v1 does not record them.
* Node ids are the IPs recorded in v1; central operator shares the greg node as in v1.
* Dataflow SLO values (30 s, 0.02) are the v1 "balanced" defaults, not measured targets.
* The prototype uses a hashing embedder, so similarity numbers are not semantic.
