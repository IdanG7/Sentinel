# Sentinel Development Policy
# Allows Sentinel services to read/write secrets during development

# KV secrets engine (v2)
path "secret/data/sentinel/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/sentinel/*" {
  capabilities = ["list", "read"]
}

# Database credentials
path "database/creds/sentinel" {
  capabilities = ["read"]
}

# Kubernetes auth
path "auth/kubernetes/*" {
  capabilities = ["read", "list"]
}

# PKI for mTLS certificates
path "pki/issue/sentinel" {
  capabilities = ["create", "update"]
}

path "pki/cert/*" {
  capabilities = ["read", "list"]
}
