# Observability Stack - Installation Guide

This guide provides step-by-step instructions for deploying the observability stack for the Health Data AI Platform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Development Installation](#development-installation)
4. [Production Installation](#production-installation)
5. [Post-Installation Steps](#post-installation-steps)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

```bash
# Verify kubectl
kubectl version --client

# Verify Helm
helm version

# Verify cluster access
kubectl cluster-info
```

### Minimum Kubernetes Version

- Kubernetes 1.24 or higher
- Helm 3.13 or higher

### Resource Requirements

**Development:**
- 2 vCPUs
- 4 GB RAM
- 20 GB storage

**Production (Oracle Always Free Tier):**
- Node 1: 2 vCPUs, 12 GB RAM (System & Observability)
- Storage: 45 GB total
  - Prometheus: 20 GB
  - Jaeger: 10 GB
  - Loki: 5 GB
  - Grafana: 5 GB
  - AlertManager: 5 GB

---

## Quick Start

For a quick development deployment:

```bash
# Clone repository
cd /path/to/health-data-ai-platform

# Navigate to chart
cd helm-charts/health-platform/charts/observability

# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install chart
helm install observability . \
  --namespace health-observability \
  --create-namespace

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana \
  -n health-observability --timeout=300s

# Port-forward Grafana
kubectl port-forward -n health-observability svc/observability-grafana 3000:80

# Access Grafana at http://localhost:3000
# Username: admin
# Password: changeme123
```

---

## Development Installation

### Step 1: Add Helm Repositories

```bash
# Add required repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts

# Update repositories
helm repo update
```

### Step 2: Update Chart Dependencies

```bash
# Navigate to chart directory
cd helm-charts/health-platform/charts/observability

# Update dependencies
helm dependency update

# Verify dependencies
helm dependency list
```

Expected output:
```
NAME                     VERSION    REPOSITORY                                           STATUS
kube-prometheus-stack    55.5.0     https://prometheus-community.github.io/helm-charts   ok
loki                     5.41.4     https://grafana.github.io/helm-charts                ok
promtail                 6.15.3     https://grafana.github.io/helm-charts                ok
```

### Step 3: Customize Values (Optional)

Create a custom values file for development:

```bash
cat > values-dev.yaml <<EOF
global:
  namespace: health-observability
  clusterName: my-dev-cluster
  environment: development
  storageClass: standard

kube-prometheus-stack:
  grafana:
    adminPassword: myDevPassword123
    ingress:
      enabled: false

jaeger:
  ingress:
    enabled: false

# Reduce resource requests for local development
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      resources:
        requests:
          cpu: 200m
          memory: 1Gi
      retention: 7d
      storageSpec:
        volumeClaimTemplate:
          spec:
            resources:
              requests:
                storage: 10Gi
EOF
```

### Step 4: Install Chart

```bash
# Install with default values
helm install observability . \
  --namespace health-observability \
  --create-namespace

# OR install with custom values
helm install observability . \
  --namespace health-observability \
  --create-namespace \
  --values values-dev.yaml
```

### Step 5: Verify Installation

```bash
# Check all pods are running
kubectl get pods -n health-observability

# Expected pods:
# - observability-kube-prometheus-operator-*
# - observability-kube-prometheus-prometheus-*
# - observability-grafana-*
# - observability-kube-prometheus-alertmanager-*
# - observability-loki-*
# - observability-promtail-* (DaemonSet, one per node)
# - jaeger-*
```

---

## Production Installation

### Step 1: Prepare Production Values

```bash
# Copy production template
cp values-production.yaml values-prod-custom.yaml

# Edit production values
nano values-prod-custom.yaml
```

**Critical settings to update:**

```yaml
global:
  clusterName: health-platform-prod  # Your cluster name
  environment: production
  storageClass: oci-bv  # Oracle Cloud Block Volume

kube-prometheus-stack:
  grafana:
    adminPassword: "CHANGE_THIS_TO_SECURE_PASSWORD"  # IMPORTANT!
    ingress:
      enabled: true
      hosts:
        - grafana.yourdomain.com  # Your domain
      tls:
        - secretName: grafana-tls
          hosts:
            - grafana.yourdomain.com

jaeger:
  ingress:
    enabled: true
    host: jaeger.yourdomain.com  # Your domain
    tls:
      enabled: true
      secretName: jaeger-tls
```

### Step 2: Create Secrets (Production)

For production, use Sealed Secrets or external secrets manager:

```bash
# Create Grafana admin password secret
kubectl create secret generic grafana-admin-password \
  --from-literal=admin-password='YOUR_SECURE_PASSWORD' \
  -n health-observability \
  --dry-run=client -o yaml > grafana-secret.yaml

# Seal the secret (if using Sealed Secrets)
kubeseal -f grafana-secret.yaml -w grafana-sealed-secret.yaml

# Apply sealed secret
kubectl apply -f grafana-sealed-secret.yaml
```

### Step 3: Pre-create Namespace with Labels

```bash
# Create namespace with labels
kubectl create namespace health-observability

# Label namespace for monitoring
kubectl label namespace health-observability \
  name=health-observability \
  environment=production \
  monitoring=enabled

# Apply pod security standards
kubectl label namespace health-observability \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

### Step 4: Install Chart (Production)

```bash
# Update dependencies
helm dependency update

# Install with production values
helm install observability . \
  --namespace health-observability \
  --values values-production.yaml \
  --timeout 10m \
  --wait
```

### Step 5: Configure SSL/TLS (Production)

If using cert-manager for SSL:

```bash
# Ensure cert-manager is installed
kubectl get pods -n cert-manager

# Create ClusterIssuer (if not exists)
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Step 6: Configure AlertManager Receivers (Production)

Update AlertManager configuration with real notification channels:

```yaml
# In values-production.yaml
kube-prometheus-stack:
  alertmanager:
    config:
      receivers:
      - name: 'critical'
        slack_configs:
        - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
          channel: '#alerts-critical'
          title: 'Critical Alert: {{ .GroupLabels.alertname }}'

      - name: 'warning'
        email_configs:
        - to: 'ops-team@yourdomain.com'
          from: 'alertmanager@yourdomain.com'
          smarthost: 'smtp.gmail.com:587'
          auth_username: 'alerts@yourdomain.com'
          auth_password: 'APP_PASSWORD'
```

---

## Post-Installation Steps

### 1. Access Dashboards

#### Grafana

```bash
# Port-forward
kubectl port-forward -n health-observability svc/observability-grafana 3000:80

# Access: http://localhost:3000
# Login with configured credentials
```

#### Prometheus

```bash
kubectl port-forward -n health-observability \
  svc/observability-kube-prometheus-prometheus 9090:9090

# Access: http://localhost:9090
```

#### Jaeger

```bash
kubectl port-forward -n health-observability svc/jaeger-query 16686:16686

# Access: http://localhost:16686
```

### 2. Configure Service Instrumentation

Add instrumentation to your services to send metrics to Prometheus:

```yaml
# Example ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-service
  namespace: my-namespace
  labels:
    release: observability
spec:
  selector:
    matchLabels:
      app: my-service
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
```

### 3. Verify Metrics Collection

```bash
# Port-forward Prometheus
kubectl port-forward -n health-observability \
  svc/observability-kube-prometheus-prometheus 9090:9090

# Open browser: http://localhost:9090/targets
# Verify all targets are "UP"
```

### 4. Test Alerts

```bash
# Port-forward AlertManager
kubectl port-forward -n health-observability \
  svc/observability-kube-prometheus-alertmanager 9093:9093

# Open browser: http://localhost:9093
# Check for active alerts
```

### 5. Explore Pre-configured Dashboards

In Grafana (http://localhost:3000):
1. Navigate to "Dashboards" → "Browse"
2. Open:
   - Health Platform - Application Overview
   - Infrastructure Health
   - Cost Monitoring - Oracle Free Tier Usage
   - Security Dashboard

---

## Verification

### Check All Pods Running

```bash
kubectl get pods -n health-observability

# All pods should show STATUS: Running
```

### Check PersistentVolumeClaims

```bash
kubectl get pvc -n health-observability

# All PVCs should show STATUS: Bound
```

### Check ServiceMonitors

```bash
kubectl get servicemonitors -A

# Should list all configured ServiceMonitors
```

### Check PrometheusRules

```bash
kubectl get prometheusrules -n health-observability

# Should show: health-platform-alerts
```

### Test Metrics Query

```bash
# Port-forward Prometheus
kubectl port-forward -n health-observability \
  svc/observability-kube-prometheus-prometheus 9090:9090

# Query metrics
curl 'http://localhost:9090/api/v1/query?query=up'
```

### Test Log Aggregation

```bash
# Port-forward Loki
kubectl port-forward -n health-observability \
  svc/observability-loki 3100:3100

# Query logs
curl http://localhost:3100/loki/api/v1/labels
```

### Test Distributed Tracing

```bash
# Port-forward Jaeger
kubectl port-forward -n health-observability svc/jaeger-query 16686:16686

# Check Jaeger is accessible
curl http://localhost:16686/api/services
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Describe pod to see events
kubectl describe pod <pod-name> -n health-observability

# Check logs
kubectl logs <pod-name> -n health-observability

# Common issues:
# - Insufficient resources: Check kubectl top nodes
# - Storage class not found: Verify storageClass in values.yaml
# - Image pull errors: Check image repository and credentials
```

### Prometheus Not Scraping Targets

```bash
# Check Prometheus operator logs
kubectl logs -n health-observability \
  deployment/observability-kube-prometheus-operator

# Verify ServiceMonitor selectors
kubectl get servicemonitor -A -o yaml | grep -A 5 selector

# Check Prometheus configuration
kubectl get secret -n health-observability \
  prometheus-observability-kube-prometheus-prometheus -o yaml
```

### Grafana Not Loading Dashboards

```bash
# Check Grafana logs
kubectl logs -n health-observability deployment/observability-grafana

# Verify dashboard ConfigMaps
kubectl get configmaps -n health-observability | grep dashboard

# Restart Grafana
kubectl rollout restart deployment/observability-grafana -n health-observability
```

### Storage Full

```bash
# Check PVC usage
kubectl exec -n health-observability prometheus-observability-kube-prometheus-prometheus-0 -- \
  df -h /prometheus

# Reduce retention:
helm upgrade observability . \
  --namespace health-observability \
  --set kube-prometheus-stack.prometheus.prometheusSpec.retention=15d
```

### High Memory Usage

```bash
# Check memory usage
kubectl top pods -n health-observability

# Adjust Prometheus memory limits
helm upgrade observability . \
  --namespace health-observability \
  --set kube-prometheus-stack.prometheus.prometheusSpec.resources.limits.memory=6Gi
```

---

## Upgrading

```bash
# Update dependencies
helm dependency update

# Upgrade release
helm upgrade observability . \
  --namespace health-observability \
  --values values-production.yaml \
  --timeout 10m

# Check upgrade status
helm history observability -n health-observability
```

## Uninstalling

```bash
# Uninstall chart
helm uninstall observability --namespace health-observability

# Delete namespace (WARNING: This deletes all data!)
kubectl delete namespace health-observability
```

---

## Next Steps

After successful installation:

1. ✅ Configure AlertManager notification channels
2. ✅ Set up ingress with SSL for production
3. ✅ Add ServiceMonitors for your applications
4. ✅ Configure authentication for Grafana (LDAP/OAuth)
5. ✅ Set up backup for Grafana dashboards
6. ✅ Test disaster recovery procedures
7. ✅ Review and adjust resource limits
8. ✅ Enable audit logging
9. ✅ Configure log retention policies
10. ✅ Document runbooks for common operations

---

## Support

For issues or questions:
- Review troubleshooting section above
- Check [README.md](README.md) for detailed documentation
- Consult official documentation:
  - [Prometheus](https://prometheus.io/docs/)
  - [Grafana](https://grafana.com/docs/)
  - [Jaeger](https://www.jaegertracing.io/docs/)
  - [Loki](https://grafana.com/docs/loki/)
