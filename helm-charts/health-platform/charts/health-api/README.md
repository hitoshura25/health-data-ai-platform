# Health API Helm Chart

Helm chart for deploying the Health Data AI Platform - API Service to Kubernetes.

## Overview

This chart deploys the Health API service, which provides a FastAPI-based REST API for uploading Android Health Connect data. The service integrates with:

- **PostgreSQL**: For storing user and health data metadata
- **Redis**: For rate limiting and caching
- **MinIO**: For storing raw health data files
- **RabbitMQ**: For publishing messages to the ETL processing pipeline
- **WebAuthn**: For JWT-based authentication
- **Jaeger**: For distributed tracing

## Prerequisites

- Kubernetes 1.24+
- Helm 3.13+
- PersistentVolume provisioner support in the underlying infrastructure
- Ingress controller (NGINX recommended)
- cert-manager (for SSL/TLS certificates)

## Installing the Chart

### Development Installation

```bash
# Create namespace
kubectl create namespace health-api

# Install with default values
helm install health-api . \
  --namespace health-api \
  --create-namespace
```

### Production Installation

```bash
# Create namespace
kubectl create namespace health-api

# Install with production values
helm install health-api . \
  --namespace health-api \
  --values values-production.yaml \
  --set image.tag=v1.0.0 \
  --set ingress.host=api.yourdomain.com
```

## Configuration

The following table lists the configurable parameters of the Health API chart and their default values.

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Health API image repository | `ghcr.io/your-org/health-api` |
| `image.tag` | Health API image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |

### Deployment Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace` | Kubernetes namespace | `health-api` |
| `replicaCount` | Number of replicas | `2` |
| `autoscaling.enabled` | Enable HorizontalPodAutoscaler | `true` |
| `autoscaling.minReplicas` | Minimum replicas | `2` |
| `autoscaling.maxReplicas` | Maximum replicas | `5` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization | `70` |
| `autoscaling.targetMemoryUtilizationPercentage` | Target memory utilization | `80` |

### Resource Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.requests.cpu` | CPU request | `250m` |
| `resources.requests.memory` | Memory request | `256Mi` |
| `resources.limits.cpu` | CPU limit | `1000m` |
| `resources.limits.memory` | Memory limit | `512Mi` |

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Kubernetes service type | `ClusterIP` |
| `service.port` | Service port | `8001` |
| `service.targetPort` | Container port | `8000` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.host` | Ingress hostname | `api.yourdomain.com` |
| `ingress.tls.enabled` | Enable TLS | `true` |
| `ingress.tls.secretName` | TLS secret name | `health-api-tls` |

### Database Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database.host` | PostgreSQL host | `postgresql-health.health-data.svc.cluster.local` |
| `database.port` | PostgreSQL port | `5432` |
| `database.name` | Database name | `healthdb` |
| `database.user` | Database user | `healthapi` |
| `secrets.database.password` | Database password (use Sealed Secrets) | `CHANGE_ME` |

### Redis Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.host` | Redis host | `redis-health.health-data.svc.cluster.local` |
| `redis.port` | Redis port | `6379` |
| `secrets.redis.password` | Redis password (use Sealed Secrets) | `CHANGE_ME` |

### MinIO Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `minio.endpoint` | MinIO endpoint | `minio.health-data.svc.cluster.local:9000` |
| `minio.bucket` | S3 bucket name | `health-data` |
| `secrets.minio.accessKey` | MinIO access key (use Sealed Secrets) | `CHANGE_ME` |
| `secrets.minio.secretKey` | MinIO secret key (use Sealed Secrets) | `CHANGE_ME` |

### RabbitMQ Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `rabbitmq.host` | RabbitMQ host | `rabbitmq.health-data.svc.cluster.local` |
| `rabbitmq.port` | RabbitMQ port | `5672` |
| `rabbitmq.exchange` | RabbitMQ exchange | `health-data-upload` |
| `secrets.rabbitmq.password` | RabbitMQ password (use Sealed Secrets) | `CHANGE_ME` |

### Application Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `app.logLevel` | Application log level | `INFO` |
| `app.workers` | Number of workers | `4` |
| `app.maxUploadSizeMB` | Max upload size in MB | `50` |
| `app.uploadRateLimit` | Upload rate limit | `10/minute` |
| `app.allowedOrigins` | CORS allowed origins | `https://app.yourdomain.com` |

## Upgrading

```bash
# Upgrade with new values
helm upgrade health-api . \
  --namespace health-api \
  --values values-production.yaml \
  --set image.tag=v1.1.0
```

## Uninstalling

```bash
helm uninstall health-api --namespace health-api
```

## Security Considerations

### Secrets Management

**⚠️ CRITICAL: Never commit secrets to Git!**

For production deployments, use one of the following:

1. **Sealed Secrets** (Recommended for GitOps)
   ```bash
   # Install kubeseal
   kubectl create secret generic health-api-secrets \
     --from-literal=database-password=xxx \
     --from-literal=redis-password=xxx \
     --dry-run=client -o yaml | \
     kubeseal -o yaml > sealed-secret.yaml
   ```

2. **External Secrets Operator** (Recommended for cloud secrets managers)
   ```yaml
   apiVersion: external-secrets.io/v1beta1
   kind: ExternalSecret
   metadata:
     name: health-api-secrets
   spec:
     secretStoreRef:
       name: oci-vault
     target:
       name: health-api-secrets
     data:
     - secretKey: database-password
       remoteRef:
         key: health-api-db-password
   ```

### Pod Security

The chart implements the following security measures:

- Runs as non-root user (UID 1000)
- Read-only root filesystem
- Drops all capabilities
- Prevents privilege escalation
- Uses security context constraints

### Network Policies

Consider implementing NetworkPolicies to restrict traffic:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: health-api-netpol
  namespace: health-api
spec:
  podSelector:
    matchLabels:
      app: health-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: health-system
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-data
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
    - protocol: TCP
      port: 6379  # Redis
    - protocol: TCP
      port: 9000  # MinIO
    - protocol: TCP
      port: 5672  # RabbitMQ
```

## Monitoring

The chart includes annotations for Prometheus scraping:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8001"
prometheus.io/path: "/metrics"
```

### Health Checks

- **Liveness Probe**: `/health/live` - Checks if the application is running
- **Readiness Probe**: `/health/ready` - Checks if the application is ready to serve traffic

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl get pods -n health-api

# Check pod logs
kubectl logs -f deployment/health-api -n health-api

# Check events
kubectl get events -n health-api --sort-by='.lastTimestamp'
```

### Database connection issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql postgresql://healthapi:password@postgresql-health.health-data.svc.cluster.local:5432/healthdb
```

### Ingress not working

```bash
# Check ingress status
kubectl describe ingress health-api-ingress -n health-api

# Check ingress controller logs
kubectl logs -n health-system deployment/nginx-ingress-controller
```

## Contributing

For issues, feature requests, or contributions, please refer to the main project repository.

## License

Copyright © 2025 Health Data AI Platform Team
