// =============================================================================
// agentic-observability v2 -- schema: constraints and indexes (idempotent)
// Draft v0. Layers: world, temporal state, dataflow, capability, intent,
// trajectory. Agent-memory labels (Conversation, Message, ReasoningTrace,
// ReasoningStep, ToolCall, Entity, ...) are created by neo4j-agent-memory.
//
// ID convention: every domain node has a globally unique string `id` of the
// form "<kind>:<name>" so it can also carry the library's :Entity label.
// =============================================================================

// -- World ---------------------------------------------------------------------
CREATE CONSTRAINT application_id   IF NOT EXISTS FOR (n:Application)  REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT microservice_id  IF NOT EXISTS FOR (n:Microservice) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT device_id        IF NOT EXISTS FOR (n:Device)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT cluster_id       IF NOT EXISTS FOR (n:Cluster)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT node_id          IF NOT EXISTS FOR (n:Node)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT operator_id      IF NOT EXISTS FOR (n:Operator)     REQUIRE n.id IS UNIQUE;

// -- Temporal state ------------------------------------------------------------
CREATE CONSTRAINT configversion_id IF NOT EXISTS FOR (n:ConfigVersion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT observation_id   IF NOT EXISTS FOR (n:Observation)   REQUIRE n.id IS UNIQUE;
CREATE INDEX observation_ts        IF NOT EXISTS FOR (n:Observation)   ON (n.ts);

// -- Dataflow ------------------------------------------------------------------
CREATE CONSTRAINT dataflow_id      IF NOT EXISTS FOR (n:Dataflow)      REQUIRE n.id IS UNIQUE;

// -- Capability ----------------------------------------------------------------
CREATE CONSTRAINT capability_id    IF NOT EXISTS FOR (n:Capability)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT signal_id        IF NOT EXISTS FOR (n:Signal)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT parameter_id     IF NOT EXISTS FOR (n:Parameter)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dimension_id     IF NOT EXISTS FOR (n:ResourceDimension) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT preset_id        IF NOT EXISTS FOR (n:ConfigPreset)  REQUIRE n.id IS UNIQUE;

// -- Intent --------------------------------------------------------------------
CREATE CONSTRAINT intent_id        IF NOT EXISTS FOR (n:ObservabilityIntent) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT goal_id          IF NOT EXISTS FOR (n:Goal)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT constraint_id    IF NOT EXISTS FOR (n:Constraint)    REQUIRE n.id IS UNIQUE;

// -- Trajectory ----------------------------------------------------------------
CREATE CONSTRAINT event_id         IF NOT EXISTS FOR (n:Event)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT plan_id          IF NOT EXISTS FOR (n:Plan)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT action_id        IF NOT EXISTS FOR (n:Action)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT outcome_id       IF NOT EXISTS FOR (n:Outcome)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT artifact_id      IF NOT EXISTS FOR (n:Artifact)      REQUIRE n.id IS UNIQUE;
