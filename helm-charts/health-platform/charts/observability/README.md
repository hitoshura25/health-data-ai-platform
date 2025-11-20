# Observability Helm Chart

Complete observability stack for the Health Data AI Platform, providing comprehensive monitoring, logging, tracing, and alerting capabilities.

## Overview

This Helm chart deploys a full observability stack including:

- **Prometheus** - Metrics collection and alerting
- **Grafana** - Visualization and dashboards
- **Jaeger** - Distributed tracing
- **Loki + Promtail** - Log aggregation
- **AlertManager** - Alert routing and management

## Components

### Metrics (Prometheus)
- **Retention**: 30 days
- **Storage**: 20 GB persistent volume
- **Scrape Interval**: 15 seconds
- **Auto-discovery**: ServiceMonitors for all platform services

### Visualization (Grafana)
- **Pre-configured Dashboards**:
  - Kubernetes Cluster Overview
  - Health API Performance (RED metrics)
  - Infrastructure Health (PostgreSQL, Redis, MinIO, RabbitMQ)
  - Cost Monitoring (Always Free tier utilization)
- **Datasources**: Prometheus, Loki, Jaeger
- **Persistence**: 5 GB for dashboard storage

### Tracing (Jaeger)
- **Storage**: Badger (10 GB persistent volume)
- **Protocols**: OTLP (gRPC/HTTP), Jaeger native
- **UI**: Web-based trace visualization

### Logging (Loki)
- **Retention**: 7 days
- **Storage**: 5 GB persistent volume
- **Collection**: Promtail DaemonSet on all nodes
- **Format**: Structured JSON logs with trace correlation

### Alerting (AlertManager)
- **Storage**: 5 GB persistent volume
- **Routes**: Critical, warning, default
- **Integrations**: Email, Slack, PagerDuty, webhooks

## Prerequisites

1. **Kubernetes Cluster**: OKE or any Kubernetes 1.24+
2. **Helm**: Version 3.13+
3. **Storage Class**: `oci-bv` (Oracle Block Volumes) or equivalent
4. **Cert-Manager**: For SSL certificates (production)
5. **NGINX Ingress Controller**: For external access (production)

## Installation

### Development Environment

```bash
# Create namespace
kubectl create namespace health-observability

# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install chart (development)
helm install observability . \
  --namespace health-observability \
  --create-namespace \
  --values values.yaml
```

### Production Environment

```bash
# Create namespace
kubectl create namespace health-observability

# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# IMPORTANT: Update production values first
# 1. Edit values-production.yaml
# 2. Set strong Grafana admin password
# 3. Update domain names for Ingress
# 4. Configure AlertManager receivers (email, Slack, etc.)

# Install chart (production)
helm install observability . \
  --namespace health-observability \
  --create-namespace \
  --values values-production.yaml
```

## Configuration

### Key Configuration Files

- **`values.yaml`**: Default values for development
- **`values-production.yaml`**: Production overrides with SSL, ingress, alerting

### Important Settings to Customize

#### 1. Grafana Admin Password

```yaml
# values-production.yaml
kube-prometheus-stack:
  grafana:
    adminPassword: "YOUR_STRONG_PASSWORD_HERE"
```

#### 2. Ingress Domains

```yaml
# values-production.yaml
kube-prometheus-stack:
  grafana:
    ingress:
      hosts:
        - grafana.yourdomain.com  # Change this
      tls:
        - hosts:
            - grafana.yourdomain.com

jaeger:
  ingress:
    hosts:
      - jaeger.yourdomain.com  # Change this
    tls:
      - hosts:
          - jaeger.yourdomain.com
```

#### 3. AlertManager Receivers

```yaml
# values-production.yaml
kube-prometheus-stack:
  alertmanager:
    config:
      receivers:
        - name: 'critical'
          # Example: Slack
          slack_configs:
            - api_url: 'YOUR_SLACK_WEBHOOK_URL'
              channel: '#critical-alerts'
              title: 'Critical Alert'

        - name: 'warning'
          # Example: Email
          email_configs:
            - to: 'team@example.com'
              from: 'alerts@example.com'
              smarthost: 'smtp.gmail.com:587'
              auth_username: 'alerts@example.com'
              auth_password: 'YOUR_APP_PASSWORD'
```

## Accessing Services

### Port Forwarding (Development)

```bash
# Grafana
kubectl port-forward -n health-observability svc/kube-prometheus-stack-grafana 3000:80
# Access: http://localhost:3000
# Username: admin
# Password: (from values.yaml)

# Prometheus
kubectl port-forward -n health-observability svc/kube-prometheus-stack-prometheus 9090:9090
# Access: http://localhost:9090

# Jaeger
kubectl port-forward -n health-observability svc/jaeger-query 16686:16686
# Access: http://localhost:16686

# AlertManager
kubectl port-forward -n health-observability svc/kube-prometheus-stack-alertmanager 9093:9093
# Access: http://localhost:9093
```

### Ingress (Production)

After deploying with production values and DNS configured:

- **Grafana**: https://grafana.yourdomain.com
- **Jaeger**: https://jaeger.yourdomain.com
- **Prometheus**: Internal only (no ingress by default for security)
- **AlertManager**: Internal only (no ingress by default for security)

## Dashboards

### Pre-configured Dashboards

1. **Kubernetes Cluster Overview** (`k8s-cluster-overview`)
   - Node CPU/Memory/Network usage
   - Pod distribution
   - Persistent volume usage
   - Active alerts

2. **Health API Performance** (`health-api-perf`)
   - Request rate (RED metrics)
   - Response time (p95, p99)
   - Error rate
   - Pod status and resources

3. **Infrastructure Health** (`infra-health`)
   - PostgreSQL status and connections
   - Redis status and memory
   - MinIO storage usage
   - RabbitMQ queue depth

4. **Cost Monitoring** (`cost-monitoring`)
   - CPU utilization vs Always Free limit (4 vCPU)
   - Memory utilization vs Always Free limit (24 GB)
   - Storage utilization vs Always Free limit (200 GB)
   - Resource distribution by namespace

### Importing Additional Dashboards

Grafana dashboards can be imported from [Grafana.com](https://grafana.com/grafana/dashboards/):

1. Navigate to Grafana → Dashboards → Import
2. Enter dashboard ID or upload JSON
3. Select Prometheus as datasource
4. Click Import

## ServiceMonitors

The chart automatically creates ServiceMonitors for:

- Health API Service
- WebAuthn Server
- ETL Narrative Engine
- PostgreSQL (health-data)
- PostgreSQL (webauthn-auth)
- Redis (health-data)
- Redis (webauthn-sessions)
- MinIO
- RabbitMQ
- Jaeger

These enable Prometheus to auto-discover and scrape metrics from all services.

## Alerting Rules

### Built-in Alert Rules

The chart includes comprehensive alerting for:

#### Application Alerts
- High error rate (>5% for 5 minutes)
- High latency (p95 > 1s for 5 minutes)
- Pod unavailable
- High memory usage (>85%)

#### Infrastructure Alerts
- Database down
- Too many database connections (>80%)
- High replication lag
- Database deadlocks
- Redis down
- Redis high memory usage
- Redis rejected connections
- MinIO down or disk offline
- MinIO low storage (<20% free)
- RabbitMQ down
- Queue depth too high (>1000 messages)
- Queue with no consumers

#### Kubernetes Alerts
- Node not ready
- Pod crash looping
- PersistentVolume filling up (>80%)
- PersistentVolume critical (>90%)
- Node CPU/Memory high (>80-85%)

### Testing Alerts

```bash
# Check PrometheusRules
kubectl get prometheusrules -n health-observability

# View active alerts in Prometheus
kubectl port-forward -n health-observability svc/kube-prometheus-stack-prometheus 9090:9090
# Navigate to: http://localhost:9090/alerts

# View AlertManager
kubectl port-forward -n health-observability svc/kube-prometheus-stack-alertmanager 9093:9093
# Navigate to: http://localhost:9093
```

## Resource Requirements

### Total Storage (Always Free Tier: 200 GB)
- Prometheus: 20 GB
- Grafana: 5 GB
- Jaeger: 10 GB
- Loki: 5 GB
- AlertManager: 5 GB
- **Total**: 45 GB (~22.5% of free tier)

### Total CPU Requests
- Prometheus: 500m
- Grafana: 200m
- Jaeger: 300m
- Loki: 200m
- Promtail: 100m (per node)
- AlertManager: 100m
- Node Exporter: 100m (per node)
- Kube State Metrics: 100m
- **Total**: ~2000m (2 vCPU) for 3-node cluster

### Total Memory Requests
- Prometheus: 2 Gi
- Grafana: 512 Mi
- Jaeger: 512 Mi
- Loki: 512 Mi
- Promtail: 128 Mi (per node)
- AlertManager: 128 Mi
- Node Exporter: 64 Mi (per node)
- Kube State Metrics: 128 Mi
- **Total**: ~5 Gi for 3-node cluster

## Upgrading

```bash
# Update Helm repositories
helm repo update

# Check for chart updates
helm search repo prometheus-community/kube-prometheus-stack
helm search repo grafana/loki-stack

# Upgrade release
helm upgrade observability . \
  --namespace health-observability \
  --values values-production.yaml
```

## Troubleshooting

### Prometheus not scraping targets

```bash
# Check ServiceMonitors
kubectl get servicemonitors -A

# Check Prometheus targets
kubectl port-forward -n health-observability svc/kube-prometheus-stack-prometheus 9090:9090
# Navigate to: http://localhost:9090/targets

# Check Prometheus logs
kubectl logs -n health-observability -l app.kubernetes.io/name=prometheus
```

### Grafana dashboards not loading

```bash
# Check ConfigMaps
kubectl get configmaps -n health-observability | grep grafana-dashboard

# Check Grafana logs
kubectl logs -n health-observability -l app.kubernetes.io/name=grafana

# Restart Grafana
kubectl rollout restart deployment/kube-prometheus-stack-grafana -n health-observability
```

### Loki not receiving logs

```bash
# Check Promtail DaemonSet
kubectl get daemonset -n health-observability loki-stack-promtail

# Check Promtail logs
kubectl logs -n health-observability -l app.kubernetes.io/name=promtail

# Check Loki logs
kubectl logs -n health-observability -l app.kubernetes.io/name=loki
```

### Jaeger not receiving traces

```bash
# Check Jaeger pod
kubectl get pods -n health-observability -l app=jaeger

# Check Jaeger logs
kubectl logs -n health-observability -l app=jaeger

# Verify OTLP endpoints are accessible
kubectl exec -it <app-pod> -- curl http://jaeger-collector.health-observability:4318
```

## Uninstallation

```bash
# Delete Helm release
helm uninstall observability --namespace health-observability

# Delete PVCs (if you want to remove all data)
kubectl delete pvc -n health-observability --all

# Delete namespace
kubectl delete namespace health-observability
```

## Security Considerations

### Production Checklist

- [ ] Changed default Grafana admin password
- [ ] Configured SSL/TLS for all ingresses
- [ ] Restricted Prometheus admin API access
- [ ] Configured AlertManager authentication
- [ ] Set up proper RBAC for service accounts
- [ ] Enabled Pod Security Standards
- [ ] Configured NetworkPolicies for service isolation
- [ ] Encrypted AlertManager secrets
- [ ] Set up audit logging
- [ ] Configured backup for Prometheus data

## Backup and Recovery

### Backup Grafana Dashboards

```bash
# Export all dashboards
kubectl get configmaps -n health-observability -l grafana_dashboard=1 -o yaml > grafana-dashboards-backup.yaml
```

### Backup Prometheus Data

Use Velero (see Module 8) or manual snapshot:

```bash
# Create snapshot of Prometheus PVC
kubectl exec -n health-observability kube-prometheus-stack-prometheus-0 -- \
  tar czf /prometheus/backup.tar.gz /prometheus/data
```

### Backup AlertManager Configuration

```bash
# Export AlertManager config
kubectl get secret -n health-observability alertmanager-kube-prometheus-stack-alertmanager -o yaml > alertmanager-config-backup.yaml
```

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review Helm chart logs: `helm status observability -n health-observability`
3. Consult upstream documentation:
   - [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
   - [Loki Stack](https://grafana.com/docs/loki/latest/)
   - [Jaeger](https://www.jaegertracing.io/docs/)

## License

This chart is part of the Health Data AI Platform project.

## Version History

- **1.0.0** (2025-01-20): Initial release with Prometheus, Grafana, Jaeger, Loki, and comprehensive alerting
