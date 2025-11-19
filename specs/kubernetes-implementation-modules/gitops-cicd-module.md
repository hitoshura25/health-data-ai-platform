# Module 7: GitOps & CI/CD
## ArgoCD & GitHub Actions Deployment Pipeline

**Estimated Time:** 1 week
**Dependencies:** Modules 1-4 (All services deployed)
**Deliverables:** Automated CI/CD pipeline with GitOps

---

## Objectives

Implement continuous deployment pipeline:
1. ArgoCD - GitOps continuous deployment
2. GitHub Actions - Build and test automation
3. Application CRDs - Declarative app definitions
4. Sync policies - Automated deployments
5. Multi-environment support (dev, staging, production)

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│  GitHub Repository                                      │
│  ├── .github/workflows/                                │
│  │   ├── build-health-api.yml     (CI)                │
│  │   ├── build-etl-engine.yml     (CI)                │
│  │   └── deploy-production.yml    (CD trigger)        │
│  ├── helm-charts/                                      │
│  │   └── health-platform/                              │
│  └── argocd/                                           │
│      ├── applications/                                 │
│      └── projects/                                     │
└────────────────────────────────────────────────────────┘
                  │
                  │ (git push)
                  ▼
┌────────────────────────────────────────────────────────┐
│  GitHub Actions (CI)                                    │
│  1. Run tests                                           │
│  2. Build Docker images                                 │
│  3. Push to GitHub Container Registry                   │
│  4. Update image tags in Git                            │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ (watches Git)
                          ▼
┌────────────────────────────────────────────────────────┐
│  ArgoCD (CD)                                            │
│  - Detects changes in Git                               │
│  - Syncs to Kubernetes cluster                          │
│  - Automated deployment with health checks              │
│  - Rollback on failure                                  │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  OKE Cluster (Production)                               │
│  - Applications updated automatically                    │
└────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Install ArgoCD

```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Port-forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login (UI: https://localhost:8080, CLI below)
argocd login localhost:8080 \
  --username admin \
  --password <password-from-above> \
  --insecure

# Change admin password
argocd account update-password
```

**Configure Ingress for ArgoCD:**

```yaml
# argocd-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server-ingress
  namespace: argocd
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - argocd.yourdomain.com
    secretName: argocd-tls
  rules:
  - host: argocd.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: argocd-server
            port:
              name: https
```

```bash
kubectl apply -f argocd-ingress.yaml
```

### Step 2: Create ArgoCD Project

```yaml
# argocd/projects/health-platform-project.yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: health-platform
  namespace: argocd
spec:
  description: Health Data AI Platform

  sourceRepos:
  - 'https://github.com/your-org/health-data-ai-platform'

  destinations:
  - namespace: '*'
    server: https://kubernetes.default.svc

  clusterResourceWhitelist:
  - group: '*'
    kind: '*'

  namespaceResourceWhitelist:
  - group: '*'
    kind: '*'
```

```bash
kubectl apply -f argocd/projects/health-platform-project.yaml
```

### Step 3: Create Application Definitions

**Infrastructure Application:**

```yaml
# argocd/applications/infrastructure.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: infrastructure
  namespace: argocd
spec:
  project: health-platform

  source:
    repoURL: https://github.com/your-org/health-data-ai-platform
    targetRevision: main
    path: helm-charts/health-platform/charts/infrastructure
    helm:
      valueFiles:
      - ../../values-production.yaml

  destination:
    server: https://kubernetes.default.svc
    namespace: health-data

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
    - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

**Health API Application:**

```yaml
# argocd/applications/health-api.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: health-api
  namespace: argocd
spec:
  project: health-platform

  source:
    repoURL: https://github.com/your-org/health-data-ai-platform
    targetRevision: main
    path: helm-charts/health-platform/charts/health-api
    helm:
      valueFiles:
      - ../../values-production.yaml
      parameters:
      - name: image.tag
        value: "latest"  # Will be updated by CI

  destination:
    server: https://kubernetes.default.svc
    namespace: health-api

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true

  # Health checks
  ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers:
    - /spec/replicas  # Ignore HPA changes
```

Apply all applications:

```bash
kubectl apply -f argocd/applications/
```

### Step 4: GitHub Actions - Build Pipeline

**File: `.github/workflows/build-health-api.yml`**

```yaml
name: Build and Push Health API

on:
  push:
    branches: [ main ]
    paths:
    - 'services/health-api-service/**'
    - '.github/workflows/build-health-api.yml'
  pull_request:
    branches: [ main ]
    paths:
    - 'services/health-api-service/**'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/health-api

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        cd services/health-api-service
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        cd services/health-api-service
        pytest tests/ --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./services/health-api-service/coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - uses: actions/checkout@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=sha,prefix={{branch}}-
          type=semver,pattern={{version}}
          type=raw,value=latest,enable={{is_default_branch}}

    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: ./services/health-api-service
        push: ${{ github.event_name != 'pull_request' }}
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

    - name: Update image tag in GitOps repo
      if: github.ref == 'refs/heads/main'
      run: |
        # Update Helm values with new image tag
        NEW_TAG=$(echo ${{ github.sha }} | cut -c1-7)
        sed -i "s/tag: .*/tag: \"${NEW_TAG}\"/" \
          helm-charts/health-platform/charts/health-api/values.yaml

        # Commit and push (triggers ArgoCD)
        git config user.name "GitHub Actions"
        git config user.email "actions@github.com"
        git add helm-charts/health-platform/charts/health-api/values.yaml
        git commit -m "Update health-api image tag to ${NEW_TAG}"
        git push
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**File: `.github/workflows/deploy-production.yml`**

```yaml
name: Deploy to Production

on:
  workflow_dispatch:
    inputs:
      service:
        description: 'Service to deploy'
        required: true
        type: choice
        options:
        - health-api
        - etl-engine
        - webauthn-stack
      version:
        description: 'Version/tag to deploy'
        required: true
        type: string

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Install ArgoCD CLI
      run: |
        curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
        chmod +x argocd
        sudo mv argocd /usr/local/bin/

    - name: Login to ArgoCD
      run: |
        argocd login argocd.yourdomain.com \
          --username admin \
          --password ${{ secrets.ARGOCD_PASSWORD }} \
          --insecure

    - name: Sync application
      run: |
        argocd app sync ${{ github.event.inputs.service }} \
          --revision ${{ github.event.inputs.version }} \
          --prune \
          --timeout 300

    - name: Wait for sync
      run: |
        argocd app wait ${{ github.event.inputs.service }} \
          --health \
          --timeout 600

    - name: Verify deployment
      run: |
        argocd app get ${{ github.event.inputs.service }} \
          --show-operation
```

### Step 5: ArgoCD Configuration

**Enable Auto-Sync:**

```bash
# For each application
argocd app set infrastructure --sync-policy automated
argocd app set health-api --sync-policy automated
argocd app set etl-engine --sync-policy automated
argocd app set webauthn-stack --sync-policy automated

# Enable self-heal (auto-revert manual changes)
argocd app set health-api --self-heal

# Enable prune (delete removed resources)
argocd app set health-api --auto-prune
```

**Configure Sync Windows:**

```yaml
# Prevent syncs during business hours
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: health-api
spec:
  syncPolicy:
    syncWindows:
    - kind: deny
      schedule: '0 8-17 * * 1-5'  # Mon-Fri 8am-5pm
      duration: 9h
      applications:
      - health-api
```

---

## Notifications

**Configure Slack notifications:**

```bash
# Install argocd-notifications
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/stable/manifests/install.yaml

# Configure Slack
kubectl create secret generic argocd-notifications-secret \
  -n argocd \
  --from-literal=slack-token=<SLACK_BOT_TOKEN>

# Create ConfigMap
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
  namespace: argocd
data:
  service.slack: |
    token: \$slack-token

  trigger.on-deployed: |
    - when: app.status.operationState.phase in ['Succeeded']
      send: [app-deployed]

  trigger.on-health-degraded: |
    - when: app.status.health.status == 'Degraded'
      send: [app-health-degraded]

  template.app-deployed: |
    message: |
      Application {{.app.metadata.name}} is now running version {{.app.status.sync.revision}}.
    slack:
      attachments: |
        [{
          "title": "{{.app.metadata.name}}",
          "color": "good",
          "fields": [{
            "title": "Sync Status",
            "value": "{{.app.status.sync.status}}",
            "short": true
          }, {
            "title": "Repository",
            "value": "{{.app.spec.source.repoURL}}",
            "short": true
          }]
        }]

  template.app-health-degraded: |
    message: |
      Application {{.app.metadata.name}} has degraded health.
    slack:
      attachments: |
        [{
          "title": "{{.app.metadata.name}}",
          "color": "danger"
        }]
EOF

# Subscribe application to notifications
kubectl patch app health-api -n argocd --type merge -p \
  '{"metadata":{"annotations":{"notifications.argoproj.io/subscribe.on-deployed.slack":"deployments"}}}'
```

---

## Rollback Strategy

```bash
# View deployment history
argocd app history health-api

# Rollback to previous version
argocd app rollback health-api

# Rollback to specific revision
argocd app rollback health-api 5

# Verify rollback
argocd app get health-api
```

---

## Success Criteria

- [ ] ArgoCD installed and accessible via ingress
- [ ] All applications defined in ArgoCD
- [ ] Auto-sync enabled for all apps
- [ ] GitHub Actions building and pushing images
- [ ] Image tags automatically updated in Git
- [ ] ArgoCD syncing changes automatically
- [ ] Health checks passing after deployment
- [ ] Notifications configured (Slack/email)
- [ ] Rollback tested and working
- [ ] Multi-environment support (dev, staging, prod)

---

**Module 7 Complete**: GitOps CI/CD pipeline operational
