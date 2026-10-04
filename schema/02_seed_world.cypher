// =============================================================================
// Seed: the v1 LORCA topology expressed in the v2 world model.
// Source: v1 configuration_agent/neo4j_setup.cypher (names, IPs, exporters).
// Differences from v1:
//   * Service -> Microservice, Cluster and Node become nodes
//   * placement edges carry valid_from / valid_to (null = still valid)
//   * Config -> ConfigVersion (versioned, SUPERSEDES chain)
//   * SLOs live on Dataflow nodes, not on the Operator config
//   * every node has a unique id "<kind>:<name>" and an Entity label with a
//     POLE+O type, so neo4j-agent-memory can link reasoning steps to it
// No SENDS_TO (call-graph) edges are seeded: v1 does not record them.
// =============================================================================

// Application
MERGE (app:Application:Entity {id: "application:LORCA"})
  SET app.name = "LORCA", app.type = "OBJECT";

// Clusters and nodes (node ids are the IPs recorded in v1)
UNWIND [
  {c: "alex_k8s_cluster", n: "147.102.13.108"},
  {c: "greg_k8s_cluster", n: "147.102.7.110"}
] AS row
MERGE (cl:Cluster:Entity {id: "cluster:" + row.c})
  SET cl.name = row.c, cl.type = "LOCATION"
MERGE (nd:Node:Entity {id: "node:" + row.n})
  SET nd.name = row.n, nd.ip = row.n, nd.type = "LOCATION"
MERGE (cl)-[:CONSISTS_OF]->(nd);

// Microservices: placement is a temporal edge
UNWIND [
  {s: "object-detector", c: "greg_k8s_cluster", n: "147.102.7.110"},
  {s: "frame-resizer",   c: "alex_k8s_cluster", n: "147.102.13.108"},
  {s: "frame-sampler",   c: "alex_k8s_cluster", n: "147.102.13.108"}
] AS row
MERGE (ms:Microservice:Entity {id: "microservice:" + row.s})
  SET ms.name = row.s, ms.type = "OBJECT"
WITH ms, row
MATCH (app:Application {id: "application:LORCA"})
MATCH (cl:Cluster {id: "cluster:" + row.c})
MATCH (nd:Node {id: "node:" + row.n})
MERGE (app)-[:CONTAINS]->(ms)
MERGE (ms)-[d:DEPLOYED_IN]->(cl)
  ON CREATE SET d.valid_from = datetime("2026-01-01T00:00:00Z"), d.valid_to = null
MERGE (ms)-[r:RUNS_ON]->(nd)
  ON CREATE SET r.valid_from = datetime("2026-01-01T00:00:00Z"), r.valid_to = null;

// IoT device (inside the application, outside any cluster)
MERGE (dev:Device:Entity {id: "device:robotic-arm"})
  SET dev.name = "robotic-arm", dev.ip = "147.102.13.109", dev.kind = "iot", dev.type = "OBJECT"
WITH dev
MATCH (app:Application {id: "application:LORCA"})
MERGE (app)-[:CONTAINS]->(dev);

// Operators: two local, one central
UNWIND [
  {c: "alex_k8s_cluster", role: "local",   n: "147.102.13.108"},
  {c: "greg_k8s_cluster", role: "local",   n: "147.102.7.110"},
  {c: "central",          role: "central", n: "147.102.7.110"}
] AS row
MERGE (op:Operator:Entity {id: "operator:" + row.c})
  SET op.name = row.c, op.role = row.role, op.type = "OBJECT"
WITH op, row
MATCH (nd:Node {id: "node:" + row.n})
MERGE (op)-[r:RUNS_ON]->(nd)
  ON CREATE SET r.valid_from = datetime("2026-01-01T00:00:00Z"), r.valid_to = null;

// Observation edges (service -> its local operator) and forwarding path
MATCH (s:Microservice {id: "microservice:object-detector"}), (o:Operator {id: "operator:greg_k8s_cluster"})
MERGE (s)-[x:OBSERVED_BY]->(o) ON CREATE SET x.valid_from = datetime("2026-01-01T00:00:00Z"), x.valid_to = null;
MATCH (s:Microservice), (o:Operator {id: "operator:alex_k8s_cluster"})
WHERE s.name IN ["frame-resizer", "frame-sampler"]
MERGE (s)-[x:OBSERVED_BY]->(o) ON CREATE SET x.valid_from = datetime("2026-01-01T00:00:00Z"), x.valid_to = null;

MATCH (l:Operator {role: "local"}), (c:Operator {id: "operator:central"})
MERGE (l)-[:FORWARDS_TO]->(c);

// Dataflows: one per local operator -> central. SLO values are the v1 "balanced"
// level defaults (freshness 30 s, drop ratio 0.02), the v1 reset baseline.
MATCH (l:Operator {role: "local"}), (c:Operator {id: "operator:central"})
MERGE (df:Dataflow:Entity {id: "dataflow:" + l.name + "->central:telemetry"})
  SET df.name = l.name + " to central (telemetry)", df.signal = "telemetry",
      df.freshness_slo = 30.0, df.drop_ratio_slo = 0.02, df.type = "OBJECT"
MERGE (df)-[:FROM]->(l)
MERGE (df)-[:TO]->(c);

// Initial configuration versions (v1 seed values)
UNWIND [
  {c: "alex_k8s_cluster", ex: ["node_level_resources", "application_logs"]},
  {c: "greg_k8s_cluster", ex: ["node_level_resources"]}
] AS row
MATCH (op:Operator {id: "operator:" + row.c})
MERGE (cv:ConfigVersion:Entity {id: "configversion:" + row.c + ":0"})
  SET cv.name = row.c + " config v0", cv.exporters = row.ex, cv.scrape_interval_s = 15,
      cv.version = 0, cv.valid_from = datetime("2026-01-01T00:00:00Z"), cv.valid_to = null,
      cv.type = "OBJECT"
MERGE (op)-[:HAS_CONFIGURATION]->(cv);
