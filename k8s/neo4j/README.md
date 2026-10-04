# Neo4j on Kubernetes (central cluster)

Single-instance Neo4j 5.26 Community as a StatefulSet in namespace `observability-memory`,
with APOC and Graph Data Science plugins. Rendered and schema-checked with kustomize 5.4.3
and kubeconform 0.6.7 (Kubernetes 1.30). Not yet applied to a real cluster.

## Deploy

```bash
# 1. Label the node that will host the database (pick one the mutation experiments never touch)
kubectl label node <node-name> observability/role=memory

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
