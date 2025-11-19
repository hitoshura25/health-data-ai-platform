# Module 5: Observability Stack
## Prometheus, Grafana, Jaeger, Loki Deployment

**Estimated Time:** 1 week
**Dependencies:** Module 1 (OKE cluster running)
**Deliverables:** Complete monitoring, logging, and tracing infrastructure

---

## Objectives

Deploy comprehensive observability stack:
1. Prometheus - Metrics collection and alerting
2. Grafana - Visualization dashboards
3. Jaeger - Distributed tracing (integrate existing instance)
4. Loki + Promtail - Log aggregation
5. AlertManager - Alert routing
6. Pre-configured dashboards for all services

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│  health-observability namespace                         │
├────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  Prometheus  │◄─────│ServiceMonitor│               │
│  │              │      │  (auto-disc)  │               │
│  │  - Scrapes   │      └──────────────┘               │
│  │    metrics   │                                       │
│  │  - 30d ret.  │                                       │
│  │  - 20GB PVC  │                                       │
│  └──────┬───────┘                                       │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐      ┌──────────────┐               │
│  │   Grafana    │◄─────│  Dashboards  │               │
│  │              │      │  (pre-conf)   │               │
│  │  - Ingress   │      └──────────────┘               │
│  │  - Auth      │                                       │
│  └──────────────┘                                       │
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │    Jaeger    │◄─────│ All Services │               │
│  │  (existing)  │      │ (OTLP trace) │               │
│  └──────────────┘      └──────────────┘               │
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │     Loki     │◄─────│   Promtail   │               │
│  │  (log store) │      │  (DaemonSet) │               │
│  │  - 7d ret.   │      └──────────────┘               │
│  │  - 5GB PVC   │                                       │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Install kube-prometheus-stack

```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create namespace
kubectl create namespace health-observability

# Create values file
cat > prometheus-values.yaml <<EOF
# kube-prometheus-stack configuration

prometheus:
  prometheusSpec:
    retention: 30d
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: oci-bv
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 20Gi

    resources:
      requests:
        cpu: 500m
        memory: 2Gi
      limits:
        cpu: 1000m
        memory: 4Gi

    # Service discovery
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false

    # External labels
    externalLabels:
      cluster: health-platform-prod
      environment: production

grafana:
  enabled: true

  adminPassword: "CHANGE_ME_STRONG_PASSWORD"

  persistence:
    enabled: true
    storageClassName: oci-bv
    size: 5Gi

  ingress:
    enabled: true
    ingressClassName: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
    hosts:
      - grafana.yourdomain.com
    tls:
      - secretName: grafana-tls
        hosts:
          - grafana.yourdomain.com

  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi

  # Pre-configured datasources
  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
      - name: Prometheus
        type: prometheus
        url: http://prometheus-kube-prometheus-prometheus:9090
        access: proxy
        isDefault: true

      - name: Loki
        type: loki
        url: http://loki:3100
        access: proxy

      - name: Jaeger
        type: jaeger
        url: http://jaeger-query.health-observability:16686
        access: proxy

  # Dashboard providers
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
      - name: 'default'
        orgId: 1
        folder: ''
        type: file
        disableDeletion: false
        editable: true
        options:
          path: /var/lib/grafana/dashboards/default

  # Pre-load dashboards
  dashboards:
    default:
      kubernetes-cluster:
        gnetId: 7249
        revision: 1
        datasource: Prometheus

      kubernetes-pods:
        gnetId: 6417
        revision: 1
        datasource: Prometheus

      postgresql:
        gnetId: 9628
        revision: 7
        datasource: Prometheus

      redis:
        gnetId: 11835
        revision: 1
        datasource: Prometheus

alertmanager:
  enabled: true

  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: oci-bv
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 5Gi

    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 200m
        memory: 256Mi

  config:
    global:
      resolve_timeout: 5m

    route:
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'default'
      routes:
      - match:
          severity: critical
        receiver: critical
        continue: true

    receivers:
    - name: 'default'
      webhook_configs:
      - url: 'http://localhost:5001'  # Replace with your webhook

    - name: 'critical'
      # Add Slack, PagerDuty, email, etc.
      webhook_configs:
      - url: 'http://localhost:5001'

# Node exporter
prometheus-node-exporter:
  enabled: true

# Kube-state-metrics
kube-state-metrics:
  enabled: true
EOF

# Install
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace health-observability \
  --values prometheus-values.yaml

# Verify
kubectl get pods -n health-observability
```

### Step 2: Install Loki Stack

```bash
# Add Grafana Helm repo
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Create values file
cat > loki-values.yaml <<EOF
loki:
  auth_enabled: false

  storage:
    type: filesystem

  commonConfig:
    replication_factor: 1

  persistence:
    enabled: true
    storageClassName: oci-bv
    size: 5Gi

  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 400m
      memory: 1Gi

  # Retention
  limits_config:
    retention_period: 168h  # 7 days

promtail:
  enabled: true

  config:
    clients:
      - url: http://loki:3100/loki/api/v1/push

    snippets:
      pipelineStages:
        - docker: {}
        - json:
            expressions:
              level: level
              msg: msg
        - labels:
            level:

  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi

grafana:
  enabled: false  # Using Grafana from kube-prometheus-stack
EOF

# Install
helm install loki grafana/loki-stack \
  --namespace health-observability \
  --values loki-values.yaml

# Verify
kubectl get pods -n health-observability | grep loki
kubectl get pods -n health-observability | grep promtail
```

### Step 3: Deploy Jaeger

```bash
# Create Jaeger deployment
cat > jaeger-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: health-observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
      - name: jaeger
        image: jaegertracing/all-in-one:1.52
        ports:
        - containerPort: 5775
          protocol: UDP
        - containerPort: 6831
          protocol: UDP
        - containerPort: 6832
          protocol: UDP
        - containerPort: 5778
          protocol: TCP
        - containerPort: 16686
          protocol: TCP
        - containerPort: 14250
          protocol: TCP
        - containerPort: 14268
          protocol: TCP
        - containerPort: 14269
          protocol: TCP
        - containerPort: 4317  # OTLP gRPC
          protocol: TCP
        - containerPort: 4318  # OTLP HTTP
          protocol: TCP
        env:
        - name: COLLECTOR_OTLP_ENABLED
          value: "true"
        - name: SPAN_STORAGE_TYPE
          value: badger
        - name: BADGER_EPHEMERAL
          value: "false"
        - name: BADGER_DIRECTORY_VALUE
          value: /badger/data
        - name: BADGER_DIRECTORY_KEY
          value: /badger/key
        resources:
          requests:
            cpu: 300m
            memory: 512Mi
          limits:
            cpu: 500m
            memory: 1Gi
        volumeMounts:
        - name: badger-data
          mountPath: /badger
      volumes:
      - name: badger-data
        persistentVolumeClaim:
          claimName: jaeger-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jaeger-pvc
  namespace: health-observability
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: oci-bv
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-agent
  namespace: health-observability
spec:
  type: ClusterIP
  ports:
  - port: 6831
    protocol: UDP
    name: jaeger-compact
  - port: 6832
    protocol: UDP
    name: jaeger-binary
  - port: 5778
    protocol: TCP
    name: jaeger-config
  selector:
    app: jaeger
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-query
  namespace: health-observability
spec:
  type: ClusterIP
  ports:
  - port: 16686
    protocol: TCP
    name: jaeger-ui
  selector:
    app: jaeger
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-collector
  namespace: health-observability
spec:
  type: ClusterIP
  ports:
  - port: 14250
    protocol: TCP
    name: jaeger-grpc
  - port: 14268
    protocol: TCP
    name: jaeger-http
  - port: 4317
    protocol: TCP
    name: otlp-grpc
  - port: 4318
    protocol: TCP
    name: otlp-http
  selector:
    app: jaeger
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: jaeger-ingress
  namespace: health-observability
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - jaeger.yourdomain.com
    secretName: jaeger-tls
  rules:
  - host: jaeger.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: jaeger-query
            port:
              number: 16686
EOF

kubectl apply -f jaeger-deployment.yaml
```

### Step 4: Create Custom Dashboards

**Health API Dashboard (`health-api-dashboard.json`):**

```json
{
  "dashboard": {
    "title": "Health API Overview",
    "tags": ["health-api"],
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"health-api\"}[5m])"
          }
        ]
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job=\"health-api\"}[5m]))"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"health-api\",status=~\"5..\"}[5m])"
          }
        ]
      },
      {
        "title": "Active Pods",
        "targets": [
          {
            "expr": "count(kube_pod_status_phase{namespace=\"health-api\",phase=\"Running\"})"
          }
        ]
      }
    ]
  }
}
```

### Step 5: Configure Alerting Rules

```yaml
# alerting-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: health-platform-alerts
  namespace: health-observability
spec:
  groups:
  - name: health-api
    interval: 30s
    rules:
    - alert: HealthAPIHighErrorRate
      expr: rate(http_requests_total{job="health-api",status=~"5.."}[5m]) > 0.05
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High error rate on Health API"
        description: "Error rate is {{ $value }} errors/sec"

    - alert: HealthAPIHighLatency
      expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="health-api"}[5m])) > 1
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High latency on Health API"
        description: "p95 latency is {{ $value }}s"

    - alert: HealthAPIPodDown
      expr: kube_deployment_status_replicas_available{namespace="health-api"} < 1
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "No Health API pods available"

  - name: infrastructure
    interval: 30s
    rules:
    - alert: PostgreSQLDown
      expr: pg_up == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "PostgreSQL is down"

    - alert: RedisDown
      expr: redis_up == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Redis is down"

    - alert: DiskSpaceHigh
      expr: (kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes) > 0.8
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Disk usage above 80%"
        description: "{{ $labels.persistentvolumeclaim }} is {{ $value | humanizePercentage }} full"

    - alert: NodeCPUHigh
      expr: (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)) > 0.8
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Node CPU usage high"
        description: "CPU usage is {{ $value | humanizePercentage }}"
```

---

## Access Dashboards

```bash
# Grafana
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n health-observability
# Open: http://localhost:3000
# Login: admin / <password from values>

# Prometheus
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n health-observability
# Open: http://localhost:9090

# Jaeger
kubectl port-forward svc/jaeger-query 16686:16686 -n health-observability
# Open: http://localhost:16686

# AlertManager
kubectl port-forward svc/kube-prometheus-stack-alertmanager 9093:9093 -n health-observability
# Open: http://localhost:9093
```

---

## Verification

```bash
# Check all pods running
kubectl get pods -n health-observability

# Expected output:
# kube-prometheus-stack-prometheus-0          2/2     Running
# kube-prometheus-stack-grafana-xxx           3/3     Running
# kube-prometheus-stack-alertmanager-0        2/2     Running
# loki-0                                      1/1     Running
# promtail-xxx                                1/1     Running (on each node)
# jaeger-xxx                                  1/1     Running

# Check ServiceMonitors
kubectl get servicemonitors -A

# Check PrometheusRules
kubectl get prometheusrules -n health-observability

# Test metrics scraping
kubectl exec -it kube-prometheus-stack-prometheus-0 -n health-observability -c prometheus -- \
  wget -O- http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job:.labels.job, health:.health}'
```

---

## Success Criteria

- [ ] Prometheus scraping all ServiceMonitors
- [ ] Grafana accessible with pre-loaded dashboards
- [ ] Jaeger receiving traces from all services
- [ ] Loki aggregating logs from all pods
- [ ] AlertManager configured and routing alerts
- [ ] Storage: 40 GB total (20+10+5+5 within 200 GB free tier)
- [ ] All dashboards showing live data
- [ ] Alerts firing for test conditions

---

**Module 5 Complete**: Full observability stack operational
