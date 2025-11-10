# Sentinel Node Agent

Lightweight Go agent for node-level metrics and actions.

## Responsibilities

- Collect system metrics (CPU, memory, disk, network)
- GPU metrics via NVIDIA NVML (utilization, temperature, PCIe)
- Workload-specific metrics (inference latency, queue depth)
- Expose Prometheus `/metrics` endpoint
- Execute scoped actions (drain, restart, diagnostics)

## Metrics

Exposed at `:9100/metrics`:

```promql
sentinel_node_cpu_percent{node="node-01"}
sentinel_node_memory_bytes{node="node-01",type="used|available"}
sentinel_node_gpu_utilization_percent{node="node-01",gpu="0",sku="L4"}
sentinel_node_gpu_temperature_celsius{node="node-01",gpu="0"}
sentinel_workload_inference_latency_ms{workload="embeddings",quantile="0.95"}
```

## Development

```bash
cd services/agent
go mod download
go build -o bin/sentinel-agent cmd/agent/main.go
./bin/sentinel-agent --config config.yaml
```

## Configuration

```yaml
node_id: node-01
metrics_port: 9100
control_api: https://sentinel-api:8000
tls:
  cert: /etc/sentinel/tls/agent.crt
  key: /etc/sentinel/tls/agent.key
  ca: /etc/sentinel/tls/ca.crt
```

## Deployment

DaemonSet on Kubernetes:
```bash
kubectl apply -f ../../charts/sentinel-agent/templates/daemonset.yaml
```

Binary for edge nodes:
```bash
# Download from GitHub Releases
wget https://github.com/<org>/sentinel/releases/download/v1.0.0/sentinel-agent_linux_amd64
chmod +x sentinel-agent_linux_amd64
./sentinel-agent_linux_amd64 --config /etc/sentinel/config.yaml
```

## Testing

```bash
go test ./... -v -cover
```
