-- Sentinel PostgreSQL Initialization Script

-- Create MLflow database
CREATE DATABASE mlflow;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO sentinel;

-- Create extensions for main database
\c sentinel;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS sentinel;
CREATE SCHEMA IF NOT EXISTS audit;

-- Set search path
ALTER DATABASE sentinel SET search_path TO sentinel, public;

-- Grant privileges
GRANT ALL PRIVILEGES ON SCHEMA sentinel TO sentinel;
GRANT ALL PRIVILEGES ON SCHEMA audit TO sentinel;

-- Initial tables for Control API (will be managed by Alembic migrations later)

-- Workloads table
CREATE TABLE IF NOT EXISTS sentinel.workloads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('training', 'inference', 'batch')),
    image VARCHAR(512) NOT NULL,
    resources JSONB NOT NULL,
    env JSONB,
    config_ref VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_workloads_name ON sentinel.workloads(name);
CREATE INDEX idx_workloads_type ON sentinel.workloads(type);
CREATE INDEX idx_workloads_deleted_at ON sentinel.workloads(deleted_at);

-- Clusters table
CREATE TABLE IF NOT EXISTS sentinel.clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    kubeconfig_ref VARCHAR(255) NOT NULL,
    labels JSONB,
    gpu_families TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Deployments table
CREATE TABLE IF NOT EXISTS sentinel.deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workload_id UUID NOT NULL REFERENCES sentinel.workloads(id),
    cluster_id UUID NOT NULL REFERENCES sentinel.clusters(id),
    strategy VARCHAR(50) NOT NULL DEFAULT 'rolling',
    replicas INT NOT NULL DEFAULT 1,
    canary_config JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_deployments_workload_id ON sentinel.deployments(workload_id);
CREATE INDEX idx_deployments_cluster_id ON sentinel.deployments(cluster_id);
CREATE INDEX idx_deployments_status ON sentinel.deployments(status);

-- Policies table
CREATE TABLE IF NOT EXISTS sentinel.policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    rules JSONB NOT NULL,
    priority INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_policies_enabled ON sentinel.policies(enabled);
CREATE INDEX idx_policies_priority ON sentinel.policies(priority DESC);

-- Action Plans table
CREATE TABLE IF NOT EXISTS sentinel.action_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decisions JSONB NOT NULL,
    source VARCHAR(50) NOT NULL,
    correlation_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_action_plans_source ON sentinel.action_plans(source);
CREATE INDEX idx_action_plans_status ON sentinel.action_plans(status);
CREATE INDEX idx_action_plans_correlation_id ON sentinel.action_plans(correlation_id);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit.logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    actor VARCHAR(255) NOT NULL,
    verb VARCHAR(100) NOT NULL,
    target JSONB NOT NULL,
    result VARCHAR(50) NOT NULL,
    reason TEXT,
    metadata JSONB
);

CREATE INDEX idx_audit_logs_timestamp ON audit.logs(timestamp DESC);
CREATE INDEX idx_audit_logs_actor ON audit.logs(actor);
CREATE INDEX idx_audit_logs_verb ON audit.logs(verb);

-- Create update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add update triggers
CREATE TRIGGER update_workloads_updated_at BEFORE UPDATE ON sentinel.workloads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clusters_updated_at BEFORE UPDATE ON sentinel.clusters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_deployments_updated_at BEFORE UPDATE ON sentinel.deployments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_policies_updated_at BEFORE UPDATE ON sentinel.policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for development
INSERT INTO sentinel.clusters (name, kubeconfig_ref, labels, gpu_families)
VALUES
    ('local-dev', '/etc/sentinel/kubeconfig/local.yaml', '{"env": "dev", "region": "local"}', ARRAY['CPU', 'L4']),
    ('staging', '/etc/sentinel/kubeconfig/staging.yaml', '{"env": "staging", "region": "us-west-2"}', ARRAY['T4', 'L4'])
ON CONFLICT (name) DO NOTHING;

-- Sample policy
INSERT INTO sentinel.policies (name, rules, priority, enabled)
VALUES (
    'default-limits',
    '[
        {"type": "cost_ceiling", "constraint": {"max_usd_per_hour": 100}},
        {"type": "rate_limit", "constraint": {"max_actions_per_5min": 50}},
        {"type": "sla", "constraint": {"min_success_rate": 0.95}}
    ]'::jsonb,
    100,
    true
)
ON CONFLICT (name) DO NOTHING;

COMMENT ON DATABASE sentinel IS 'Sentinel autonomous infrastructure management platform';
COMMENT ON TABLE sentinel.workloads IS 'Workload definitions (training, inference, batch jobs)';
COMMENT ON TABLE sentinel.deployments IS 'Deployment instances of workloads on clusters';
COMMENT ON TABLE sentinel.policies IS 'Policy rules for action validation';
COMMENT ON TABLE audit.logs IS 'Immutable audit log of all actions';
