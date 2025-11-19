# Module 4: Helm Charts - Health Services
## Health API & ETL Narrative Engine Deployment

**Estimated Time:** 1 week
**Dependencies:** Modules 1-3 (Cluster, Infrastructure, WebAuthn)
**Deliverables:** Application services deployed and operational

---

## Objectives

Deploy the core application services:
1. Health API (FastAPI) - Android Health Connect data upload
2. ETL Narrative Engine - Clinical data processing pipeline
3. Configure autoscaling and resource limits
4. Set up ingress routing and SSL
5. Integrate with data layer (PostgreSQL, Redis, MinIO, RabbitMQ)

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│  health-api namespace                                   │
├────────────────────────────────────────────────────────┤
│                                                         │
│  Internet → Ingress → Health API (2-5 pods)            │
│                           │                             │
│                           ├──→ PostgreSQL (health-data) │
│                           ├──→ Redis (health)           │
│                           ├──→ MinIO (data lake)        │
│                           └──→ RabbitMQ (publish)       │
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │  ETL Narrative Engine (1-3 pods)       │            │
│  │  - Consumes from RabbitMQ              │            │
│  │  - Reads from MinIO                    │            │
│  │  - Writes to PostgreSQL                │            │
│  │  - Uses AI models for processing       │            │
│  └────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Create Health API Helm Chart

**File: `helm-charts/health-platform/charts/health-api/Chart.yaml`**

```yaml
apiVersion: v2
name: health-api
description: Health Data AI Platform - API Service
type: application
version: 1.0.0
appVersion: "1.0.0"
```

**File: `helm-charts/health-platform/charts/health-api/values.yaml`**

```yaml
namespace: health-api

replicaCount: 2

image:
  repository: ghcr.io/your-org/health-api
  tag: "latest"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8001

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"  # Large file uploads
  host: api.yourdomain.com
  tls:
    secretName: health-api-tls

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 512Mi

# Database configuration
database:
  host: postgresql-health.health-data.svc.cluster.local
  port: 5432
  name: healthdb
  user: healthapi
  # Password from secret

# Redis configuration
redis:
  host: redis-health.health-data.svc.cluster.local
  port: 6379
  # Password from secret

# MinIO configuration
minio:
  endpoint: minio.health-data.svc.cluster.local:9000
  bucket: health-data
  # Credentials from secret

# RabbitMQ configuration
rabbitmq:
  host: rabbitmq.health-data.svc.cluster.local
  port: 5672
  exchange: health-data-upload
  routingKey: raw-data
  # Credentials from secret

# WebAuthn JWT verification
webauthn:
  jwksUrl: http://webauthn-server.health-auth.svc.cluster.local:8080/.well-known/jwks.json
  issuer: https://auth.yourdomain.com

# Jaeger tracing
jaeger:
  enabled: true
  agentHost: jaeger-agent.health-observability.svc.cluster.local
  agentPort: 6831

# Application settings
app:
  logLevel: INFO
  workers: 4
  maxUploadSize: 52428800  # 50MB
  allowedOrigins: "https://app.yourdomain.com"

# Secrets (use Sealed Secrets in production)
secrets:
  database:
    password: "CHANGE_ME"
  redis:
    password: "CHANGE_ME"
  minio:
    accessKey: "CHANGE_ME"
    secretKey: "CHANGE_ME"
  rabbitmq:
    password: "CHANGE_ME"
```

**File: `helm-charts/health-platform/charts/health-api/templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: health-api
  namespace: {{ .Values.namespace }}
  labels:
    app: health-api
    version: {{ .Chart.AppVersion }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      app: health-api
  template:
    metadata:
      labels:
        app: health-api
        version: {{ .Chart.AppVersion }}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8001"
        prometheus.io/path: "/metrics"
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      serviceAccountName: health-api-sa
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      initContainers:
      - name: wait-for-db
        image: busybox:1.36
        command: ['sh', '-c', 'until nc -z {{ .Values.database.host }} {{ .Values.database.port }}; do echo waiting for db; sleep 2; done']

      containers:
      - name: health-api
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}

        ports:
        - name: http
          containerPort: 8001
          protocol: TCP

        env:
        # Database
        - name: DATABASE_URL
          value: "postgresql://{{ .Values.database.user }}:$(DB_PASSWORD)@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: health-api-secrets
              key: database-password

        # Redis
        - name: REDIS_URL
          value: "redis://:$(REDIS_PASSWORD)@{{ .Values.redis.host }}:{{ .Values.redis.port }}/0"
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: health-api-secrets
              key: redis-password

        # MinIO
        - name: S3_ENDPOINT_URL
          value: "http://{{ .Values.minio.endpoint }}"
        - name: S3_BUCKET_NAME
          value: {{ .Values.minio.bucket | quote }}
        - name: S3_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: health-api-secrets
              key: minio-access-key
        - name: S3_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: health-api-secrets
              key: minio-secret-key

        # RabbitMQ
        - name: RABBITMQ_URL
          value: "amqp://user:$(RABBITMQ_PASSWORD)@{{ .Values.rabbitmq.host }}:{{ .Values.rabbitmq.port }}/"
        - name: RABBITMQ_PASSWORD
          valueFrom:
            secretKeyRef:
              name: health-api-secrets
              key: rabbitmq-password
        - name: RABBITMQ_EXCHANGE
          value: {{ .Values.rabbitmq.exchange | quote }}
        - name: RABBITMQ_ROUTING_KEY
          value: {{ .Values.rabbitmq.routingKey | quote }}

        # WebAuthn
        - name: JWKS_URL
          value: {{ .Values.webauthn.jwksUrl | quote }}
        - name: JWT_ISSUER
          value: {{ .Values.webauthn.issuer | quote }}

        # Jaeger
        {{- if .Values.jaeger.enabled }}
        - name: JAEGER_AGENT_HOST
          value: {{ .Values.jaeger.agentHost | quote }}
        - name: JAEGER_AGENT_PORT
          value: {{ .Values.jaeger.agentPort | quote }}
        {{- end }}

        # App config
        - name: LOG_LEVEL
          value: {{ .Values.app.logLevel | quote }}
        - name: WORKERS
          value: {{ .Values.app.workers | quote }}
        - name: MAX_UPLOAD_SIZE
          value: {{ .Values.app.maxUploadSize | quote }}
        - name: ALLOWED_ORIGINS
          value: {{ .Values.app.allowedOrigins | quote }}

        livenessProbe:
          httpGet:
            path: /health/live
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5

        readinessProbe:
          httpGet:
            path: /health/ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3

        resources:
          {{- toYaml .Values.resources | nindent 12 }}

        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
          readOnlyRootFilesystem: true

        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /app/.cache

      volumes:
      - name: tmp
        emptyDir: {}
      - name: cache
        emptyDir: {}
```

### Step 2: Create ETL Narrative Engine Helm Chart

**File: `helm-charts/health-platform/charts/etl-engine/Chart.yaml`**

```yaml
apiVersion: v2
name: etl-engine
description: ETL Narrative Engine - Clinical data processing
type: application
version: 1.0.0
appVersion: "1.0.0"
```

**File: `helm-charts/health-platform/charts/etl-engine/values.yaml`**

```yaml
namespace: health-etl

replicaCount: 1

image:
  repository: ghcr.io/your-org/etl-narrative-engine
  tag: "latest"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8002

resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 2000m  # Higher for AI model processing
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 70
  # Scale based on RabbitMQ queue depth
  custom:
    - type: External
      external:
        metricName: rabbitmq_queue_messages
        targetValue: 100

# Database (same as health-api)
database:
  host: postgresql-health.health-data.svc.cluster.local
  port: 5432
  name: healthdb
  user: healthapi

# MinIO
minio:
  endpoint: minio.health-data.svc.cluster.local:9000
  bucket: health-data
  processedBucket: processed-data

# RabbitMQ (consumer)
rabbitmq:
  host: rabbitmq.health-data.svc.cluster.local
  port: 5672
  queue: health-data-processing
  prefetchCount: 1  # Process one at a time

# AI Model configuration
aiModel:
  modelPath: /models/clinical-narrative
  cachePath: /app/.cache/huggingface
  maxTokens: 2048
  temperature: 0.7

secrets:
  database:
    password: "CHANGE_ME"
  minio:
    accessKey: "CHANGE_ME"
    secretKey: "CHANGE_ME"
  rabbitmq:
    password: "CHANGE_ME"
```

**File: `helm-charts/health-platform/charts/etl-engine/templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: etl-engine
  namespace: {{ .Values.namespace }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      app: etl-engine
  template:
    metadata:
      labels:
        app: etl-engine
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8002"
    spec:
      serviceAccountName: etl-engine-sa

      containers:
      - name: etl-engine
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}

        ports:
        - name: http
          containerPort: 8002

        env:
        # Database
        - name: DATABASE_URL
          value: "postgresql://{{ .Values.database.user }}:$(DB_PASSWORD)@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: etl-engine-secrets
              key: database-password

        # MinIO
        - name: S3_ENDPOINT_URL
          value: "http://{{ .Values.minio.endpoint }}"
        - name: S3_BUCKET_NAME
          value: {{ .Values.minio.bucket | quote }}
        - name: S3_PROCESSED_BUCKET
          value: {{ .Values.minio.processedBucket | quote }}
        - name: S3_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: etl-engine-secrets
              key: minio-access-key
        - name: S3_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: etl-engine-secrets
              key: minio-secret-key

        # RabbitMQ
        - name: RABBITMQ_URL
          value: "amqp://user:$(RABBITMQ_PASSWORD)@{{ .Values.rabbitmq.host }}:{{ .Values.rabbitmq.port }}/"
        - name: RABBITMQ_PASSWORD
          valueFrom:
            secretKeyRef:
              name: etl-engine-secrets
              key: rabbitmq-password
        - name: RABBITMQ_QUEUE
          value: {{ .Values.rabbitmq.queue | quote }}
        - name: RABBITMQ_PREFETCH_COUNT
          value: {{ .Values.rabbitmq.prefetchCount | quote }}

        # AI Model
        - name: MODEL_PATH
          value: {{ .Values.aiModel.modelPath | quote }}
        - name: TRANSFORMERS_CACHE
          value: {{ .Values.aiModel.cachePath | quote }}

        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 60  # Model loading takes time
          periodSeconds: 30

        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10

        resources:
          {{- toYaml .Values.resources | nindent 12 }}

        volumeMounts:
        - name: model-cache
          mountPath: /app/.cache
        - name: tmp
          mountPath: /tmp

      volumes:
      - name: model-cache
        emptyDir:
          sizeLimit: 5Gi
      - name: tmp
        emptyDir: {}
```

### Step 3: Create Supporting Resources

**File: `helm-charts/health-platform/charts/health-api/templates/hpa.yaml`**

```yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: health-api-hpa
  namespace: {{ .Values.namespace }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: health-api
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
{{- end }}
```

**File: `helm-charts/health-platform/charts/health-api/templates/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: health-api
  namespace: {{ .Values.namespace }}
  labels:
    app: health-api
spec:
  type: {{ .Values.service.type }}
  ports:
  - port: {{ .Values.service.port }}
    targetPort: http
    protocol: TCP
    name: http
  selector:
    app: health-api
```

**File: `helm-charts/health-platform/charts/health-api/templates/ingress.yaml`**

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: health-api-ingress
  namespace: {{ .Values.namespace }}
  annotations:
    {{- toYaml .Values.ingress.annotations | nindent 4 }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  tls:
  - hosts:
    - {{ .Values.ingress.host }}
    secretName: {{ .Values.ingress.tls.secretName }}
  rules:
  - host: {{ .Values.ingress.host }}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: health-api
            port:
              number: {{ .Values.service.port }}
{{- end }}
```

---

## Deployment

```bash
# 1. Build and push Docker images
docker build -t ghcr.io/your-org/health-api:latest ./services/health-api-service
docker push ghcr.io/your-org/health-api:latest

docker build -t ghcr.io/your-org/etl-narrative-engine:latest ./services/etl-narrative-engine
docker push ghcr.io/your-org/etl-narrative-engine:latest

# 2. Create namespaces
kubectl create namespace health-api
kubectl create namespace health-etl

# 3. Deploy Health API
helm install health-api ./helm-charts/health-platform/charts/health-api \
  --namespace health-api \
  --values ./helm-charts/health-platform/values-production.yaml

# 4. Deploy ETL Engine
helm install etl-engine ./helm-charts/health-platform/charts/etl-engine \
  --namespace health-etl \
  --values ./helm-charts/health-platform/values-production.yaml

# 5. Verify
kubectl get pods -n health-api
kubectl get pods -n health-etl
kubectl get ingress -n health-api
```

---

## Testing

```bash
# Test Health API endpoint
curl -X POST https://api.yourdomain.com/upload \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d @sample-health-data.json

# Check autoscaling
kubectl get hpa -n health-api

# Load test
ab -n 1000 -c 10 -H "Authorization: Bearer <TOKEN>" \
  https://api.yourdomain.com/health/ready

# Watch pods scale
kubectl get pods -n health-api -w

# Check ETL processing
kubectl logs -f deployment/etl-engine -n health-etl

# Check RabbitMQ queue
kubectl exec -it rabbitmq-0 -n health-data -- rabbitmqctl list_queues
```

---

## Success Criteria

- [ ] Health API pods running (2-5 replicas based on load)
- [ ] ETL Engine pods running (1-3 based on queue depth)
- [ ] Ingress routing to Health API with SSL
- [ ] Health API can upload data to MinIO
- [ ] Health API publishes messages to RabbitMQ
- [ ] ETL Engine consumes messages from RabbitMQ
- [ ] ETL Engine processes data and stores in PostgreSQL
- [ ] HPA scaling based on CPU/memory
- [ ] All health checks passing
- [ ] Jaeger traces showing end-to-end flow

---

## Optional Enhancement: Carbon Emissions Tracking

This section describes how to add carbon footprint monitoring to the ETL Narrative Engine using CodeCarbon, aligning with the platform's sustainability goals (Oracle EU 100% renewable energy).

### Overview

**Why Track Carbon Emissions?**
- **Visibility**: Measure the environmental impact of AI model inference
- **Optimization**: Identify energy-intensive models for replacement or optimization
- **Compliance**: Report carbon metrics for sustainability certifications
- **Cost Management**: Energy efficiency correlates with reduced cloud costs
- **Right-sizing**: Use emissions data to optimize resource allocations

**Expected Impact:**
- Typical clinical narrative generation: ~0.00002 kg CO2e per inference
- Daily processing (10,000 narratives): ~0.2 kg CO2e
- Annual footprint: ~73 kg CO2e (equivalent to driving 290 km in a gasoline car)

### Step 1: Add CodeCarbon Dependency

**File: `services/etl-narrative-engine/requirements.txt`**

Add the following dependency:

```txt
codecarbon==3.0.1
```

### Step 2: Update ETL Engine Helm Values

**File: `helm-charts/health-platform/charts/etl-engine/values.yaml`**

Add the following configuration section after `aiModel`:

```yaml
# CodeCarbon configuration (optional)
codecarbon:
  enabled: true
  projectName: "etl-narrative-engine"
  # Oracle OCI EU regions use 100% renewable energy
  countryIsoCode: "NLD"  # Netherlands (example for EU deployment)
  # Expose carbon metrics to Prometheus
  prometheusEnabled: true
  prometheusPort: 8003
  # Track emissions per run
  trackMode: "machine"  # Tracks actual hardware energy usage
  # Output directory for emissions logs
  outputDir: "/app/emissions"
  # Save emissions to API (optional - set if using CodeCarbon dashboard)
  saveToApi: false
```

### Step 3: Update ETL Engine Deployment

**File: `helm-charts/health-platform/charts/etl-engine/templates/deployment.yaml`**

Add the following environment variables in the `env` section:

```yaml
        # CodeCarbon Configuration (if enabled)
        {{- if .Values.codecarbon.enabled }}
        - name: CODECARBON_ENABLED
          value: "true"
        - name: CODECARBON_PROJECT_NAME
          value: {{ .Values.codecarbon.projectName | quote }}
        - name: CODECARBON_COUNTRY_ISO_CODE
          value: {{ .Values.codecarbon.countryIsoCode | quote }}
        - name: CODECARBON_TRACK_MODE
          value: {{ .Values.codecarbon.trackMode | quote }}
        - name: CODECARBON_OUTPUT_DIR
          value: {{ .Values.codecarbon.outputDir | quote }}
        - name: CODECARBON_SAVE_TO_API
          value: {{ .Values.codecarbon.saveToApi | quote }}
        {{- end }}
```

Add an additional port for Prometheus metrics in the `ports` section:

```yaml
        {{- if .Values.codecarbon.prometheusEnabled }}
        - name: carbon-metrics
          containerPort: {{ .Values.codecarbon.prometheusPort }}
          protocol: TCP
        {{- end }}
```

Add a volume mount for emissions logs:

```yaml
        volumeMounts:
        # ... existing mounts ...
        {{- if .Values.codecarbon.enabled }}
        - name: emissions-logs
          mountPath: {{ .Values.codecarbon.outputDir }}
        {{- end }}
```

Add a volume definition:

```yaml
      volumes:
      # ... existing volumes ...
      {{- if .Values.codecarbon.enabled }}
      - name: emissions-logs
        emptyDir:
          sizeLimit: 1Gi
      {{- end }}
```

### Step 4: Application Code Integration

**File: `services/etl-narrative-engine/src/processor.py`**

Example integration into the ETL Narrative Engine:

```python
import os
from codecarbon import EmissionsTracker
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class NarrativeProcessor:
    def __init__(self):
        self.codecarbon_enabled = os.getenv("CODECARBON_ENABLED", "false").lower() == "true"
        self.tracker: Optional[EmissionsTracker] = None

        if self.codecarbon_enabled:
            self.tracker = EmissionsTracker(
                project_name=os.getenv("CODECARBON_PROJECT_NAME", "etl-narrative-engine"),
                country_iso_code=os.getenv("CODECARBON_COUNTRY_ISO_CODE", "NLD"),
                tracking_mode=os.getenv("CODECARBON_TRACK_MODE", "machine"),
                output_dir=os.getenv("CODECARBON_OUTPUT_DIR", "/app/emissions"),
                save_to_api=os.getenv("CODECARBON_SAVE_TO_API", "false").lower() == "true",
                log_level="warning",  # Reduce noise in logs
            )
            logger.info("CodeCarbon emissions tracking enabled")

    async def process_message(self, message: dict):
        """Process a single health data message and generate clinical narrative."""

        # Start carbon tracking for this narrative generation
        if self.tracker:
            self.tracker.start()

        try:
            # Your existing ETL processing logic
            raw_data = await self.fetch_from_minio(message["object_key"])
            parsed_data = await self.parse_health_data(raw_data)

            # AI model inference (this is what we're measuring)
            narrative = await self.generate_narrative(parsed_data)

            # Store results
            await self.store_narrative(narrative)

            # Stop tracking and get emissions
            if self.tracker:
                emissions = self.tracker.stop()
                logger.info(
                    f"Narrative generated. Carbon emissions: {emissions:.8f} kg CO2e"
                )

                # Optionally emit custom Prometheus metric
                self.emit_carbon_metric(emissions)

            return narrative

        except Exception as e:
            if self.tracker:
                self.tracker.stop()
            raise e

    def emit_carbon_metric(self, emissions: float):
        """Emit carbon emissions as a Prometheus metric."""
        # This is a simplified example - integrate with your Prometheus client
        from prometheus_client import Counter

        carbon_emissions_counter = Counter(
            'etl_carbon_emissions_kg_co2e_total',
            'Total carbon emissions from ETL processing in kg CO2e'
        )
        carbon_emissions_counter.inc(emissions)
```

**File: `services/etl-narrative-engine/src/main.py`**

Expose Prometheus metrics endpoint:

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI()

# Mount Prometheus metrics endpoint
if os.getenv("CODECARBON_ENABLED", "false").lower() == "true":
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
```

### Step 5: Create Prometheus ServiceMonitor

**File: `helm-charts/health-platform/charts/etl-engine/templates/servicemonitor.yaml`**

```yaml
{{- if and .Values.codecarbon.enabled .Values.codecarbon.prometheusEnabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: etl-engine-carbon-metrics
  namespace: {{ .Values.namespace }}
  labels:
    app: etl-engine
    prometheus: kube-prometheus
spec:
  selector:
    matchLabels:
      app: etl-engine
  endpoints:
  - port: carbon-metrics
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
{{- end }}
```

**File: `helm-charts/health-platform/charts/etl-engine/templates/service.yaml`**

Add the carbon metrics port to the Service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: etl-engine
  namespace: {{ .Values.namespace }}
  labels:
    app: etl-engine
spec:
  type: {{ .Values.service.type }}
  ports:
  - port: {{ .Values.service.port }}
    targetPort: http
    protocol: TCP
    name: http
  {{- if and .Values.codecarbon.enabled .Values.codecarbon.prometheusEnabled }}
  - port: {{ .Values.codecarbon.prometheusPort }}
    targetPort: carbon-metrics
    protocol: TCP
    name: carbon-metrics
  {{- end }}
  selector:
    app: etl-engine
```

### Step 6: Create Grafana Dashboard

Add the following dashboard panel to your Grafana dashboard for the ETL Narrative Engine.

**File: `helm-charts/observability/grafana-dashboards/etl-carbon-emissions.json`**

```json
{
  "dashboard": {
    "title": "ETL Narrative Engine - Carbon Emissions",
    "panels": [
      {
        "title": "Total Carbon Emissions (kg CO2e)",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(etl_carbon_emissions_kg_co2e_total)",
            "legendFormat": "Total CO2e"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "kg CO2e",
            "decimals": 6
          }
        }
      },
      {
        "title": "Carbon Emissions Rate (kg CO2e/hour)",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(etl_carbon_emissions_kg_co2e_total[1h]) * 3600",
            "legendFormat": "Emissions Rate"
          }
        ],
        "yaxes": [
          {
            "format": "kg CO2e/h"
          }
        ]
      },
      {
        "title": "Carbon Emissions per Narrative (avg)",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(etl_carbon_emissions_kg_co2e_total[5m]) / rate(etl_narratives_generated_total[5m])",
            "legendFormat": "CO2e per narrative"
          }
        ],
        "yaxes": [
          {
            "format": "kg CO2e"
          }
        ]
      },
      {
        "title": "Carbon Intensity by Time of Day",
        "type": "heatmap",
        "targets": [
          {
            "expr": "rate(etl_carbon_emissions_kg_co2e_total[1h])",
            "legendFormat": "{{ hour }}"
          }
        ]
      }
    ]
  }
}
```

ConfigMap for Grafana dashboard (add to observability module):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: etl-carbon-dashboard
  namespace: health-observability
  labels:
    grafana_dashboard: "1"
data:
  etl-carbon-emissions.json: |-
    # ... paste the JSON above ...
```

### Step 7: Testing the Integration

**1. Deploy with CodeCarbon Enabled:**

```bash
# Update values file
helm upgrade etl-engine ./helm-charts/health-platform/charts/etl-engine \
  --namespace health-etl \
  --set codecarbon.enabled=true \
  --set codecarbon.prometheusEnabled=true

# Verify pod is running
kubectl get pods -n health-etl
```

**2. Verify Carbon Tracking in Logs:**

```bash
# Check that CodeCarbon is initialized
kubectl logs -f deployment/etl-engine -n health-etl | grep -i "codecarbon\|emissions"

# Expected output:
# [INFO] CodeCarbon emissions tracking enabled
# [INFO] Narrative generated. Carbon emissions: 0.00002134 kg CO2e
```

**3. Verify Prometheus Metrics:**

```bash
# Port-forward to carbon metrics endpoint
kubectl port-forward -n health-etl svc/etl-engine 8003:8003

# Query metrics
curl http://localhost:8003/metrics | grep etl_carbon

# Expected output:
# etl_carbon_emissions_kg_co2e_total 0.000427
```

**4. Verify Grafana Dashboard:**

```bash
# Access Grafana
kubectl port-forward -n health-observability svc/kube-prometheus-stack-grafana 3000:80

# Navigate to Dashboards → ETL Narrative Engine - Carbon Emissions
# You should see:
# - Total cumulative emissions
# - Emissions rate over time
# - Average emissions per narrative
```

**5. Load Test to Generate Metrics:**

```bash
# Generate sample health data processing tasks
for i in {1..100}; do
  # Publish message to RabbitMQ queue
  kubectl exec -n health-data rabbitmq-0 -- \
    rabbitmqadmin publish exchange=health-data-upload \
    routing_key=raw-data \
    payload='{"object_key":"test-data-'$i'.json","user_id":"test-user"}'
  sleep 1
done

# Watch emissions accumulate
kubectl logs -f deployment/etl-engine -n health-etl | grep "Carbon emissions"
```

**6. Verify Emissions Data File:**

```bash
# Check emissions log file
kubectl exec -n health-etl deployment/etl-engine -- \
  cat /app/emissions/emissions.csv

# Expected format:
# timestamp,project_name,duration,emissions,energy_consumed,country_iso_code
# 2025-11-19 12:34:56,etl-narrative-engine,2.3,0.00002,0.00005,NLD
```

### Sample Metrics and Benchmarks

**Expected Carbon Footprint:**

| Scenario | Emissions (kg CO2e) | Energy (kWh) |
|----------|---------------------|--------------|
| Single narrative (small model) | 0.00002 | 0.00005 |
| Single narrative (large model) | 0.00008 | 0.0002 |
| 1,000 narratives/day | 0.02-0.08 | 0.05-0.2 |
| 10,000 narratives/day | 0.2-0.8 | 0.5-2.0 |
| Annual (3.65M narratives) | 73-292 kg | 183-730 kWh |

**Comparison (Annual Basis):**
- **ETL Engine Carbon Footprint**: ~73-292 kg CO2e/year
- **Equivalent to**: Driving 290-1,160 km in a gasoline car
- **Context**: Oracle OCI EU regions use 100% renewable energy, so actual impact is offset

**Optimization Opportunities:**

If carbon emissions exceed expected values:
1. **Model Selection**: Switch to smaller, more efficient models (e.g., DistilBERT instead of BERT)
2. **Batch Processing**: Process multiple narratives in a single model inference call
3. **Resource Right-sizing**: Reduce CPU/memory limits if over-provisioned
4. **Regional Migration**: Move to data centers with lower carbon intensity (if not using renewable energy)
5. **Inference Optimization**: Use quantization, pruning, or knowledge distillation

### Success Criteria

**CodeCarbon Integration:**
- [ ] CodeCarbon dependency added to `requirements.txt`
- [ ] Helm values configured with carbon tracking settings
- [ ] ETL Engine deployment updated with CodeCarbon environment variables
- [ ] Emissions logs being written to `/app/emissions/` directory
- [ ] Prometheus ServiceMonitor scraping carbon metrics
- [ ] Grafana dashboard showing carbon emissions data
- [ ] Per-narrative emissions logged (visible in pod logs)
- [ ] Total cumulative emissions metric available in Prometheus
- [ ] Carbon tracking does not impact processing performance (< 1% overhead)
- [ ] Emissions data aligns with expected benchmarks (0.00002-0.00008 kg CO2e per narrative)

---

**Module 4 Complete**: Application services deployed
