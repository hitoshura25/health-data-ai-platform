# WebAuthn Stack - Quick Installation Guide

This guide provides step-by-step instructions for deploying the WebAuthn authentication stack to Kubernetes.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Kubernetes cluster (1.24+) running
- [ ] kubectl configured and connected to cluster
- [ ] Helm 3.13+ installed
- [ ] Module 2 deployed (PostgreSQL and Redis)
- [ ] NGINX Ingress Controller installed
- [ ] cert-manager installed

## Quick Start (5 minutes)

### 1. Generate Secrets (30 seconds)

```bash
# Navigate to chart directory
cd helm-charts/health-platform/charts/webauthn-stack

# Generate secure passwords
export DB_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)
export JWT_MASTER_KEY=$(openssl rand -base64 32)

# Save to file (DO NOT COMMIT THIS FILE!)
cat > .env.secrets <<EOF
DATABASE_PASSWORD=${DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
JWT_MASTER_KEY=${JWT_MASTER_KEY}
EOF

# Add to .gitignore
echo ".env.secrets" >> ../../../../.gitignore
```

### 2. Configure Domain (1 minute)

Edit `values-production.yaml` and update these fields:

```yaml
webauthn:
  config:
    relyingPartyId: "auth.yourdomain.com"          # Your domain
    relyingPartyName: "Your Application Name"       # Your app name
    relyingPartyOrigin: "https://auth.yourdomain.com"  # HTTPS URL

envoy:
  config:
    jwtIssuer: "https://auth.yourdomain.com"        # HTTPS URL

ingress:
  host: auth.yourdomain.com                         # Your domain
```

### 3. Install Chart (2 minutes)

```bash
# Load secrets
source .env.secrets

# Install
helm install webauthn-stack . \
  --namespace health-auth \
  --create-namespace \
  --values values-production.yaml \
  --set secrets.databasePassword="${DATABASE_PASSWORD}" \
  --set secrets.redisPassword="${REDIS_PASSWORD}" \
  --set secrets.jwtMasterKey="${JWT_MASTER_KEY}"

# Wait for pods to be ready
kubectl wait --for=condition=ready pod \
  -l app=webauthn-server \
  -n health-auth \
  --timeout=300s
```

### 4. Verify Installation (1 minute)

```bash
# Check all pods are running
kubectl get pods -n health-auth

# Expected output:
# NAME                               READY   STATUS    RESTARTS   AGE
# envoy-gateway-xxxxxxxxx-xxxxx      1/1     Running   0          2m
# envoy-gateway-xxxxxxxxx-xxxxx      1/1     Running   0          2m
# jaeger-xxxxxxxxx-xxxxx             1/1     Running   0          2m
# webauthn-server-xxxxxxxxx-xxxxx    1/1     Running   0          2m
# webauthn-server-xxxxxxxxx-xxxxx    1/1     Running   0          2m

# Check ingress
kubectl get ingress -n health-auth

# Test health endpoint
kubectl port-forward -n health-auth svc/envoy-gateway 8000:8000 &
curl http://localhost:8000/health
```

### 5. Configure DNS (varies)

Point your domain to the Ingress LoadBalancer:

```bash
# Get LoadBalancer IP/hostname
kubectl get ingress -n health-auth webauthn-ingress

# Create DNS A record:
# auth.yourdomain.com → <EXTERNAL-IP>
```

### 6. Test HTTPS Endpoint (after DNS propagates)

```bash
# Test health endpoint
curl https://auth.yourdomain.com/health

# Test registration endpoint
curl -X POST https://auth.yourdomain.com/register/start \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","displayName":"Test User"}'
```

## Production Deployment Checklist

### Pre-Deployment

- [ ] PostgreSQL and Redis deployed (Module 2)
- [ ] Secrets generated and stored securely
- [ ] Domain name configured and propagated
- [ ] SSL certificate issuer configured (Let's Encrypt)
- [ ] Resource limits reviewed for your cluster size

### Post-Deployment

- [ ] All pods running and ready
- [ ] Ingress configured with valid SSL certificate
- [ ] Health endpoint responding
- [ ] Registration/authentication flows tested
- [ ] HorizontalPodAutoscaler active
- [ ] Jaeger traces visible (if enabled)
- [ ] Metrics endpoint accessible (for Prometheus)
- [ ] Backup secrets to secure location

### Security Hardening

- [ ] Rotate default secrets
- [ ] Enable Sealed Secrets or External Secrets Operator
- [ ] Configure NetworkPolicies (Module 6)
- [ ] Enable Pod Security Standards
- [ ] Review RBAC permissions
- [ ] Enable rate limiting on Ingress
- [ ] Configure security headers

### Monitoring & Observability

- [ ] Enable ServiceMonitor (after Module 5)
- [ ] Configure Prometheus alerts
- [ ] Set up Grafana dashboards
- [ ] Test distributed tracing in Jaeger
- [ ] Configure log aggregation

## Common Installation Issues

### Issue 1: Pods Pending (ImagePullBackOff)

```bash
# Check pod details
kubectl describe pod -n health-auth webauthn-server-xxx

# Solution: Verify image repository and tag
# Update values.yaml with correct image
```

### Issue 2: Database Connection Failed

```bash
# Test PostgreSQL connectivity
kubectl run -it --rm debug --image=postgres:15-alpine --restart=Never -- \
  psql -h postgresql-auth.health-data.svc.cluster.local \
       -U webauthn_user \
       -d webauthn

# Verify password matches Module 2 deployment
```

### Issue 3: Ingress Not Working

```bash
# Check Ingress Controller
kubectl get pods -n health-system -l app.kubernetes.io/name=ingress-nginx

# Check cert-manager
kubectl get certificate -n health-auth
kubectl describe certificate -n health-auth webauthn-tls

# Check Ingress events
kubectl describe ingress -n health-auth webauthn-ingress
```

### Issue 4: JWT Verification Failing

```bash
# Check JWKS endpoint
curl http://localhost:8000/.well-known/jwks.json

# Should return JSON with RSA keys
# If empty, check WebAuthn server logs
kubectl logs -n health-auth deployment/webauthn-server
```

## Upgrade Procedure

### Prepare Upgrade

```bash
# Backup current values
helm get values webauthn-stack -n health-auth > current-values.yaml

# Review changes in new chart version
helm diff upgrade webauthn-stack . \
  --namespace health-auth \
  --values values-production.yaml
```

### Execute Upgrade

```bash
# Load secrets
source .env.secrets

# Perform upgrade
helm upgrade webauthn-stack . \
  --namespace health-auth \
  --values values-production.yaml \
  --set secrets.databasePassword="${DATABASE_PASSWORD}" \
  --set secrets.redisPassword="${REDIS_PASSWORD}" \
  --set secrets.jwtMasterKey="${JWT_MASTER_KEY}"

# Monitor rollout
kubectl rollout status deployment/webauthn-server -n health-auth
kubectl rollout status deployment/envoy-gateway -n health-auth
```

### Rollback (if needed)

```bash
# View history
helm history webauthn-stack -n health-auth

# Rollback to previous version
helm rollback webauthn-stack -n health-auth
```

## Uninstallation

```bash
# Uninstall chart
helm uninstall webauthn-stack -n health-auth

# Delete namespace (optional - removes all resources)
kubectl delete namespace health-auth

# Clean up secrets file
rm .env.secrets
```

## Next Steps

After successful installation:

1. **Integration Testing**: Test full authentication flow with your application
2. **Module 4**: Deploy Health Services Helm charts
3. **Module 5**: Set up Observability stack (Prometheus, Grafana)
4. **Module 6**: Apply Security hardening (NetworkPolicies, RBAC)
5. **Module 7**: Configure GitOps with ArgoCD
6. **Module 8**: Set up Disaster Recovery backups

## Support

- **Documentation**: See [README.md](./README.md) for detailed configuration
- **Troubleshooting**: See [README.md#troubleshooting](./README.md#troubleshooting)
- **Specifications**: `specs/kubernetes-implementation-modules/helm-webauthn-module.md`
- **Issues**: https://github.com/your-org/health-data-ai-platform/issues

---

**Installation Time**: ~5 minutes
**Difficulty**: Intermediate
**Module**: 3 of 8
