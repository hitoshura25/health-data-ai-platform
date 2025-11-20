# ETL Narrative Engine Helm Chart

Helm chart for deploying the ETL Narrative Engine - Clinical data processing pipeline to Kubernetes.

## Overview

This chart deploys the ETL Narrative Engine service, which processes raw health data from RabbitMQ, generates clinical narratives using AI models, and stores the results. The service integrates with:

- **RabbitMQ**: For consuming health data messages
- **MinIO**: For reading raw data and writing processed data
- **PostgreSQL**: For storing processed narratives and metadata
- **Jaeger**: For distributed tracing

## Prerequisites

- Kubernetes 1.24+
- Helm 3.13+
- PersistentVolume provisioner support (for deduplication database)
- RabbitMQ message queue
- MinIO object storage
- PostgreSQL database

## Installing the Chart

### Development Installation

```bash
# Create namespace
kubectl create namespace health-etl

# Install with default values
helm install etl-engine . \
  --namespace health-etl \
  --create-namespace
```

### Production Installation

```bash
# Create namespace
kubectl create namespace health-etl

# Install with production values
helm install etl-engine . \
  --namespace health-etl \
  --values values-production.yaml \
  --set image.tag=v1.0.0
```

## Configuration

The following table lists the configurable parameters of the ETL Engine chart and their default values.

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | ETL Engine image repository | `ghcr.io/your-org/etl-narrative-engine` |
| `image.tag` | ETL Engine image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |

### Deployment Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace` | Kubernetes namespace | `health-etl` |
| `replicaCount` | Number of replicas | `1` |
| `autoscaling.enabled` | Enable HorizontalPodAutoscaler | `true` |
| `autoscaling.minReplicas` | Minimum replicas | `1` |
| `autoscaling.maxReplicas` | Maximum replicas | `3` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization | `70` |
| `autoscaling.targetMemoryUtilizationPercentage` | Target memory utilization | `80` |

### Resource Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.requests.cpu` | CPU request | `200m` |
| `resources.requests.memory` | Memory request | `512Mi` |
| `resources.limits.cpu` | CPU limit | `2000m` |
| `resources.limits.memory` | Memory limit | `2Gi` |

**Note**: Higher CPU/memory limits are required for AI model inference.

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Kubernetes service type | `ClusterIP` |
| `service.port` | Service port | `8002` |
| `service.metricsPort` | Metrics port | `8004` |

### Database Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database.host` | PostgreSQL host | `postgresql-health.health-data.svc.cluster.local` |
| `database.port` | PostgreSQL port | `5432` |
| `database.name` | Database name | `healthdb` |
| `database.user` | Database user | `healthapi` |
| `secrets.database.password` | Database password (use Sealed Secrets) | `CHANGE_ME` |

### MinIO Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `minio.endpoint` | MinIO endpoint | `minio.health-data.svc.cluster.local:9000` |
| `minio.bucket` | Raw data bucket | `health-data` |
| `minio.processedBucket` | Processed data bucket | `processed-data` |
| `secrets.minio.accessKey` | MinIO access key (use Sealed Secrets) | `CHANGE_ME` |
| `secrets.minio.secretKey` | MinIO secret key (use Sealed Secrets) | `CHANGE_ME` |

### RabbitMQ Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `rabbitmq.host` | RabbitMQ host | `rabbitmq.health-data.svc.cluster.local` |
| `rabbitmq.port` | RabbitMQ port | `5672` |
| `rabbitmq.queue` | RabbitMQ queue name | `health-data-processing` |
| `rabbitmq.prefetchCount` | Message prefetch count | `1` |
| `secrets.rabbitmq.user` | RabbitMQ user | `user` |
| `secrets.rabbitmq.password` | RabbitMQ password (use Sealed Secrets) | `CHANGE_ME` |

### ETL Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `etl.logLevel` | Log level | `INFO` |
| `etl.enableMetrics` | Enable Prometheus metrics | `true` |
| `etl.deduplicationStore` | Deduplication store type | `sqlite` |
| `etl.deduplicationDbPath` | Deduplication DB path | `/data/etl_processed_messages.db` |

### AI Model Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `aiModel.modelPath` | Model path | `/models/clinical-narrative` |
| `aiModel.cachePath` | HuggingFace cache path | `/app/.cache/huggingface` |
| `aiModel.maxTokens` | Max tokens for generation | `2048` |
| `aiModel.temperature` | Model temperature | `0.7` |

### Persistence Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persistence.enabled` | Enable persistence for deduplication DB | `true` |
| `persistence.storageClass` | Storage class | `oci-bv` |
| `persistence.accessMode` | Access mode | `ReadWriteOnce` |
| `persistence.size` | Volume size | `1Gi` |
| `persistence.mountPath` | Mount path | `/data` |

## Upgrading

```bash
# Upgrade with new values
helm upgrade etl-engine . \
  --namespace health-etl \
  --values values-production.yaml \
  --set image.tag=v1.1.0
```

## Uninstalling

```bash
helm uninstall etl-engine --namespace health-etl
```

**⚠️ Warning**: Uninstalling will not delete the PersistentVolumeClaim. Delete manually if needed:

```bash
kubectl delete pvc etl-engine-data -n health-etl
```

## Architecture

### Message Processing Flow

```
RabbitMQ Queue → ETL Engine → MinIO (read raw data)
                     ↓
                AI Model (generate narrative)
                     ↓
                PostgreSQL (store narrative)
                     ↓
                MinIO (store processed data)
```

### Autoscaling

The ETL Engine scales based on:

1. **CPU Utilization**: Scales when CPU > 70%
2. **Memory Utilization**: Scales when memory > 80%
3. **RabbitMQ Queue Depth**: (Optional) Scale based on queue size

To enable queue-based scaling, install the KEDA operator:

```bash
# Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace

# Add ScaledObject
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: etl-engine-scaler
  namespace: health-etl
spec:
  scaleTargetRef:
    name: etl-engine
  minReplicaCount: 1
  maxReplicaCount: 3
  triggers:
  - type: rabbitmq
    metadata:
      queueName: health-data-processing
      host: amqp://user:password@rabbitmq.health-data.svc.cluster.local:5672/
      queueLength: "100"
```

## Monitoring

The chart includes annotations for Prometheus scraping:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8004"
prometheus.io/path: "/metrics"
```

### Metrics Endpoints

- **Health Check**: `http://etl-engine:8004/health`
- **Readiness Check**: `http://etl-engine:8004/ready`
- **Metrics**: `http://etl-engine:8004/metrics`

### Key Metrics

- `etl_messages_processed_total`: Total messages processed
- `etl_processing_duration_seconds`: Message processing duration
- `etl_errors_total`: Total processing errors
- `etl_queue_size`: Current queue size (if KEDA enabled)

## Security Considerations

### Secrets Management

**⚠️ CRITICAL: Never commit secrets to Git!**

Use Sealed Secrets or External Secrets Operator for production:

```bash
# Create sealed secret
kubectl create secret generic etl-engine-secrets \
  --from-literal=database-password=xxx \
  --from-literal=minio-access-key=xxx \
  --from-literal=minio-secret-key=xxx \
  --from-literal=rabbitmq-user=user \
  --from-literal=rabbitmq-password=xxx \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secret.yaml
```

### Pod Security

- Runs as non-root user (UID 1000)
- Read-only root filesystem
- Drops all capabilities
- Prevents privilege escalation

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: etl-engine-netpol
  namespace: health-etl
spec:
  podSelector:
    matchLabels:
      app: etl-engine
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-data
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
    - protocol: TCP
      port: 9000  # MinIO
    - protocol: TCP
      port: 5672  # RabbitMQ
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl get pods -n health-etl

# Check pod logs
kubectl logs -f deployment/etl-engine -n health-etl

# Check init container logs
kubectl logs deployment/etl-engine -n health-etl -c wait-for-rabbitmq
```

### Message processing issues

```bash
# Check RabbitMQ queue
kubectl exec -n health-data rabbitmq-0 -- \
  rabbitmqctl list_queues name messages consumers

# Check ETL logs for errors
kubectl logs -f deployment/etl-engine -n health-etl | grep ERROR

# Check metrics
kubectl port-forward -n health-etl svc/etl-engine 8004:8004
curl http://localhost:8004/metrics | grep etl_
```

### High memory usage

```bash
# Check memory consumption
kubectl top pods -n health-etl

# Adjust model cache size (reduce volume size)
helm upgrade etl-engine . \
  --set aiModel.cachePath=/app/.cache/huggingface \
  --reuse-values
```

### Persistence issues

```bash
# Check PVC status
kubectl get pvc -n health-etl

# Check PV binding
kubectl describe pvc etl-engine-data -n health-etl

# Check storage class
kubectl get storageclass
```

## Performance Tuning

### For Low-Resource Environments (Oracle Always Free)

```yaml
# values-production.yaml
resources:
  limits:
    cpu: 700m      # Lower limit
    memory: 2Gi    # Keep high for model inference

rabbitmq:
  prefetchCount: 1  # Process one at a time

autoscaling:
  minReplicas: 1
  maxReplicas: 2    # Lower max
```

### For High-Throughput Environments

```yaml
resources:
  limits:
    cpu: 4000m
    memory: 8Gi

rabbitmq:
  prefetchCount: 5  # Process multiple messages

autoscaling:
  minReplicas: 3
  maxReplicas: 10
```

## Contributing

For issues, feature requests, or contributions, please refer to the main project repository.

## License

Copyright © 2025 Health Data AI Platform Team
