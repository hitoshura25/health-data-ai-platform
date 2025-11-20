# ArgoCD Helm Chart

This Helm chart installs and configures ArgoCD for the Health Data AI Platform with platform-specific settings.

## Overview

ArgoCD is a declarative, GitOps continuous delivery tool for Kubernetes. This chart wraps the official ArgoCD Helm chart with our platform-specific configuration.

## Installation

### Prerequisites

- Kubernetes cluster (OKE or other)
- Helm 3.x
- kubectl configured to access your cluster

### Quick Install

```bash
# Add ArgoCD Helm repository
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Install ArgoCD
helm install argocd . \
  --namespace argocd \
  --create-namespace \
  --values values.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd
```

### Access ArgoCD

**Get Initial Admin Password:**
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

**Port Forward (for local access):**
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

**Access UI:**
- URL: https://localhost:8080
- Username: `admin`
- Password: (from above command)

**Change Admin Password:**
```bash
argocd login localhost:8080 --insecure
argocd account update-password
```

## Configuration

### Main Values

Key configuration options in `values.yaml`:

```yaml
argo-cd:
  global:
    domain: argocd.yourdomain.com  # Update for your domain

  server:
    replicas: 2                     # High availability
    ingress:
      enabled: true                 # Enable ingress
      ingressClassName: nginx       # Ingress controller
      annotations:
        cert-manager.io/cluster-issuer: letsencrypt-prod

  repoServer:
    replicas: 2                     # High availability for Git operations

  controller:
    replicas: 1                     # Application controller

  metrics:
    enabled: true                   # Prometheus metrics
```

### Environment-Specific Values

Create separate values files for each environment:

**`values-dev.yaml`:**
```yaml
argo-cd:
  server:
    replicas: 1
    resources:
      limits:
        cpu: 250m
        memory: 256Mi
```

**`values-production.yaml`:**
```yaml
argo-cd:
  server:
    replicas: 3
    resources:
      limits:
        cpu: 1000m
        memory: 1Gi
  controller:
    replicas: 2
```

## Features

### High Availability

- Multiple replicas for server and repo-server
- Load balancing via Kubernetes Service
- Health checks and readiness probes

### Ingress

- Nginx ingress controller support
- TLS/SSL with cert-manager
- SSL passthrough for ArgoCD

### Monitoring

- Prometheus metrics exported
- ServiceMonitor resources for Prometheus Operator
- Health status exposed via `/healthz`

### Notifications

- Slack notifications (configure separately)
- Webhook support
- Email alerts

### ApplicationSet

- ApplicationSet controller included
- Generate multiple Applications from templates
- Support for Git generators, Matrix generators, etc.

## Post-Installation

### 1. Configure Ingress

Update your DNS to point `argocd.yourdomain.com` to your ingress controller's external IP:

```bash
kubectl get svc -n ingress-nginx
# Note the EXTERNAL-IP
```

### 2. Install Applications

Apply ArgoCD Applications and Projects:

```bash
# Install AppProject
kubectl apply -f ../../argocd-apps/projects/health-platform-project.yaml

# Install Applications
kubectl apply -f ../../argocd-apps/applications/dev/
```

### 3. Configure Repository Access

For private repositories, add credentials:

```bash
# Via CLI
argocd repo add https://github.com/your-org/health-data-ai-platform \
  --username <username> \
  --password <github-token>

# Via UI
# Settings → Repositories → Connect Repo
```

### 4. Enable Notifications (Optional)

```bash
# Install argocd-notifications
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/stable/manifests/install.yaml

# Configure Slack
kubectl create secret generic argocd-notifications-secret \
  -n argocd \
  --from-literal=slack-token=<SLACK_BOT_TOKEN>

# Apply notification templates (see CICD.md)
```

## Upgrading ArgoCD

### Check Current Version

```bash
helm list -n argocd
argocd version
```

### Upgrade Chart

```bash
# Update Helm dependencies
helm dependency update

# Upgrade ArgoCD
helm upgrade argocd . \
  --namespace argocd \
  --values values.yaml

# Verify upgrade
kubectl get pods -n argocd
argocd version
```

## Uninstallation

**Warning**: This will delete all ArgoCD resources, including Applications.

```bash
# Delete all Applications first (optional, prevents cascading deletes)
argocd app delete --all

# Uninstall ArgoCD
helm uninstall argocd -n argocd

# Delete namespace (if desired)
kubectl delete namespace argocd
```

## Troubleshooting

### ArgoCD Server Not Starting

```bash
# Check pod status
kubectl get pods -n argocd

# View logs
kubectl logs -f deployment/argocd-server -n argocd

# Check events
kubectl get events -n argocd --sort-by='.lastTimestamp'
```

### Cannot Access UI

```bash
# Verify service is running
kubectl get svc argocd-server -n argocd

# Check ingress
kubectl get ingress -n argocd
kubectl describe ingress argocd-server-ingress -n argocd

# Test port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### Sync Failures

```bash
# Check application status
argocd app list
argocd app get <app-name>

# View sync errors
argocd app sync <app-name> --dry-run

# Hard refresh
argocd app refresh <app-name> --hard
```

## Resources

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [ArgoCD Helm Chart](https://github.com/argoproj/argo-helm/tree/main/charts/argo-cd)
- [Platform CI/CD Guide](../../CICD.md)
- [ArgoCD Applications](../../argocd-apps/)

## Support

For issues or questions:
- GitHub Issues: [Create Issue](https://github.com/your-org/health-data-ai-platform/issues)
- Slack: #health-platform-ops

---

**Maintained By**: Health Data AI Platform Team
