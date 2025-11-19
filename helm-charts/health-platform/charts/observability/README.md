# Observability Stack Helm Chart

Complete observability stack for the Health Data AI Platform, providing metrics, logs, traces, and dashboards.

## Overview

This Helm chart deploys a comprehensive observability solution based on:

- **Prometheus** - Metrics collection and alerting
- **Grafana** - Visualization and dashboards
- **Jaeger** - Distributed tracing
- **Loki** - Log aggregation
- **Promtail** - Log shipping
- **AlertManager** - Alert routing and notifications

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  health-observability namespace                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │  Prometheus  │◄─────│ServiceMonitor│                │
│  │              │      │  (CRDs)       │                │
│  │  - Scrapes   │      └──────────────┘                │
│  │  - 30d ret.  │                                        │
│  │  - 20GB PVC  │           ▼                           │
│  └──────┬───────┘    ┌──────────────┐                  │
│         │            │ AlertManager │                   │
│         │            │ (Notifications)                  │
│         ▼            └──────────────┘                  │
│  ┌──────────────┐                                        │
│  │   Grafana    │◄─── Loki ◄─── Promtail (DaemonSet)  │
│  │              │                                        │
│  │  - Ingress   │◄─── Jaeger (OTLP)                    │
│  │  - Auth      │                                        │
│  └──────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes 1.24+
- Helm 3.13+
- PersistentVolume support (for metrics and logs storage)
- Prometheus Operator CRDs (automatically installed with kube-prometheus-stack)

## Installation

### Development Environment

```bash
# Add required Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install the chart
helm install observability . \
  --namespace health-observability \
  --create-namespace
```

### Production Environment (Oracle Cloud - Always Free Tier)

```bash
# Install with production values
helm install observability . \
  --namespace health-observability \
  --create-namespace \
  --values values-production.yaml
```

### Custom Configuration

```bash
# Create custom values file
cat > my-values.yaml <<EOF
global:
  clusterName: my-cluster
  environment: staging

kube-prometheus-stack:
  grafana:
    adminPassword: MySecurePassword123!
    ingress:
      enabled: true
      hosts:
        - grafana.example.com

jaeger:
  ingress:
    enabled: true
    host: jaeger.example.com
EOF

# Install with custom values
helm install observability . \
  --namespace health-observability \
  --create-namespace \
  --values my-values.yaml
```

## Configuration

### Key Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Namespace for observability stack | `health-observability` |
| `global.clusterName` | Cluster identifier | `health-platform-dev` |
| `global.environment` | Environment (dev/staging/prod) | `development` |
| `global.storageClass` | Storage class for PVCs | `standard` |
| `jaeger.enabled` | Enable Jaeger tracing | `true` |
| `jaeger.persistence.size` | Jaeger storage size | `5Gi` |
| `kube-prometheus-stack.enabled` | Enable Prometheus stack | `true` |
| `kube-prometheus-stack.prometheus.prometheusSpec.retention` | Metrics retention period | `30d` |
| `kube-prometheus-stack.prometheus.prometheusSpec.storageSpec.resources.requests.storage` | Prometheus storage size | `20Gi` |
| `loki.enabled` | Enable Loki log aggregation | `true` |
| `loki.loki.limits_config.retention_period` | Log retention period | `168h` (7 days) |
| `promtail.enabled` | Enable Promtail log shipping | `true` |
| `serviceMonitors.enabled` | Create ServiceMonitors for services | `true` |

### Resource Limits (Production - Always Free Tier)

```yaml
# Prometheus
resources:
  requests:
    cpu: 500m
    memory: 2Gi
  limits:
    cpu: 1000m
    memory: 4Gi

# Grafana
resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 500m
    memory: 1Gi

# Jaeger
resources:
  requests:
    cpu: 300m
    memory: 512Mi
  limits:
    cpu: 500m
    memory: 1Gi

# Loki
resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 400m
    memory: 1Gi
```

### Storage Allocation

| Component | Size | Purpose |
|-----------|------|---------|
| Prometheus | 20 GB | 30-day metrics retention |
| Jaeger | 10 GB | Distributed trace storage |
| Loki | 5 GB | 7-day log retention |
| Grafana | 5 GB | Dashboard configurations |
| AlertManager | 5 GB | Alert history |
| **Total** | **45 GB** | Within 200 GB free tier |

## Accessing Dashboards

### Grafana

```bash
# Port-forward
kubectl port-forward -n health-observability svc/observability-grafana 3000:80

# Access: http://localhost:3000
# Default credentials (dev): admin / changeme123
```

### Prometheus

```bash
# Port-forward
kubectl port-forward -n health-observability \
  svc/observability-kube-prometheus-prometheus 9090:9090

# Access: http://localhost:9090
```

### Jaeger

```bash
# Port-forward
kubectl port-forward -n health-observability svc/jaeger-query 16686:16686

# Access: http://localhost:16686
```

### AlertManager

```bash
# Port-forward
kubectl port-forward -n health-observability \
  svc/observability-kube-prometheus-alertmanager 9093:9093

# Access: http://localhost:9093
```

## Pre-configured Dashboards

The chart includes the following Grafana dashboards:

1. **Health Platform - Application Overview**
   - Request rates (RED metrics)
   - Response times (p50, p95, p99)
   - Error rates
   - Pod status
   - Memory usage

2. **Infrastructure Health - Databases & Queues**
   - PostgreSQL status and connections
   - Redis memory usage
   - MinIO storage usage
   - RabbitMQ queue depth

3. **Cost Monitoring - Oracle Free Tier Usage**
   - Total CPU usage vs. 4 core limit
   - Total memory usage vs. 24 GB limit
   - Total storage usage vs. 200 GB limit
   - Usage breakdown by namespace

4. **Security Dashboard - Authentication & Access**
   - Authentication failures (401/403)
   - Request status codes
   - SSL certificate expiry
   - Pod restart events

5. **Kubernetes Cluster Overview** (from Grafana.com #7249)
6. **Kubernetes Pods** (from Grafana.com #6417)
7. **Node Exporter** (from Grafana.com #1860)

## ServiceMonitors

The chart creates ServiceMonitors for automatic Prometheus scraping:

- **health-api** - Health API metrics
- **webauthn-server** - WebAuthn service metrics
- **etl-narrative-engine** - ETL engine metrics
- **postgres-exporter** - PostgreSQL metrics
- **redis-exporter** - Redis metrics
- **minio** - MinIO metrics
- **rabbitmq** - RabbitMQ metrics

## Alerting Rules

Pre-configured alerts include:

### Application Alerts
- High error rate (> 5% for 5m)
- High latency (p95 > 1s for 5m)
- Pod down (< 1 replica for 1m)
- High memory usage (> 85% for 5m)

### Infrastructure Alerts
- PostgreSQL down
- Redis down
- MinIO nodes offline
- RabbitMQ down
- High disk usage (> 80%)

### Resource Alerts (Free Tier)
- CPU usage approaching limit (> 3.8 cores)
- Memory usage approaching limit (> 22 GB)
- Storage usage approaching limit (> 180 GB)

### Kubernetes Alerts
- Node not ready
- Node CPU high (> 80% for 10m)
- Node memory high (> 85% for 10m)
- PersistentVolume almost full (> 95%)

## Instrumentation Guide

### Adding Metrics to Your Service

1. Expose `/metrics` endpoint in your application
2. Create a ServiceMonitor:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-service
  namespace: my-namespace
spec:
  selector:
    matchLabels:
      app: my-service
  endpoints:
  - port: metrics
    path: /metrics
    interval: 15s
```

### Adding Distributed Tracing

Configure OpenTelemetry exporter in your application:

```python
# Python example
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint="jaeger-collector.health-observability:4317",
    insecure=True
)

# Set up tracing
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)
```

### Structured Logging for Loki

Use JSON format for logs:

```python
import json
import logging

# Configure JSON logging
logging.basicConfig(
    format='%(message)s',
    level=logging.INFO
)

# Log with structure
logging.info(json.dumps({
    "timestamp": "2025-01-19T12:00:00Z",
    "level": "info",
    "service": "my-service",
    "trace_id": "abc123",
    "message": "Request processed successfully"
}))
```

## Upgrading

```bash
# Upgrade to latest version
helm upgrade observability . \
  --namespace health-observability \
  --values values-production.yaml

# Upgrade with dependency updates
helm dependency update
helm upgrade observability . \
  --namespace health-observability \
  --values values-production.yaml
```

## Uninstalling

```bash
# Uninstall the chart
helm uninstall observability --namespace health-observability

# Delete namespace (this will delete all PVCs and data!)
kubectl delete namespace health-observability
```

**⚠️ WARNING:** Uninstalling will delete all metrics, logs, and traces. Ensure you have backups if needed.

## Backup and Restore

### Backup Grafana Dashboards

```bash
# Export all dashboards
kubectl exec -n health-observability deployment/observability-grafana -- \
  grafana-cli admin export-dashboards --homepath=/usr/share/grafana \
  > dashboards-backup.json
```

### Backup Prometheus Data

```bash
# Create snapshot
kubectl exec -n health-observability prometheus-observability-kube-prometheus-prometheus-0 -- \
  curl -XPOST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Copy snapshot
kubectl cp health-observability/prometheus-observability-kube-prometheus-prometheus-0:/prometheus/snapshots/<snapshot-id> \
  ./prometheus-backup/
```

## Troubleshooting

### Prometheus Not Scraping Targets

```bash
# Check ServiceMonitor configuration
kubectl get servicemonitors -A

# Check Prometheus logs
kubectl logs -n health-observability \
  prometheus-observability-kube-prometheus-prometheus-0 -c prometheus

# Verify target configuration in Prometheus UI
# Access: http://localhost:9090/targets
```

### Grafana Not Loading Dashboards

```bash
# Check ConfigMaps
kubectl get configmaps -n health-observability | grep dashboard

# Check Grafana logs
kubectl logs -n health-observability deployment/observability-grafana

# Restart Grafana
kubectl rollout restart deployment/observability-grafana -n health-observability
```

### Loki Not Receiving Logs

```bash
# Check Promtail pods
kubectl get pods -n health-observability | grep promtail

# Check Promtail logs
kubectl logs -n health-observability daemonset/observability-promtail

# Test Loki endpoint
kubectl exec -n health-observability deployment/observability-loki -- \
  wget -O- http://localhost:3100/ready
```

### High Resource Usage

```bash
# Check resource usage
kubectl top pods -n health-observability

# Adjust retention periods in values.yaml:
prometheus:
  prometheusSpec:
    retention: 15d  # Reduce from 30d

loki:
  loki:
    limits_config:
      retention_period: 72h  # Reduce from 168h
```

## Security Considerations

### Production Checklist

- [ ] Change default Grafana admin password
- [ ] Enable SSL/TLS for all ingresses
- [ ] Configure authentication for Grafana (LDAP/OAuth)
- [ ] Enable basic auth or OAuth for Jaeger UI
- [ ] Use NetworkPolicies to restrict access
- [ ] Encrypt secrets with Sealed Secrets or Vault
- [ ] Configure AlertManager with secure receivers
- [ ] Enable audit logging for Grafana
- [ ] Regularly rotate credentials
- [ ] Monitor certificate expiration dates

## Contributing

To modify or add dashboards:

1. Edit JSON in `templates/dashboards/*.yaml`
2. Test in development environment
3. Update version in `Chart.yaml`
4. Submit pull request

## License

This Helm chart is part of the Health Data AI Platform project.

## Support

For issues or questions:
- Check troubleshooting section above
- Review Prometheus/Grafana/Jaeger documentation
- Open issue in project repository

## References

- [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/)
