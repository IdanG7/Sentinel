# Sentinel Architecture

This document describes the architecture of the Sentinel autonomous AI infrastructure platform.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Security Architecture](#security-architecture)
- [Deployment Architecture](#deployment-architecture)

## System Overview

Sentinel is an autonomous infrastructure controller that integrates with InfraMind (the predictive brain) to form a closed feedback loop for managing AI/ML workloads.

```mermaid
graph TB
    subgraph "InfraMind (Brain)"
        TI[Telemetry Ingestor]
        PM[Predictive Models]
        OE[Optimization Engine]
        DA[Decision API]

        TI --> PM
        PM --> OE
        OE --> DA
    end

    subgraph "Sentinel (Executor/Observer)"
        API[Control API]
        POL[Policy Engine]
        PC[Pipeline Controller]
        K8S[Kubernetes Driver]
        AGT[Node Agents]

        API --> POL
        API --> PC
        PC --> K8S
        K8S --> AGT
    end

    subgraph "Observability"
        PROM[Prometheus]
        GRAF[Grafana]
        KAFKA[Kafka]

        AGT --> PROM
        AGT --> KAFKA
        PROM --> GRAF
    end

    AGT -.metrics.-> TI
    KAFKA -.events.-> TI
    DA -.action plans.-> API

    style InfraMind fill:#e1f5ff
    style Sentinel fill:#fff4e1
    style Observability fill:#f0f0f0
```

## Component Architecture

### Control API

The Control API is the primary interface for managing Sentinel operations.

```mermaid
graph LR
    subgraph "Control API"
        AUTH[Authentication Layer]
        ROUTES[API Routes]
        VAL[Validators]
        DB[(PostgreSQL)]

        AUTH --> ROUTES
        ROUTES --> VAL
        VAL --> DB
    end

    CLIENT[API Clients] --> AUTH
    ROUTES --> KAFKA[Kafka Events]
    ROUTES --> METRICS[Prometheus Metrics]

    style AUTH fill:#ffe1e1
    style ROUTES fill:#e1ffe1
    style DB fill:#e1e1ff
```

**Key Responsibilities:**
- JWT-based authentication and authorization
- RESTful API for workloads, deployments, policies
- Action plan submission and validation
- Audit logging

### Pipeline Controller

The Pipeline Controller executes deployment operations and manages workload lifecycle.

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Validating: Receive Action Plan
    Validating --> Approved: Policy Check Pass
    Validating --> Rejected: Policy Violation
    Approved --> Executing: Apply Changes
    Executing --> Completed: Success
    Executing --> Failed: Error
    Executing --> RollingBack: Health Check Fail
    RollingBack --> RolledBack
    Completed --> [*]
    Failed --> [*]
    Rejected --> [*]
    RolledBack --> [*]
```

**Key Features:**
- Idempotent reconciliation loop
- Multiple rollout strategies (rolling, canary, blue/green)
- Automatic rollback on health check failures
- Integration with Kubernetes API

### Node Agent

The Node Agent collects metrics and executes scoped actions on individual nodes.

```mermaid
graph TB
    AGENT[Node Agent]

    subgraph "Collectors"
        CPU[CPU Collector]
        MEM[Memory Collector]
        DISK[Disk Collector]
        NET[Network Collector]
        GPU[GPU Collector NVML]
    end

    subgraph "Outputs"
        PROM[Prometheus Exporter]
        LOGS[Structured Logs]
    end

    AGENT --> CPU
    AGENT --> MEM
    AGENT --> DISK
    AGENT --> NET
    AGENT --> GPU

    CPU --> PROM
    MEM --> PROM
    DISK --> PROM
    NET --> PROM
    GPU --> PROM

    AGENT --> LOGS

    style GPU fill:#90EE90
```

## Data Flow

### Telemetry Collection Flow

```mermaid
sequenceDiagram
    participant Agent as Node Agent
    participant Prom as Prometheus
    participant Kafka
    participant Adapter as InfraMind Adapter
    participant IM as InfraMind

    loop Every 5s
        Agent->>Agent: Collect Metrics
        Agent->>Prom: Expose /metrics
    end

    loop Every 15s
        Prom->>Agent: Scrape Metrics
    end

    Agent->>Kafka: Publish Events

    loop Every 30s
        Adapter->>Prom: Query Metrics
        Adapter->>Kafka: Consume Events
        Adapter->>IM: Send Telemetry Batch
    end
```

### Action Plan Execution Flow

```mermaid
sequenceDiagram
    participant IM as InfraMind
    participant API as Control API
    participant Policy as Policy Engine
    participant Pipeline as Pipeline Controller
    participant K8s as Kubernetes
    participant Agent as Node Agent

    IM->>API: Submit Action Plan
    API->>Policy: Validate Plan

    alt Policy Approved
        Policy->>API: Approved
        API->>Pipeline: Execute Plan
        Pipeline->>K8s: Apply Changes
        K8s->>Agent: Deploy/Scale
        Agent->>Pipeline: Health Status
        Pipeline->>API: Execution Result
        API->>IM: Acknowledge
    else Policy Violated
        Policy->>API: Rejected
        API->>IM: Rejection Reason
    end
```

### Deployment Lifecycle

```mermaid
graph TD
    START[User Submits Deployment] --> VALIDATE{Policy Check}
    VALIDATE -->|Pass| QUEUE[Queue for Execution]
    VALIDATE -->|Fail| REJECT[Reject]

    QUEUE --> CREATE[Create K8s Resources]
    CREATE --> STRATEGY{Deployment Strategy}

    STRATEGY -->|Rolling| ROLLING[Rolling Update]
    STRATEGY -->|Canary| CANARY[Canary Deployment]
    STRATEGY -->|Blue/Green| BLUEGREEN[Blue/Green Switch]

    ROLLING --> HEALTH1{Health Check}
    CANARY --> HEALTH2{Health Check}
    BLUEGREEN --> HEALTH3{Health Check}

    HEALTH1 -->|Pass| SUCCESS[Completed]
    HEALTH1 -->|Fail| ROLLBACK1[Rollback]
    HEALTH2 -->|Pass| PROMOTE[Promote Canary]
    HEALTH2 -->|Fail| ROLLBACK2[Rollback]
    HEALTH3 -->|Pass| SUCCESS
    HEALTH3 -->|Fail| ROLLBACK3[Rollback]

    PROMOTE --> SUCCESS
    ROLLBACK1 --> FAILED[Deployment Failed]
    ROLLBACK2 --> FAILED
    ROLLBACK3 --> FAILED

    style SUCCESS fill:#90EE90
    style FAILED fill:#FFB6C1
    style REJECT fill:#FFB6C1
```

## Security Architecture

```mermaid
graph TB
    subgraph "Authentication & Authorization"
        JWT[JWT Tokens]
        RBAC[Role-Based Access Control]
        MTLS[mTLS Between Services]
    end

    subgraph "Secrets Management"
        VAULT[HashiCorp Vault]
        K8SSEC[Kubernetes Secrets]
    end

    subgraph "Supply Chain Security"
        COSIGN[Cosign Image Signing]
        SBOM[SBOM Generation]
        SCAN[Vulnerability Scanning]
    end

    subgraph "Network Security"
        NETPOL[Network Policies]
        INGRESS[Ingress TLS]
    end

    API[Control API] --> JWT
    API --> RBAC
    PC[Pipeline Controller] --> MTLS
    AGENT[Node Agent] --> MTLS

    API --> VAULT
    PC --> VAULT

    CI[CI/CD Pipeline] --> COSIGN
    CI --> SBOM
    CI --> SCAN

    style JWT fill:#ffe1e1
    style VAULT fill:#e1ffe1
    style COSIGN fill:#e1e1ff
```

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant API as Control API
    participant Vault as HashiCorp Vault
    participant K8s as Kubernetes

    User->>API: POST /api/v1/auth/login (username, password)
    API->>API: Verify Credentials
    API->>API: Generate JWT (access + refresh)
    API->>User: Return Tokens

    User->>API: Request with Bearer Token
    API->>API: Validate JWT
    API->>API: Check RBAC Permissions

    alt Authorized
        API->>K8s: Execute Operation
        K8s->>API: Result
        API->>User: Success Response
    else Unauthorized
        API->>User: 401/403 Error
    end
```

## Deployment Architecture

### Kubernetes Deployment

```mermaid
graph TB
    subgraph "sentinel-system Namespace"
        subgraph "Control Plane"
            API1[Control API Pod 1]
            API2[Control API Pod 2]
            PC1[Pipeline Controller 1]
            PC2[Pipeline Controller 2]
            IA[InfraMind Adapter]
        end

        SVC[Service]
        ING[Ingress]

        ING --> SVC
        SVC --> API1
        SVC --> API2
    end

    subgraph "kube-system"
        AGENT1[Agent DaemonSet Node 1]
        AGENT2[Agent DaemonSet Node 2]
        AGENT3[Agent DaemonSet Node 3]
    end

    subgraph "observability Namespace"
        PROM[Prometheus]
        GRAF[Grafana]
        KAFKA[Kafka]
    end

    AGENT1 --> PROM
    AGENT2 --> PROM
    AGENT3 --> PROM

    PC1 --> AGENT1
    PC2 --> AGENT2

    IA --> PROM
    IA --> KAFKA

    style API1 fill:#e1f5ff
    style API2 fill:#e1f5ff
    style PC1 fill:#fff4e1
    style PC2 fill:#fff4e1
```

### Multi-Cluster Architecture

```mermaid
graph TB
    subgraph "Management Cluster"
        API[Control API]
        PC[Pipeline Controller]
        IA[InfraMind Adapter]
    end

    subgraph "Production Cluster 1 (us-west-2)"
        AGT1[Node Agents]
        WL1[AI/ML Workloads]
    end

    subgraph "Production Cluster 2 (eu-west-1)"
        AGT2[Node Agents]
        WL2[AI/ML Workloads]
    end

    subgraph "Edge Cluster (on-prem)"
        AGT3[Node Agents]
        WL3[Inference Workloads]
    end

    subgraph "InfraMind (SaaS/Self-Hosted)"
        IM[Predictive Engine]
    end

    PC -->|kubeconfig 1| AGT1
    PC -->|kubeconfig 2| AGT2
    PC -->|kubeconfig 3| AGT3

    AGT1 -.telemetry.-> IA
    AGT2 -.telemetry.-> IA
    AGT3 -.telemetry.-> IA

    IA -.metrics + events.-> IM
    IM -.action plans.-> API

    style IM fill:#e1f5ff
```

## Technology Stack

```mermaid
graph LR
    subgraph "Languages"
        PYTHON[Python 3.11+]
        GO[Go 1.21+]
    end

    subgraph "Frameworks"
        FASTAPI[FastAPI]
        COBRA[Cobra CLI]
    end

    subgraph "Data Stores"
        POSTGRES[PostgreSQL]
        KAFKA[Apache Kafka]
    end

    subgraph "Orchestration"
        K8S[Kubernetes]
        HELM[Helm]
    end

    subgraph "Observability"
        PROM[Prometheus]
        GRAF[Grafana]
        JAEGER[Jaeger]
        MLFLOW[MLflow]
    end

    subgraph "Security"
        VAULT[HashiCorp Vault]
        COSIGN[Sigstore Cosign]
    end

    PYTHON --> FASTAPI
    GO --> COBRA

    FASTAPI --> POSTGRES
    FASTAPI --> KAFKA

    COBRA --> PROM

    style PYTHON fill:#3776ab,color:#fff
    style GO fill:#00ADD8,color:#fff
    style K8S fill:#326CE5,color:#fff
```

## Next Steps

- [API Reference](../api/openapi.yaml)
- [Development Guide](../guides/development.md)
- [Operator Runbook](../runbooks/operator-guide.md)
- [Security Model](../security.md)
