# Sentinel Helm Charts

This directory contains Helm charts for deploying Sentinel components to Kubernetes.

## Available Charts

### sentinel-core

Deploys the Sentinel control plane services:
- **Control API** - REST API for managing workloads, deployments, and policies
- **Pipeline Controller** - Orchestrates workload lifecycle and reconciliation
- **InfraMind Adapter** - gRPC bridge to InfraMind predictive engine

**Installation:**
```bash
helm install sentinel charts/sentinel-core \
  --namespace sentinel-system \
  --create-namespace \
  --values custom-values.yaml
```

**Configuration:**
See [sentinel-core/values.yaml](sentinel-core/values.yaml) for all available options.

### sentinel-agent

Deploys the Sentinel node agent as a DaemonSet on all nodes:
- Collects system metrics (CPU, memory, disk, network)
- Collects GPU metrics via NVIDIA NVML
- Exposes Prometheus metrics endpoint
- Executes scoped node actions

**Installation:**
```bash
helm install sentinel-agent charts/sentinel-agent \
  --namespace sentinel-system
```

**Configuration:**
See [sentinel-agent/values.yaml](sentinel-agent/values.yaml) for all available options.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.x
- For GPU monitoring: NVIDIA GPU Operator or device plugin

## Quick Start

```bash
# Install both core and agent
helm install sentinel charts/sentinel-core \
  --namespace sentinel-system \
  --create-namespace

helm install sentinel-agent charts/sentinel-agent \
  --namespace sentinel-system

# Verify installation
kubectl get pods -n sentinel-system
kubectl get svc -n sentinel-system

# Access Control API (port-forward)
kubectl port-forward -n sentinel-system svc/sentinel-control-api 8000:8000
# Then visit: http://localhost:8000/docs
```

## Configuration Examples

### Custom Resource Limits

```yaml
# custom-values.yaml
controlApi:
  resources:
    limits:
      cpu: 2000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 1Gi
```

### Enable Autoscaling

```yaml
controlApi:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
```

### GPU Nodes Only

```yaml
# For agent chart
nodeSelector:
  nvidia.com/gpu: "true"
```

## Uninstalling

```bash
helm uninstall sentinel-agent -n sentinel-system
helm uninstall sentinel -n sentinel-system
kubectl delete namespace sentinel-system
```

## Development

### Linting

```bash
helm lint charts/sentinel-core
helm lint charts/sentinel-agent
```

### Template Testing

```bash
helm template sentinel charts/sentinel-core \
  --namespace sentinel-system \
  --debug
```

### Packaging

```bash
helm package charts/sentinel-core --version 0.1.0
helm package charts/sentinel-agent --version 0.1.0
```

## Support

For issues and questions:
- [GitHub Issues](../../../issues)
- [Documentation](../docs/README.md)
- [Architecture Guide](../docs/architecture/README.md)
