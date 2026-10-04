# Neo4j on Kubernetes (central cluster)

Single-instance Neo4j 5.26 Community as a StatefulSet in namespace `observability-memory`,
with APOC and Graph Data Science plugins. Rendered and schema-checked with kustomize 5.4.3
and kubeconform 0.6.7 (Kubernetes 1.30). Not yet applied to a real cluster.

## Deploy

```bash
# 1. (Multi-node clusters only) pin the database to a node the mutation experiments never touch:
#    label the node, then uncomment the nodeSelector in statefulset.yaml. A single-node
#    cluster needs nothing here.

# 2. Create the password file (git-ignored)
cd k8s/neo4j
cp neo4j-auth.env.example neo4j-auth.env      # then edit: NEO4J_AUTH=neo4j/<your password>

# 3. Apply
kubectl apply -k .
kubectl -n observability-memory rollout status statefulset/neo4j --timeout=10m

# 4. Reach it from your machine, then load the schema
kubectl -n observability-memory port-forward svc/neo4j 7687:7687 7474:7474 &
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=<your password>
python scripts/apply_schema.py && python scripts/seed_capabilities.py
```

In-cluster clients use `bolt://neo4j.observability-memory.svc.cluster.local:7687`.

## Things to know

* Community edition: one replica, one user database, no clustering or online backup.
  A reproducible snapshot of a trajectory dataset means stopping the pod and running
  `neo4j-admin database dump`; automating that is not done yet.
* The first start downloads the APOC and GDS plugins, so the pod needs outbound internet.
  For an air-gapped cluster, bake the jars into an image instead.
* Memory (heap 1G, page cache 512M, pod limit 3Gi) and storage (10Gi) are starting values.
* Access control is the Secret only. Add a NetworkPolicy limiting port 7687 to the agent and
  tool-server namespaces once those exist (requires a CNI that enforces policies).
* The StatefulSet's PVC uses the cluster's default StorageClass.
* Single-node cluster: the database shares the node with everything else on the central
  cluster, so (a) check `kubectl describe node` for allocatable memory before applying (the pod
  requests 2Gi), (b) the data lives on that one node's disk, so keep an off-node copy of any
  dataset you cite, and (c) when injecting link latency with `tc netem`, filter by destination or
  apply it on the data-plane side, so Neo4j's own traffic is not delayed.
