# WebAuthn Stack Helm Chart

A production-ready Helm chart for deploying the WebAuthn authentication stack on Kubernetes. This chart provides passwordless authentication using FIDO2/WebAuthn with zero-trust architecture via Envoy Gateway and JWT-based authorization.

## Overview

This Helm chart deploys:

- **WebAuthn Server**: FIDO2/Passkey authentication with JWT issuing
- **Envoy Gateway**: API gateway with JWT verification
- **Jaeger** (optional): Distributed tracing (temporary until Module 5)
- **Ingress**: NGINX Ingress with TLS/SSL support
- **HorizontalPodAutoscaler**: Auto-scaling based on CPU/memory
- **PodDisruptionBudget**: High availability during updates

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  health-auth namespace                                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Internet                                                │
│      │                                                   │
│      ▼                                                   │
│  ┌────────────────┐                                     │
│  │ Ingress (NGINX)│                                     │
│  │ auth.domain    │                                     │
│  └────────┬───────┘                                     │
│           │                                              │
│           ▼                                              │
│  ┌────────────────┐                                     │
│  │ Envoy Gateway  │ (JWT verification, rate limiting)   │
│  │  Port: 8000    │                                     │
│  └────────┬───────┘                                     │
│           │                                              │
│           ▼                                              │
│  ┌────────────────┐                                     │
│  │ WebAuthn Server│ (FIDO2 registration/authentication)│
│  │  Port: 8080    │                                     │
│  └────┬───────┬───┘                                     │
│       │       │                                          │
│       │       └──────────┐                              │
│       ▼                  ▼                               │
│  PostgreSQL          Redis                              │
│  (webauthn-auth)     (sessions)                         │
│  health-data ns      health-data ns                     │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required (Module 2 - Infrastructure)

Before installing this chart, ensure the following services are deployed:

1. **PostgreSQL (webauthn-auth database)**
   ```bash
   kubectl get svc -n health-data postgresql-auth
   ```

2. **Redis (session storage)**
   ```bash
   kubectl get svc -n health-data redis-auth
   ```

### Required (Ingress Controller)

3. **NGINX Ingress Controller**
   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm install ingress-nginx ingress-nginx/ingress-nginx \
     --namespace health-system --create-namespace
   ```

4. **cert-manager (for SSL certificates)**
   ```bash
   helm repo add jetstack https://charts.jetstack.io
   helm install cert-manager jetstack/cert-manager \
     --namespace health-system \
     --set installCRDs=true
   ```

### Kubernetes Version

- Kubernetes 1.24+ (for autoscaling/v2 API)

## Installation

### 1. Generate Secrets

Before installation, generate secure secrets:

```bash
# Generate database password
export DB_PASSWORD=$(openssl rand -base64 32)

# Generate Redis password
export REDIS_PASSWORD=$(openssl rand -base64 32)

# Generate JWT master encryption key
export JWT_MASTER_KEY=$(openssl rand -base64 32)

# Save to environment file (for reuse)
cat > .env.secrets <<EOF
DATABASE_PASSWORD=${DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
JWT_MASTER_KEY=${JWT_MASTER_KEY}
EOF

# IMPORTANT: Add .env.secrets to .gitignore
echo ".env.secrets" >> .gitignore
```

### 2. Update Production Values

Edit `values-production.yaml`:

```yaml
# Update domain configuration
webauthn:
  config:
    relyingPartyId: "auth.yourdomain.com"
    relyingPartyName: "Your Application Name"
    relyingPartyOrigin: "https://auth.yourdomain.com"

envoy:
  config:
    jwtIssuer: "https://auth.yourdomain.com"

ingress:
  host: auth.yourdomain.com

# Update secrets (use environment variables)
secrets:
  databasePassword: "${DATABASE_PASSWORD}"
  redisPassword: "${REDIS_PASSWORD}"
  jwtMasterKey: "${JWT_MASTER_KEY}"
```

### 3. Install the Chart

```bash
# Load environment variables
source .env.secrets

# Install with production values
helm install webauthn-stack ./helm-charts/health-platform/charts/webauthn-stack \
  --namespace health-auth \
  --create-namespace \
  --values ./helm-charts/health-platform/charts/webauthn-stack/values-production.yaml \
  --set secrets.databasePassword="${DATABASE_PASSWORD}" \
  --set secrets.redisPassword="${REDIS_PASSWORD}" \
  --set secrets.jwtMasterKey="${JWT_MASTER_KEY}"
```

### 4. Verify Installation

```bash
# Check pod status
kubectl get pods -n health-auth

# Check services
kubectl get svc -n health-auth

# Check ingress
kubectl get ingress -n health-auth

# View logs
kubectl logs -f deployment/webauthn-server -n health-auth
```

### 5. Test the Deployment

```bash
# Port forward to test locally
kubectl port-forward -n health-auth svc/envoy-gateway 8000:8000

# Test health endpoint
curl http://localhost:8000/health

# Test registration endpoint
curl -X POST http://localhost:8000/register/start \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","displayName":"Test User"}'
```

## Configuration

### Key Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace` | Kubernetes namespace | `health-auth` |
| `webauthn.replicaCount` | Number of WebAuthn server replicas | `2` |
| `webauthn.config.relyingPartyId` | WebAuthn relying party ID (domain) | `auth.health-platform.example.com` |
| `envoy.replicaCount` | Number of Envoy gateway replicas | `2` |
| `envoy.config.jwksCacheDuration` | JWKS cache duration (seconds) | `300` |
| `ingress.enabled` | Enable Ingress | `true` |
| `ingress.host` | Ingress hostname | `auth.health-platform.example.com` |
| `autoscaling.enabled` | Enable HorizontalPodAutoscaler | `true` |
| `jaeger.enabled` | Enable Jaeger tracing | `true` |

### Resource Limits (Oracle Always Free Tier)

The default resource limits are optimized for Oracle Cloud Always Free tier:

```yaml
webauthn:
  resources:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi

envoy:
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi
```

## Security

### Secret Management

**NEVER commit secrets to Git!** Use one of these methods:

#### Option 1: Sealed Secrets (Recommended for GitOps)

```bash
# Install Sealed Secrets controller
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace health-system

# Encrypt secrets
kubectl create secret generic webauthn-secrets \
  --from-literal=database-password="${DB_PASSWORD}" \
  --from-literal=redis-password="${REDIS_PASSWORD}" \
  --from-literal=jwt-master-key="${JWT_MASTER_KEY}" \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secrets.yaml

# Commit sealed-secrets.yaml to Git (safe)
git add sealed-secrets.yaml
```

#### Option 2: External Secrets Operator with OCI Vault

```bash
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace health-system

# Configure OCI Vault backend (see Module 6)
```

#### Option 3: Environment Variables (CI/CD)

```bash
# In your CI/CD pipeline (GitHub Actions, GitLab CI, etc.)
helm install webauthn-stack ./charts/webauthn-stack \
  --set secrets.databasePassword="${DATABASE_PASSWORD}" \
  --set secrets.redisPassword="${REDIS_PASSWORD}" \
  --set secrets.jwtMasterKey="${JWT_MASTER_KEY}"
```

### TLS/SSL Certificates

The chart uses cert-manager with Let's Encrypt for automatic SSL certificate management:

```bash
# Create Let's Encrypt issuer (production)
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

## Monitoring

### Prometheus Metrics

Enable ServiceMonitor for Prometheus Operator:

```yaml
serviceMonitor:
  enabled: true
  interval: 30s
  scrapeTimeout: 10s
```

Metrics endpoints:
- WebAuthn Server: `http://webauthn-server:8080/metrics`
- Envoy Gateway: `http://envoy-gateway:9901/stats/prometheus`

### Jaeger Tracing

Access Jaeger UI:

```bash
kubectl port-forward -n health-auth svc/jaeger 16686:16686
# Open http://localhost:16686
```

## High Availability

### Autoscaling

The chart includes HorizontalPodAutoscaler for both WebAuthn and Envoy:

```bash
# Check HPA status
kubectl get hpa -n health-auth

# Describe HPA
kubectl describe hpa webauthn-server-hpa -n health-auth
```

### Pod Disruption Budget

Ensures at least 1 pod remains available during updates:

```bash
kubectl get pdb -n health-auth
```

## Upgrading

### Upgrade the Chart

```bash
# Update values
vim values-production.yaml

# Upgrade release
helm upgrade webauthn-stack ./helm-charts/health-platform/charts/webauthn-stack \
  --namespace health-auth \
  --values values-production.yaml \
  --set secrets.databasePassword="${DATABASE_PASSWORD}" \
  --set secrets.redisPassword="${REDIS_PASSWORD}" \
  --set secrets.jwtMasterKey="${JWT_MASTER_KEY}"
```

### Rollback

```bash
# View release history
helm history webauthn-stack -n health-auth

# Rollback to previous version
helm rollback webauthn-stack -n health-auth

# Rollback to specific revision
helm rollback webauthn-stack 3 -n health-auth
```

## Uninstallation

```bash
# Uninstall the release
helm uninstall webauthn-stack -n health-auth

# Delete namespace (optional)
kubectl delete namespace health-auth
```

## Troubleshooting

### Pods Not Starting

```bash
# Describe pod
kubectl describe pod -n health-auth <pod-name>

# Check logs
kubectl logs -n health-auth <pod-name>

# Check events
kubectl get events -n health-auth --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
kubectl run -it --rm debug --image=postgres:15-alpine --restart=Never -- \
  psql -h postgresql-auth.health-data.svc.cluster.local -U webauthn_user -d webauthn

# Check database service
kubectl get svc -n health-data postgresql-auth
```

### Redis Connection Issues

```bash
# Test Redis connection
kubectl run -it --rm debug --image=redis:7-alpine --restart=Never -- \
  redis-cli -h redis-auth.health-data.svc.cluster.local

# Check Redis service
kubectl get svc -n health-data redis-auth
```

### Ingress Not Working

```bash
# Describe ingress
kubectl describe ingress -n health-auth webauthn-ingress

# Check NGINX Ingress Controller logs
kubectl logs -n health-system -l app.kubernetes.io/name=ingress-nginx

# Verify cert-manager certificate
kubectl get certificate -n health-auth
kubectl describe certificate -n health-auth webauthn-tls
```

### JWT Verification Failing

```bash
# Check JWKS endpoint
kubectl port-forward -n health-auth svc/envoy-gateway 8000:8000
curl http://localhost:8000/.well-known/jwks.json | jq

# Check Envoy configuration
kubectl logs -n health-auth deployment/envoy-gateway
```

## Development

### Local Testing (Minikube/Kind)

```bash
# Start Minikube with sufficient resources
minikube start --cpus=4 --memory=8192

# Install with development values
helm install webauthn-stack ./charts/webauthn-stack \
  --namespace health-auth \
  --create-namespace \
  --values values.yaml

# Test with port forwarding
kubectl port-forward -n health-auth svc/envoy-gateway 8000:8000
```

### Linting

```bash
# Lint the chart
helm lint ./helm-charts/health-platform/charts/webauthn-stack

# Dry run install
helm install webauthn-stack ./helm-charts/health-platform/charts/webauthn-stack \
  --namespace health-auth \
  --dry-run --debug
```

### Template Rendering

```bash
# Render templates with values
helm template webauthn-stack ./helm-charts/health-platform/charts/webauthn-stack \
  --values values-production.yaml \
  --set secrets.databasePassword="test" \
  --set secrets.redisPassword="test" \
  --set secrets.jwtMasterKey="test"
```

## Contributing

See the main project [CONTRIBUTING.md](../../../../CONTRIBUTING.md) for guidelines.

## License

Apache-2.0

## Support

- **Issues**: https://github.com/your-org/health-data-ai-platform/issues
- **Documentation**: See `specs/kubernetes-implementation-modules/helm-webauthn-module.md`
- **Integration Guide**: See `webauthn-stack/docs/INTEGRATION.md`

## Related Charts

This chart is part of the Health Data AI Platform umbrella chart:

- **Module 1**: Terraform Infrastructure
- **Module 2**: Helm Charts - Infrastructure (PostgreSQL, Redis, MinIO, RabbitMQ)
- **Module 3**: Helm Charts - WebAuthn Stack (this chart)
- **Module 4**: Helm Charts - Health Services
- **Module 5**: Observability Stack (Prometheus, Grafana, Jaeger, Loki)
- **Module 6**: Security & RBAC
- **Module 7**: GitOps & CI/CD
- **Module 8**: Disaster Recovery
