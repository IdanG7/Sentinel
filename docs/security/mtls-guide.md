# mTLS Implementation Guide

## Overview

Sentinel uses **mutual TLS (mTLS)** for all inter-service communication to ensure:
- **Encryption** of data in transit
- **Authentication** of both client and server
- **Authorization** based on certificate identity
- **Automatic certificate rotation** with zero downtime

This guide covers setup, configuration, and troubleshooting of mTLS in Sentinel.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    cert-manager                              │
│  ┌──────────────┐       ┌──────────────┐                   │
│  │ Self-Signed  │──────▶│ Sentinel CA  │                   │
│  │   Issuer     │       │ (Root Cert)  │                   │
│  └──────────────┘       └───────┬──────┘                   │
│                                  │                           │
│                         ┌────────▼────────┐                 │
│                         │  CA Issuer      │                 │
│                         │ (Signs service  │                 │
│                         │  certificates)  │                 │
│                         └────────┬────────┘                 │
└──────────────────────────────────┼──────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
    ┌────▼─────┐           ┌──────▼──────┐         ┌───────▼──────┐
    │ Control  │           │  Pipeline   │         │   InfraMind  │
    │   API    │◀─────────▶│ Controller  │◀───────▶│   Adapter    │
    │ (Server) │   mTLS    │  (Client)   │  mTLS   │   (Client)   │
    └──────────┘           └─────────────┘         └──────────────┘
```

## Components

### 1. cert-manager

**Purpose:** Automates certificate lifecycle management

**Features:**
- Issues certificates from CA
- Auto-renews before expiration (15 days default)
- Stores certificates in Kubernetes Secrets
- Monitors certificate health

**Installation:**
```bash
# Install cert-manager CRDs and operator
kubectl apply -f deploy/k8s/cert-manager.yaml

# Verify installation
kubectl get pods -n cert-manager
kubectl get clusterissuer
```

### 2. Certificate Authority (CA)

**Self-Signed CA (Development/Testing):**
- Root CA certificate valid for 10 years
- All service certificates signed by this CA
- Stored in `sentinel-ca-secret` in cert-manager namespace

**Production Options:**
- **Vault PKI:** Use HashiCorp Vault as CA (recommended)
- **Let's Encrypt:** For public-facing services
- **Enterprise CA:** Integrate with corporate PKI

### 3. Service Certificates

Each service gets a dedicated certificate:

| Service | Secret Name | Common Name | DNS Names |
|---------|-------------|-------------|-----------|
| Control API | control-api-tls | control-api.sentinel-system.svc.cluster.local | control-api, control-api.sentinel-system, ... |
| Pipeline Controller | pipeline-controller-tls | pipeline-controller.sentinel-system.svc.cluster.local | pipeline-controller, ... |
| InfraMind Adapter | infra-adapter-tls | infra-adapter.sentinel-system.svc.cluster.local | infra-adapter, ... |
| Node Agent | node-agent-tls | node-agent.sentinel-system.svc.cluster.local | node-agent, *.sentinel-system.svc.cluster.local |

**Certificate Properties:**
- **Duration:** 90 days (2160h)
- **Renewal:** 15 days before expiry (360h)
- **Algorithm:** RSA 2048
- **Usages:** server auth, client auth, digital signature, key encipherment

### 4. Python mTLS Library

**Location:** `libs/sentinel-common/sentinel_common/mtls.py`

**Classes:**
- `MTLSConfig`: Certificate paths and verification settings
- Helper functions for SSL context creation
- gRPC credentials builders

**Usage Example:**
```python
from sentinel_common.mtls import mtls_config_from_env, create_ssl_context

# Load certificates from environment/default paths
mtls_config = mtls_config_from_env()

# Create SSL context for HTTPS server
ssl_context = create_ssl_context(mtls_config, server_side=True)

# Use with uvicorn
uvicorn.run(
    app,
    ssl_keyfile=str(mtls_config.key_path),
    ssl_certfile=str(mtls_config.cert_path),
    ssl_ca_certs=str(mtls_config.ca_cert_path),
)
```

## Installation

### Step 1: Install cert-manager

```bash
# Apply cert-manager manifests
kubectl apply -f deploy/k8s/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/cert-manager -n cert-manager
```

### Step 2: Create Service Certificates

```bash
# Apply certificate requests
kubectl apply -f deploy/k8s/mtls-config.yaml

# Verify certificates are issued
kubectl get certificates -n sentinel-system
kubectl get secrets -n sentinel-system | grep tls
```

**Expected Output:**
```
NAME                  READY   SECRET                AGE
control-api-tls       True    control-api-tls       30s
pipeline-controller-tls True  pipeline-controller-tls 30s
infra-adapter-tls     True    infra-adapter-tls     30s
node-agent-tls        True    node-agent-tls        30s
```

### Step 3: Deploy Sentinel with mTLS

```bash
# Install Sentinel with Helm (mTLS enabled by default)
helm install sentinel charts/sentinel-core \
  --namespace sentinel-system \
  --create-namespace \
  --set global.mtls.enabled=true
```

### Step 4: Verify mTLS

```bash
# Check Control API logs for mTLS status
kubectl logs -n sentinel-system deployment/control-api | grep mTLS

# Expected: "mTLS: Enabled"

# Test certificate verification
kubectl exec -n sentinel-system deployment/control-api -- \
  openssl verify -CAfile /etc/sentinel/certs/ca.crt /etc/sentinel/certs/tls.crt
```

## Configuration

### Environment Variables

Each service supports these mTLS environment variables:

```bash
# Enable/disable mTLS
MTLS_ENABLED=true  # Set to "false" to disable (not recommended for production)

# Certificate paths (defaults shown)
MTLS_CERT_PATH=/etc/sentinel/certs/tls.crt
MTLS_KEY_PATH=/etc/sentinel/certs/tls.key
MTLS_CA_CERT_PATH=/etc/sentinel/certs/ca.crt
```

### Helm Values

**Enable/disable globally:**
```yaml
global:
  mtls:
    enabled: true
    issuer: sentinel-ca-issuer
    certPath: /etc/sentinel/certs
```

**Per-service configuration:**
```yaml
controlApi:
  env:
    - name: MTLS_ENABLED
      value: "true"
```

### Local Development

For local development without Kubernetes:

**Option 1: Disable mTLS**
```bash
export MTLS_ENABLED=false
python -m uvicorn app.main:app
```

**Option 2: Use Self-Signed Certificates**
```bash
# Generate self-signed certificates
mkdir -p /tmp/certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /tmp/certs/tls.key \
  -out /tmp/certs/tls.crt \
  -days 365 \
  -subj "/CN=localhost"
cp /tmp/certs/tls.crt /tmp/certs/ca.crt

# Export paths
export MTLS_ENABLED=true
export MTLS_CERT_PATH=/tmp/certs/tls.crt
export MTLS_KEY_PATH=/tmp/certs/tls.key
export MTLS_CA_CERT_PATH=/tmp/certs/ca.crt

# Run service
python -m uvicorn app.main:app
```

## Certificate Rotation

Certificates are automatically rotated by cert-manager **15 days before expiry** with zero downtime.

### How It Works

1. **cert-manager** monitors certificate expiration
2. **15 days before expiry**, requests new certificate from CA
3. **New certificate** is written to the same Kubernetes Secret
4. **Pods automatically** pick up new certificate (volume mount)
5. **Services reload** certificates on next request (Python ssl library handles this)

### Monitoring

**Prometheus Alerts:**
```yaml
- alert: CertificateExpiringSoon
  expr: certmanager_certificate_expiration_timestamp_seconds - time() < 604800
  for: 5m
  annotations:
    summary: "Certificate {{ $labels.name }} expires in <7 days"

- alert: CertificateRenewalFailed
  expr: certmanager_certificate_ready_status{condition="False"} == 1
  for: 5m
  annotations:
    summary: "Certificate {{ $labels.name }} renewal failed"
```

**Check Certificate Status:**
```bash
# List all certificates and their status
kubectl get certificates -n sentinel-system

# Describe certificate for detailed info
kubectl describe certificate control-api-tls -n sentinel-system

# Check certificate expiration
kubectl get secret control-api-tls -n sentinel-system -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -dates
```

## Troubleshooting

### Issue: Certificate Not Ready

**Symptoms:**
```bash
kubectl get certificates -n sentinel-system
# NAME              READY   SECRET            AGE
# control-api-tls   False   control-api-tls   1m
```

**Diagnosis:**
```bash
kubectl describe certificate control-api-tls -n sentinel-system
# Look for events showing errors
```

**Common Causes:**
1. **ClusterIssuer not ready:** Check `kubectl get clusterissuer sentinel-ca-issuer`
2. **CA secret missing:** Check `kubectl get secret sentinel-ca-secret -n cert-manager`
3. **RBAC issues:** Check cert-manager pod logs

**Solution:**
```bash
# Restart cert-manager if needed
kubectl rollout restart deployment/cert-manager -n cert-manager

# Manually delete and recreate certificate
kubectl delete certificate control-api-tls -n sentinel-system
kubectl apply -f deploy/k8s/mtls-config.yaml
```

### Issue: Service Fails to Start with mTLS

**Symptoms:**
```
ERROR: Failed to load mTLS certificates: FileNotFoundError
mTLS: DISABLED (not secure for production)
```

**Diagnosis:**
```bash
# Check if certificate secret exists
kubectl get secret control-api-tls -n sentinel-system

# Check if secret is mounted in pod
kubectl describe pod <pod-name> -n sentinel-system | grep -A10 Mounts
```

**Solution:**
```bash
# Verify Helm values include mTLS configuration
helm get values sentinel -n sentinel-system

# Upgrade Helm release to mount certificates
helm upgrade sentinel charts/sentinel-core -n sentinel-system \
  --set global.mtls.enabled=true
```

### Issue: mTLS Handshake Failures

**Symptoms:**
```
grpc.aio.AioRpcError: StatusCode.UNAVAILABLE: failed to connect to all addresses
```

**Diagnosis:**
```bash
# Test TLS connection manually
openssl s_client -connect control-api.sentinel-system.svc.cluster.local:8000 \
  -cert /etc/sentinel/certs/tls.crt \
  -key /etc/sentinel/certs/tls.key \
  -CAfile /etc/sentinel/certs/ca.crt
```

**Common Causes:**
1. **Certificate CN/DNS mismatch:** Ensure connecting to correct hostname
2. **CA certificate mismatch:** Client and server must trust same CA
3. **Expired certificate:** Check certificate dates

**Solution:**
```bash
# Verify certificate DNS names
kubectl get secret control-api-tls -n sentinel-system -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -text | grep -A5 "Subject Alternative Name"

# Force certificate renewal
kubectl delete certificate control-api-tls -n sentinel-system
kubectl apply -f deploy/k8s/mtls-config.yaml
```

### Issue: Certificate Rotation Doesn't Work

**Symptoms:**
- Certificate expired despite auto-renewal being enabled
- cert-manager logs show errors

**Diagnosis:**
```bash
# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager | grep -i error

# Check certificate renewal status
kubectl describe certificate control-api-tls -n sentinel-system
```

**Solution:**
```bash
# Ensure cert-manager has RBAC permissions
kubectl get clusterrole cert-manager-controller

# Manually trigger renewal
kubectl annotate certificate control-api-tls -n sentinel-system \
  cert-manager.io/issue-temporary-certificate="true" --overwrite
```

## Security Best Practices

### 1. Certificate Lifecycle

✅ **Do:**
- Use 90-day certificate validity
- Renew 15+ days before expiry
- Monitor certificate expiration
- Automate rotation with cert-manager

❌ **Don't:**
- Use long-lived certificates (>1 year)
- Store certificates in version control
- Share certificates between services
- Disable certificate verification

### 2. Key Management

✅ **Do:**
- Use RSA 2048 or higher
- Store private keys in Kubernetes Secrets
- Restrict Secret access with RBAC
- Enable encryption at rest for etcd

❌ **Don't:**
- Use weak key algorithms (RSA 1024, DSA)
- Store keys in environment variables
- Share private keys between services
- Commit keys to git repositories

### 3. CA Management

✅ **Do:**
- Use separate CA for each environment (dev, staging, prod)
- Protect root CA private key
- Use intermediate CAs for service certificates
- Consider using Vault PKI for production

❌ **Don't:**
- Use same CA across environments
- Store root CA key in Kubernetes
- Use self-signed service certificates directly
- Disable CA verification

### 4. Network Policies

Combine mTLS with Kubernetes NetworkPolicies:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: control-api-mtls-only
  namespace: sentinel-system
spec:
  podSelector:
    matchLabels:
      app: control-api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: pipeline-controller
      ports:
        - protocol: TCP
          port: 8000
```

## Production Deployment

### Prerequisites Checklist

- [ ] cert-manager installed and healthy
- [ ] CA issuer configured (Vault PKI recommended)
- [ ] Service certificates issued and valid
- [ ] Prometheus alerts configured
- [ ] Certificate monitoring dashboard
- [ ] Runbook for certificate issues
- [ ] Backup of CA certificates

### Migration from Non-mTLS

**Phase 1: Deploy with mTLS Disabled**
```bash
helm upgrade sentinel charts/sentinel-core \
  --set global.mtls.enabled=false
```

**Phase 2: Install cert-manager and Issue Certificates**
```bash
kubectl apply -f deploy/k8s/cert-manager.yaml
kubectl apply -f deploy/k8s/mtls-config.yaml
```

**Phase 3: Enable mTLS (Rolling Update)**
```bash
helm upgrade sentinel charts/sentinel-core \
  --set global.mtls.enabled=true
```

**Phase 4: Verify All Services Using mTLS**
```bash
kubectl logs -n sentinel-system -l app=control-api | grep "mTLS: Enabled"
```

## References

- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Kubernetes TLS Management](https://kubernetes.io/docs/concepts/configuration/secret/#tls-secrets)
- [Python SSL Module](https://docs.python.org/3/library/ssl.html)
- [gRPC Authentication](https://grpc.io/docs/guides/auth/)
- [NIST Certificate Guidelines](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-57pt1r5.pdf)

## Support

For issues with mTLS:
1. Check troubleshooting section above
2. Review cert-manager logs: `kubectl logs -n cert-manager deployment/cert-manager`
3. Open GitHub issue with logs and certificate status
4. Contact Sentinel team via Slack #security channel

---

**Last Updated:** November 11, 2025
**Version:** v0.4.0 (Phase 4)
**Status:** Production Ready
