# Module 0: Local Kubernetes Testing Guide
## Validate Before Cloud Deployment

**Purpose:** Test and validate Kubernetes deployments locally before deploying to Oracle Cloud Infrastructure (OKE)
**Estimated Time:** 1-2 weeks for complete validation
**Prerequisites:** None (this is the starting point)
**Cost:** $0 (local testing) + optional $30-50 (temporary dev OKE for ARM validation)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Local Kubernetes Options](#local-kubernetes-options)
3. [Multi-Layer Validation Strategy](#multi-layer-validation-strategy)
4. [What Can Be Tested Locally](#what-can-be-tested-locally)
5. [ARM Architecture Testing](#arm-architecture-testing)
6. [Storage Class Validation](#storage-class-validation)
7. [Complete Testing Checklist](#complete-testing-checklist)
8. [Practical Setup Instructions](#practical-setup-instructions)
9. [GitHub Actions Integration](#github-actions-integration)
10. [Recommended Timeline](#recommended-timeline)
11. [Troubleshooting](#troubleshooting)

---

## Executive Summary

### Why Test Locally?

**Risk Reduction:** Catch 90%+ of deployment issues before production
**Cost Savings:** Avoid cloud costs during development and debugging
**Faster Iteration:** Test changes in seconds/minutes vs. cloud deployment times
**Confidence:** Validate Helm charts, RBAC, NetworkPolicies, and application logic
**Learning:** Understand Kubernetes behavior in controlled environment

### Core Recommendations

1. **Use minikube as primary local testing environment**
   - Best balance of production fidelity and functionality
   - Supports Calico CNI for NetworkPolicy testing
   - Built-in ingress, metrics-server, dashboard

2. **Implement multi-layer validation strategy**
   - Layer 1: Helm lint + template validation (no cluster)
   - Layer 2: Helm dry-run testing (minikube)
   - Layer 3: Full deployment testing (minikube with workloads)
   - Layer 4: Terraform plan validation (review without applying)
   - Layer 5: ARM compatibility validation (multi-arch images)

3. **Resource Requirements**
   - **Minimum:** 4 vCPU, 8GB RAM, 100GB storage
   - **Recommended:** 6 vCPU, 12GB RAM, 150GB storage
   - **Optimal:** 8 vCPU, 16GB RAM, 200GB storage

4. **ARM Architecture Strategy**
   - Build multi-architecture images from day one
   - Use Docker Buildx for arm64 + amd64
   - Validate with KubeArchInspect
   - Optional: Small dev OKE cluster for final ARM testing (~$30-50)

### What This Guide Covers

- Comparison of local Kubernetes options (minikube, k3d, KiND)
- Step-by-step setup and validation procedures
- Complete testing checklist (10 phases)
- ARM compatibility strategies
- Storage class testing approaches
- CI/CD integration with GitHub Actions
- Timeline and cost estimates

---

## Local Kubernetes Options

### Comparison Matrix

| Feature | minikube | k3d | KiND | Docker Desktop |
|---------|----------|-----|------|----------------|
| **Production Fidelity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Resource Usage** | High | Low | Medium | High |
| **Startup Time** | 2-3 min | 10-30 sec | 30-60 sec | 1-2 min |
| **CNI Support** | Excellent | Limited | Limited | Basic |
| **NetworkPolicy Testing** | Yes (Calico) | Partial | No (default) | No |
| **Multi-node** | Yes | Yes | Yes | No |
| **Storage Options** | Excellent | Good | Good | Limited |
| **Ingress Support** | Built-in addon | Manual | Manual | Limited |
| **Best For** | Local dev/test | CI/CD | CI/CD | Simple apps |
| **Recommendation** | ✅ PRIMARY | Secondary | Alternative | ❌ Avoid |

---

### Option 1: minikube (RECOMMENDED PRIMARY)

**Why minikube?**
- Most production-like Kubernetes environment
- Excellent CNI support (Calico, Cilium, Flannel)
- Critical for testing NetworkPolicies (required for Module 6)
- Built-in addons reduce setup complexity
- Best for testing RBAC, Pod Security Standards
- Persistent storage support with multiple plugins

**Pros:**
- ✅ Production fidelity for security features
- ✅ Calico CNI for NetworkPolicy testing
- ✅ Built-in ingress controller addon
- ✅ Metrics-server addon for HPA testing
- ✅ Dashboard addon for visualization
- ✅ Multiple storage provisioners
- ✅ Excellent documentation and community support

**Cons:**
- ❌ Higher resource consumption (~35% more than k3d)
- ❌ Slower startup time (2-3 minutes)
- ❌ More complex multi-node setup

**Resource Footprint:**
- **Idle:** ~2.7GB RAM, 1-2 CPU
- **Under Load:** 4-8GB RAM, 2-4 CPU
- **Recommended Allocation:** 6 CPU, 12GB RAM, 150GB disk

**Installation:**

```bash
# macOS
brew install minikube

# Linux
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Windows (PowerShell as Administrator)
choco install minikube
```

**Basic Setup:**

```bash
# Start with recommended configuration
minikube start \
  --cpus=6 \
  --memory=12288 \
  --disk-size=150g \
  --driver=docker \
  --cni=calico \
  --kubernetes-version=1.28.0 \
  --addons=metrics-server,ingress,dashboard

# Verify
minikube status
kubectl get nodes
kubectl get pods -A

# Check Calico
kubectl get pods -n kube-system | grep calico
```

**Essential Addons:**

```bash
# Enable addons
minikube addons enable metrics-server
minikube addons enable ingress
minikube addons enable dashboard
minikube addons enable storage-provisioner

# List all addons
minikube addons list
```

**Accessing Services:**

```bash
# Method 1: Port forwarding (recommended)
kubectl port-forward -n health-api svc/health-api 8001:8001

# Method 2: minikube service (opens browser)
minikube service health-api -n health-api

# Method 3: Ingress (requires DNS or /etc/hosts)
echo "$(minikube ip) api.local.dev" | sudo tee -a /etc/hosts
curl http://api.local.dev
```

**Multi-node Setup (Optional):**

```bash
# Create 3-node cluster
minikube start \
  --nodes=3 \
  --cpus=2 \
  --memory=4096 \
  --driver=docker \
  --cni=calico

# Verify nodes
kubectl get nodes
```

---

### Option 2: k3d (Secondary for CI/CD)

**Why k3d?**
- Fastest startup (10-30 seconds)
- Lowest resource consumption
- Excellent for CI/CD pipelines (GitHub Actions)
- k3s distribution is production-ready

**Pros:**
- ✅ Blazing fast startup/teardown
- ✅ Minimal resource usage (~2GB RAM idle)
- ✅ Easy multi-node setup
- ✅ Good Docker integration
- ✅ Perfect for GitHub Actions workflows

**Cons:**
- ❌ k3s strips some advanced features
- ❌ Limited NetworkPolicy support (Flannel default)
- ❌ RBAC less complete than full Kubernetes
- ❌ Not ideal for security feature testing

**When to Use:**
- GitHub Actions CI/CD validation
- Quick smoke tests during development
- Testing Helm chart rendering
- Rapid iteration feedback loops

**Installation:**

```bash
# macOS/Linux
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Or via package manager
brew install k3d  # macOS
```

**Basic Setup:**

```bash
# Create cluster
k3d cluster create health-platform \
  --agents 2 \
  --port "8001:8001@loadbalancer" \
  --port "9000:9000@loadbalancer"

# Verify
kubectl get nodes

# Delete when done
k3d cluster delete health-platform
```

**GitHub Actions Example:**

```yaml
# .github/workflows/helm-validate.yml
name: Helm Chart Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Create k3d cluster
        run: |
          curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
          k3d cluster create test --wait

      - name: Deploy Helm charts
        run: |
          helm install health-platform ./helm-charts/health-platform \
            --values ./helm-charts/values-ci.yaml \
            --wait --timeout 5m

      - name: Run tests
        run: |
          kubectl get pods -A
          kubectl wait --for=condition=ready pod -l app=health-api --timeout=300s

      - name: Cleanup
        if: always()
        run: k3d cluster delete test
```

---

### Option 3: KiND (Kubernetes in Docker)

**Why KiND?**
- Popular in Kubernetes community
- Great for testing Kubernetes features
- Used by Kubernetes project for testing

**Pros:**
- ✅ Fast cluster creation
- ✅ Docker-native (containers as nodes)
- ✅ Good multi-node support
- ✅ Low overhead

**Cons:**
- ❌ Default CNI (Kindnet) doesn't support NetworkPolicies
- ❌ Requires manual Calico installation for NetworkPolicy testing
- ❌ Less user-friendly than minikube
- ❌ No built-in addons

**When to Use:**
- Alternative to k3d for CI/CD
- Multi-node testing scenarios
- Kubernetes feature testing

**Setup with Calico (for NetworkPolicy testing):**

```bash
# Install KiND
brew install kind  # macOS

# Create cluster with custom CNI
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: 192.168.0.0/16
nodes:
- role: control-plane
- role: worker
- role: worker
EOF

# Install Calico
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.0/manifests/calico.yaml

# Verify
kubectl get pods -n kube-system | grep calico
```

---

### Option 4: Docker Desktop Kubernetes (NOT RECOMMENDED)

**Why Not?**
- ❌ Single-node only (can't test multi-node scenarios)
- ❌ Limited networking capabilities
- ❌ Poor storage testing
- ❌ No CNI choice (basic overlay)
- ❌ Can't test NetworkPolicies properly

**When It Might Be Acceptable:**
- Very simple applications
- Already using Docker Desktop
- No security feature testing needed

**Our Verdict:** Use minikube instead. The resource overhead is worth it for production fidelity.

---

## Multi-Layer Validation Strategy

Testing Kubernetes deployments requires multiple validation layers. Each layer catches different types of issues.

### Layer 1: Helm Chart Validation (No Cluster Required)

**What This Tests:**
- YAML syntax errors
- Template variable substitution
- Kubernetes API schema compliance
- Policy violations (via OPA/Conftest)
- Chart dependencies

**Tools Required:**
- `helm` CLI
- `kubeval` (Kubernetes manifest validator)
- `conftest` (OPA policy testing, optional)
- `helm-unittest` (chart unit tests, optional)

**Setup:**

```bash
# Install tools
brew install helm kubeval

# Optional: OPA Conftest
brew install conftest

# Optional: Helm unittest plugin
helm plugin install https://github.com/helm-unittest/helm-unittest
```

**Validation Commands:**

```bash
# 1. Helm Lint - Check for best practices
helm lint ./helm-charts/health-platform

# Expected output:
# ==> Linting ./helm-charts/health-platform
# [INFO] Chart.yaml: icon is recommended
# 1 chart(s) linted, 0 chart(s) failed

# 2. Template Rendering - Generate manifests
helm template health-platform ./helm-charts/health-platform \
  --values ./helm-charts/values-dev.yaml \
  --output-dir /tmp/rendered-manifests

# Review rendered files
ls -la /tmp/rendered-manifests/

# 3. Kubeval - Validate against Kubernetes API
kubeval /tmp/rendered-manifests/**/*.yaml \
  --kubernetes-version 1.28.0 \
  --strict

# Expected output:
# PASS - manifests/deployment.yaml contains a valid Deployment
# PASS - manifests/service.yaml contains a valid Service

# 4. Check for common issues
grep -r "CHANGE_ME" /tmp/rendered-manifests/
grep -r "TODO" /tmp/rendered-manifests/

# 5. Validate dependencies
helm dependency list ./helm-charts/health-platform
helm dependency update ./helm-charts/health-platform
```

**OPA Policy Testing (Optional but Recommended):**

```bash
# Create policy file: policies/required-labels.rego
cat > policies/required-labels.rego <<'EOF'
package main

deny[msg] {
  input.kind == "Deployment"
  not input.metadata.labels.app
  msg = sprintf("Deployment %s must have 'app' label", [input.metadata.name])
}

deny[msg] {
  input.kind == "Service"
  not input.metadata.labels.app
  msg = sprintf("Service %s must have 'app' label", [input.metadata.name])
}
EOF

# Run policy tests
conftest test /tmp/rendered-manifests/**/*.yaml -p policies/

# Expected output:
# FAIL - manifests/deployment.yaml - Deployment health-api must have 'app' label
```

**Helm Unit Tests (Optional):**

```bash
# Create test file: helm-charts/health-platform/tests/deployment_test.yaml
cat > helm-charts/health-platform/tests/deployment_test.yaml <<'EOF'
suite: test deployment
templates:
  - templates/deployment.yaml
tests:
  - it: should create deployment with correct replicas
    set:
      replicaCount: 3
    asserts:
      - equal:
          path: spec.replicas
          value: 3

  - it: should set resource limits
    asserts:
      - isNotEmpty:
          path: spec.template.spec.containers[0].resources.limits
EOF

# Run unit tests
helm unittest ./helm-charts/health-platform

# Expected output:
# ### Chart [ health-platform ] ./helm-charts/health-platform
#  PASS  test deployment  ./helm-charts/health-platform/tests/deployment_test.yaml
# Charts:      1 passed, 1 total
# Test Suites: 1 passed, 1 total
# Tests:       2 passed, 2 total
```

**What Layer 1 Catches:**
- ✅ YAML syntax errors
- ✅ Missing required fields
- ✅ Invalid Kubernetes API usage
- ✅ Template rendering errors
- ✅ Policy violations
- ✅ Incorrect value references

**What It Doesn't Catch:**
- ❌ Runtime issues (pod won't start)
- ❌ Service connectivity problems
- ❌ RBAC permission issues
- ❌ Resource constraint violations
- ❌ Storage provisioning failures

---

### Layer 2: Helm Dry-Run Testing (Requires minikube)

**What This Tests:**
- API server compatibility
- Admission controller validation
- Webhook validation (if configured)
- Resource name conflicts
- Namespace existence
- More accurate than Layer 1

**Prerequisites:**

```bash
# Start minikube
minikube start

# Create required namespaces
kubectl create namespace health-api
kubectl create namespace health-data
kubectl create namespace health-etl
kubectl create namespace health-auth
kubectl create namespace health-observability
```

**Dry-Run Commands:**

```bash
# 1. Basic dry-run (client-side only)
helm install health-platform ./helm-charts/health-platform \
  --values ./helm-charts/values-dev.yaml \
  --dry-run

# 2. Server-side dry-run (MORE ACCURATE)
helm install health-platform ./helm-charts/health-platform \
  --values ./helm-charts/values-dev.yaml \
  --dry-run \
  --debug \
  --namespace health-api \
  > /tmp/dry-run-output.yaml

# 3. Review output
less /tmp/dry-run-output.yaml

# 4. Check for hooks
grep -A 10 "kind: Job" /tmp/dry-run-output.yaml

# 5. Verify computed values
grep -A 5 "COMPUTED VALUES" /tmp/dry-run-output.yaml
```

**Validate Against Running Cluster:**

```bash
# This actually talks to API server but doesn't create resources
kubectl apply --dry-run=server -f /tmp/dry-run-output.yaml

# Check what would be created
kubectl diff -f /tmp/dry-run-output.yaml || true
```

**Common Issues Caught:**

```bash
# Example: Resource already exists
Error: INSTALLATION FAILED: rendered manifests contain a resource that already exists

# Example: RBAC permissions missing
Error: serviceaccounts "health-api-sa" not found

# Example: Invalid storage class
Error: StorageClass "oci-bv" not found
```

**What Layer 2 Catches:**
- ✅ API server validation
- ✅ Admission controller checks
- ✅ Webhook validation
- ✅ Resource conflicts
- ✅ RBAC issues (some)
- ✅ Storage class availability

**What It Doesn't Catch:**
- ❌ Runtime container issues
- ❌ Actual service connectivity
- ❌ Resource exhaustion
- ❌ Image pull failures
- ❌ Application-specific bugs

---

### Layer 3: Full Deployment Testing (minikube with Workloads)

**What This Tests:**
- Complete end-to-end deployment
- Pod startup and health checks
- Service-to-service communication
- Storage provisioning
- RBAC enforcement
- NetworkPolicy enforcement
- Actual application functionality

**Prerequisites:**

```bash
# Ensure minikube is running with sufficient resources
minikube start \
  --cpus=6 \
  --memory=12288 \
  --disk-size=150g \
  --cni=calico

# Create namespaces
kubectl create namespace health-api
kubectl create namespace health-data
kubectl create namespace health-etl
kubectl create namespace health-auth
kubectl create namespace health-observability
```

**Deployment Steps:**

```bash
# 1. Deploy infrastructure layer (Module 2)
helm install postgresql-health ./helm-charts/health-platform/charts/postgresql \
  --namespace health-data \
  --values ./helm-charts/values-dev.yaml \
  --set persistence.size=10Gi

helm install redis-health ./helm-charts/health-platform/charts/redis \
  --namespace health-data \
  --values ./helm-charts/values-dev.yaml

helm install minio ./helm-charts/health-platform/charts/minio \
  --namespace health-data \
  --values ./helm-charts/values-dev.yaml \
  --set persistence.size=20Gi

helm install rabbitmq ./helm-charts/health-platform/charts/rabbitmq \
  --namespace health-data \
  --values ./helm-charts/values-dev.yaml

# 2. Wait for infrastructure to be ready
kubectl wait --for=condition=ready pod \
  -l app=postgresql-health \
  -n health-data \
  --timeout=300s

kubectl wait --for=condition=ready pod \
  -l app=redis-health \
  -n health-data \
  --timeout=300s

# 3. Deploy application layer (Module 4)
helm install health-api ./helm-charts/health-platform/charts/health-api \
  --namespace health-api \
  --values ./helm-charts/values-dev.yaml

helm install etl-engine ./helm-charts/health-platform/charts/etl-engine \
  --namespace health-etl \
  --values ./helm-charts/values-dev.yaml

# 4. Wait for applications
kubectl wait --for=condition=ready pod \
  -l app=health-api \
  -n health-api \
  --timeout=300s
```

**Verification Commands:**

```bash
# Check all pods
kubectl get pods -A

# Expected: All pods in Running state, no restarts

# Check pod details
kubectl describe pod <pod-name> -n <namespace>

# Check logs
kubectl logs -f deployment/health-api -n health-api

# Check events
kubectl get events -n health-api --sort-by='.lastTimestamp'

# Check services
kubectl get svc -A

# Check persistent volumes
kubectl get pv
kubectl get pvc -A
```

**Connectivity Testing:**

```bash
# Test 1: Pod-to-Pod DNS
kubectl run test-pod --image=busybox --rm -it --restart=Never -- \
  nslookup postgresql-health.health-data.svc.cluster.local

# Expected: DNS resolution succeeds

# Test 2: Service connectivity
kubectl run test-pod --image=nicolaka/netshoot --rm -it --restart=Never -- \
  curl -v http://health-api.health-api.svc.cluster.local:8001/health

# Expected: HTTP 200 response

# Test 3: Database connectivity
kubectl run test-pod --image=postgres:15 --rm -it --restart=Never -- \
  psql -h postgresql-health.health-data.svc.cluster.local -U healthapi -d healthdb -c "SELECT 1"

# Expected: Connection succeeds, returns 1
```

**Application Functionality Testing:**

```bash
# Port-forward to access locally
kubectl port-forward -n health-api svc/health-api 8001:8001 &

# Test health endpoint
curl http://localhost:8001/health

# Expected: {"status": "healthy"}

# Test readiness endpoint
curl http://localhost:8001/health/ready

# Expected: {"status": "ready"}

# Test API functionality (if implemented)
curl -X POST http://localhost:8001/upload \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

**Resource Usage Monitoring:**

```bash
# Check resource usage
kubectl top nodes
kubectl top pods -A

# Check HPA status (if configured)
kubectl get hpa -n health-api

# Watch pod autoscaling
watch kubectl get pods -n health-api
```

**What Layer 3 Catches:**
- ✅ Container startup issues
- ✅ Image pull failures
- ✅ Health check failures
- ✅ Service connectivity issues
- ✅ Database connection problems
- ✅ RBAC enforcement
- ✅ Storage provisioning
- ✅ Resource constraints
- ✅ Application logic errors

**What It Doesn't Catch:**
- ❌ OCI-specific features
- ❌ Load balancer behavior
- ❌ ARM architecture issues
- ❌ Production-scale performance
- ❌ Multi-region scenarios

---

### Layer 4: Terraform Validation (Review Without Applying)

**What This Tests:**
- Terraform syntax
- Variable interpolation
- Resource dependencies
- Infrastructure changes
- Cost implications
- **CRITICAL: What will be created/destroyed**

**Prerequisites:**

```bash
# Install Terraform
brew install terraform  # macOS
# or download from https://www.terraform.io/downloads

# Configure OCI credentials (for plan generation)
export TF_VAR_tenancy_ocid="ocid1.tenancy.oc1..xxx"
export TF_VAR_user_ocid="ocid1.user.oc1..xxx"
export TF_VAR_fingerprint="xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx"
export TF_VAR_private_key_path="~/.oci/oci_api_key.pem"
export TF_VAR_region="us-ashburn-1"
export TF_VAR_compartment_id="ocid1.compartment.oc1..xxx"
```

**Validation Commands:**

```bash
cd terraform/environments/production

# 1. Format check
terraform fmt -check -recursive

# If not formatted:
terraform fmt -recursive

# 2. Initialize (downloads providers)
terraform init

# Expected:
# Terraform has been successfully initialized!

# 3. Validate syntax
terraform validate

# Expected:
# Success! The configuration is valid.

# 4. Generate plan (CRITICAL STEP - ALWAYS REVIEW)
terraform plan \
  -var-file=production.tfvars \
  -out=tfplan.out

# CAREFULLY REVIEW THE OUTPUT
# Look for:
# - Resources to be created (+ symbol)
# - Resources to be modified (~ symbol)
# - Resources to be DESTROYED (- symbol) ⚠️ DANGER

# 5. Save plan for human review
terraform show tfplan.out > tfplan-human-readable.txt

# 6. Review specific changes
grep "will be created" tfplan-human-readable.txt
grep "will be destroyed" tfplan-human-readable.txt
grep "will be updated" tfplan-human-readable.txt

# 7. Check for sensitive values
grep -i "password\|secret\|key" tfplan-human-readable.txt
```

**Cost Estimation (Optional):**

```bash
# Using Infracost (third-party tool)
brew install infracost

# Register and set API key
infracost auth login

# Generate cost estimate
infracost breakdown \
  --path terraform/environments/production \
  --terraform-var-file production.tfvars

# Expected output:
# Project: health-platform-production
# Breakdown:
#   oci_containerengine_cluster.k8s_cluster
#     └─ Free tier (Basic cluster)           $0.00
#   oci_containerengine_node_pool.app_nodes
#     └─ Ampere A1 (4 vCPU, 24GB RAM)       $0.00
# TOTAL: $0.00/month (Always Free tier)
```

**What to Look For:**

```bash
# ⚠️ RED FLAGS - Review carefully before applying

# 1. Unexpected resource deletions
# Terraform will perform the following actions:
#   - oci_containerengine_cluster.k8s_cluster will be DESTROYED
# ^^^ DANGER: This will delete your cluster!

# 2. Data loss risks
#   - oci_core_volume.postgresql_data will be DESTROYED
# ^^^ DANGER: This will delete your database!

# 3. Network changes
#   ~ oci_core_security_list.k8s_seclist {
#       - ingress_security_rules = [...]
#       + ingress_security_rules = [...]
#     }
# ^^^ Review: Are new ingress rules correct?

# 4. Resource recreation (destroy + create)
# -/+ oci_containerengine_node_pool.app_nodes (forces replacement)
# ^^^ DANGER: Pods will be evicted during recreation!
```

**Safe Review Process:**

```bash
# 1. NEVER skip the plan review
terraform plan -out=tfplan.out

# 2. ALWAYS save and review the human-readable output
terraform show tfplan.out > tfplan.txt
less tfplan.txt

# 3. Share with team for review (if applicable)
git add tfplan.txt
git commit -m "Terraform plan for review"
git push origin feature-branch
# Create PR for team review

# 4. Only apply after approval
# (User must explicitly approve before applying)
```

**What Layer 4 Catches:**
- ✅ Terraform syntax errors
- ✅ Invalid variable references
- ✅ Resource dependency issues
- ✅ Unexpected infrastructure changes
- ✅ Potential data loss scenarios
- ✅ Cost implications

**What It Doesn't Catch:**
- ❌ OCI API permission issues (until apply)
- ❌ Resource quota limits (until apply)
- ❌ Runtime Kubernetes issues
- ❌ Application deployment problems

---

### Layer 5: ARM Compatibility Validation

**What This Tests:**
- Container image ARM support
- Binary compatibility
- Multi-architecture builds
- Architecture-specific issues

**The Challenge:**

Oracle OKE uses **ARM Ampere A1** processors, but most development happens on **x86-64** machines (Intel/AMD). You must ensure container images support ARM architecture.

**Solution: Multi-Architecture Images**

Build images for both architectures from the start:

```bash
# Setup Docker Buildx (multi-architecture builder)
docker buildx create --name multiarch --use
docker buildx inspect --bootstrap
```

**Building Multi-Arch Images:**

```bash
# Build for both amd64 (local testing) and arm64 (OKE production)
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/your-org/health-api:v1.0.0 \
  --tag ghcr.io/your-org/health-api:latest \
  --push \
  ./services/health-api-service

# Expected output:
# [+] Building 245.3s (24/24) FINISHED
# => [linux/amd64 internal] load build context
# => [linux/arm64 internal] load build context
# => exporting to image
# => pushing ghcr.io/your-org/health-api:v1.0.0
```

**Dockerfile Best Practices for Multi-Arch:**

```dockerfile
# Use multi-arch base images
FROM --platform=$BUILDPLATFORM python:3.11-slim

# Install architecture-specific dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python packages usually work across architectures
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Runtime
CMD ["python", "main.py"]
```

**Validation Tools:**

```bash
# Install KubeArchInspect
go install github.com/ArmDeveloperEcosystem/kubearchinspect@latest

# Validate images in your Helm charts
kubearchinspect \
  --kubeconfig ~/.kube/config \
  --namespace health-api

# Expected output:
# ✓ ghcr.io/your-org/health-api:latest supports arm64
# ✓ postgres:15 supports arm64
# ✓ redis:7-alpine supports arm64
# ✗ some-legacy-image:v1 does NOT support arm64 (WARNING)
```

**Testing ARM Images Locally:**

```bash
# If you have ARM Mac (M1/M2/M3)
docker run --platform linux/arm64 \
  -it \
  ghcr.io/your-org/health-api:latest \
  bash

# Test functionality
python -c "import sys; print(sys.platform, sys.version)"

# If you DON'T have ARM Mac
# Use QEMU emulation (slower but works)
docker run --platform linux/arm64 \
  -it \
  ghcr.io/your-org/health-api:latest \
  python -c "print('ARM test successful')"
```

**Common ARM Compatibility Issues:**

```bash
# Issue 1: Binary dependencies not available for ARM
# Example: Some Python wheels don't have ARM builds

# Solution: Build from source or find ARM-compatible alternatives
RUN pip install --no-binary=:all: some-package

# Issue 2: Legacy Docker images without ARM support
# Solution: Find alternatives or build your own

# Issue 3: Native code compilation
# Solution: Ensure gcc/build tools installed in Dockerfile
```

**When to Use Temporary Dev OKE Cluster:**

If you encounter ARM-specific issues that can't be tested locally:

```bash
# Create minimal OKE cluster for ARM testing
# Cost: ~$30-50 for a week of testing

# 1. Create small dev cluster (1 node, 2 vCPU, 12GB RAM)
terraform apply -var-file=dev-arm-test.tfvars

# 2. Deploy and test
kubectl apply -f test-deployment.yaml

# 3. Validate ARM-specific behavior
kubectl exec -it test-pod -- uname -m
# Expected: aarch64

# 4. Destroy when done
terraform destroy -var-file=dev-arm-test.tfvars
```

**What Layer 5 Catches:**
- ✅ Missing ARM support in images
- ✅ Binary compatibility issues
- ✅ Architecture-specific bugs
- ✅ Build configuration problems

**What It Doesn't Catch:**
- ❌ Performance differences (until OKE)
- ❌ ARM-specific optimizations
- ❌ Hardware-specific issues

---

## What Can Be Tested Locally

### ✅ Highly Testable (90-100% Confidence)

**Helm Chart Functionality:**
- Template rendering
- Value substitution
- Chart dependencies
- Hooks and lifecycle management
- Resource definitions

**Application Logic:**
- API endpoints
- Business logic
- Data processing (ETL)
- AI model inference
- Database CRUD operations

**Service Communication:**
- DNS resolution
- Service discovery
- Pod-to-pod networking
- ClusterIP services
- Port configurations

**Database Operations:**
- PostgreSQL connections
- Schema migrations
- Query performance (relative)
- Connection pooling
- Data persistence

**Message Queue:**
- RabbitMQ publish/consume
- Queue creation
- Exchange routing
- Message persistence
- Dead letter queues

**Object Storage:**
- MinIO S3 API compatibility
- Bucket operations
- Object CRUD
- Lifecycle policies
- Access policies

**Security Features:**
- RBAC rules
- ServiceAccount permissions
- NetworkPolicies (with Calico)
- Pod Security Standards
- Secret management

**Observability:**
- Prometheus metrics scraping
- Grafana dashboards
- Jaeger distributed tracing
- Loki log aggregation
- AlertManager rules

**Configuration:**
- ConfigMaps
- Secrets
- Environment variables
- Volume mounts
- Init containers

---

### ⚠️ Partially Testable (50-80% Confidence)

**Ingress:**
- ✅ Basic routing rules
- ✅ Path-based routing
- ⚠️ SSL/TLS termination (self-signed locally)
- ❌ OCI Load Balancer specific features
- ❌ Production SSL certificates

**Storage:**
- ✅ PVC provisioning
- ✅ Volume mounting
- ✅ Data persistence
- ⚠️ Performance characteristics
- ❌ OCI Block Volume specific features
- ❌ Cross-zone replication

**Autoscaling:**
- ✅ HPA configuration
- ✅ Metric-based scaling triggers
- ⚠️ Actual scaling behavior (limited load locally)
- ❌ Production-scale load patterns
- ❌ Cost implications of scaling

**Disaster Recovery:**
- ✅ Backup procedures (Velero)
- ✅ Restore procedures (Velero)
- ⚠️ Cross-cluster restore
- ❌ Multi-region failover
- ❌ Production RTO/RPO validation

---

### ❌ Cannot Test Locally (Requires OKE)

**OCI Load Balancer:**
- External IP assignment
- SSL termination behavior
- Health check configuration
- Session affinity
- Timeout settings

**OCI Block Volumes:**
- Volume provisioning speed
- Snapshot operations
- Volume expansion behavior
- Encryption at rest
- Cross-zone replication

**ARM Architecture Specifics:**
- ARM-specific performance
- Memory characteristics
- CPU instruction differences
- Binary compatibility edge cases

**Network Latency:**
- Actual OCI region latency
- Cross-zone communication
- External API calls
- CDN behavior

**Production Scale:**
- Large dataset processing
- High concurrent user load
- Memory pressure at scale
- Disk I/O under load

**Cost Optimization:**
- Actual resource costs
- Cost per request metrics
- Spot instance behavior
- Right-sizing recommendations

**Multi-Region:**
- Cross-region replication
- Failover behavior
- Data synchronization
- Disaster recovery at scale

---

## ARM Architecture Testing

### The ARM Challenge

**Problem:** Oracle OKE uses ARM Ampere A1 processors, but most development happens on x86-64.

**Impact:**
- Container images must support ARM (arm64/aarch64)
- Some libraries don't have ARM builds
- Binary compatibility issues possible
- Performance characteristics differ

**Solution:** Multi-architecture image builds from day one.

---

### Docker Buildx Setup

**Install Buildx:**

```bash
# Check if buildx is available
docker buildx version

# Create multi-arch builder
docker buildx create --name multiarch --driver docker-container --use
docker buildx inspect --bootstrap

# Verify
docker buildx ls
# Expected:
# multiarch * docker-container
#   └─ multiarch0 running linux/amd64, linux/arm64, linux/arm/v7
```

**Configure Registry Authentication:**

```bash
# GitHub Container Registry (ghcr.io)
echo $GITHUB_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Docker Hub
docker login

# Oracle Container Registry (ocir.io)
docker login <region>.ocir.io -u '<tenancy>/<username>' -p '<auth-token>'
```

---

### Building Multi-Arch Images

**Basic Multi-Arch Build:**

```bash
# Build for both amd64 and arm64
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/your-org/health-api:v1.0.0 \
  --tag ghcr.io/your-org/health-api:latest \
  --push \
  ./services/health-api-service

# Why --push is required:
# Multi-arch images use manifest lists which can't be loaded locally
# Must be pushed to registry
```

**Advanced Build with Cache:**

```bash
# Use GitHub Actions cache for faster builds
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/your-org/health-api:v1.0.0 \
  --cache-from type=registry,ref=ghcr.io/your-org/health-api:buildcache \
  --cache-to type=registry,ref=ghcr.io/your-org/health-api:buildcache,mode=max \
  --push \
  ./services/health-api-service
```

**Build All Service Images:**

```bash
#!/bin/bash
# build-all-images.sh

set -e

REGISTRY="ghcr.io/your-org"
VERSION="v1.0.0"

services=(
  "health-api-service"
  "etl-narrative-engine"
  "webauthn-server"
)

for service in "${services[@]}"; do
  echo "Building $service..."
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag ${REGISTRY}/${service}:${VERSION} \
    --tag ${REGISTRY}/${service}:latest \
    --push \
    ./services/${service}
  echo "✓ $service built and pushed"
done

echo "All images built successfully!"
```

---

### Dockerfile Best Practices for Multi-Arch

**Example: Python Service**

```dockerfile
# syntax=docker/dockerfile:1

# Use multi-arch base image
FROM python:3.11-slim

# Install build dependencies (works on both architectures)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
# Most packages work on both architectures
# Some may need compilation from source
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s \
  CMD python -c "import requests; requests.get('http://localhost:8001/health')"

# Runtime
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Example: Go Service**

```dockerfile
# syntax=docker/dockerfile:1

# Build stage
FROM --platform=$BUILDPLATFORM golang:1.21-alpine AS builder

# Build arguments for cross-compilation
ARG TARGETOS
ARG TARGETARCH

WORKDIR /src

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build for target architecture
RUN GOOS=$TARGETOS GOARCH=$TARGETARCH \
    go build -o /app/server .

# Runtime stage
FROM alpine:3.18

# Install ca-certificates for HTTPS
RUN apk --no-cache add ca-certificates

# Copy binary from builder
COPY --from=builder /app/server /app/server

# Non-root user
RUN adduser -D -u 1000 appuser
USER appuser

EXPOSE 8080

CMD ["/app/server"]
```

---

### Validation with KubeArchInspect

**Install:**

```bash
# Requires Go
go install github.com/ArmDeveloperEcosystem/kubearchinspect@latest

# Add to PATH
export PATH=$PATH:$(go env GOPATH)/bin
```

**Validate Helm Charts:**

```bash
# Validate all images in a namespace
kubearchinspect \
  --kubeconfig ~/.kube/config \
  --namespace health-api

# Expected output:
# Checking images in namespace: health-api
# ✓ ghcr.io/your-org/health-api:latest supports arm64
# ✓ postgres:15-alpine supports arm64
# ✓ redis:7-alpine supports arm64
# ✗ some/legacy-image:v1 does NOT support arm64 ⚠️
```

**Validate Before Deployment:**

```bash
# Extract images from Helm template
helm template health-platform ./helm-charts/health-platform \
  --values ./helm-charts/values-production.yaml \
  | grep "image:" \
  | awk '{print $2}' \
  | sort -u > /tmp/images.txt

# Check each image
while read image; do
  echo "Checking $image..."
  docker manifest inspect $image | jq '.manifests[] | select(.platform.architecture == "arm64")'
done < /tmp/images.txt

# If jq output is empty for any image = no ARM support!
```

---

### Common ARM Compatibility Issues

**Issue 1: Python Wheel Not Available for ARM**

```bash
# Error during pip install:
# ERROR: Could not find a version that satisfies the requirement some-package

# Solution 1: Build from source
RUN pip install --no-binary=:all: some-package

# Solution 2: Use conda (better ARM support)
FROM continuumio/miniconda3
RUN conda install -c conda-forge some-package

# Solution 3: Find alternative package
# Example: Use 'Pillow' instead of 'PIL'
```

**Issue 2: Legacy Base Image Without ARM**

```bash
# Error:
# no matching manifest for linux/arm64 in the manifest list

# Solution: Find ARM-compatible alternative
# ❌ FROM ubuntu:16.04
# ✅ FROM ubuntu:22.04

# ❌ FROM node:10
# ✅ FROM node:20-alpine

# Check image support:
docker manifest inspect ubuntu:22.04 | jq '.manifests[].platform'
```

**Issue 3: Native Binary Dependencies**

```bash
# Error during runtime:
# exec format error
# (binary compiled for wrong architecture)

# Solution: Compile during Docker build
RUN gcc -o myapp myapp.c

# Or use pre-built ARM binaries
RUN wget https://example.com/myapp-arm64 -O /usr/local/bin/myapp
```

---

### Testing ARM Images Locally

**On ARM Mac (M1/M2/M3/M4):**

```bash
# Native ARM testing
docker run --platform linux/arm64 \
  -it \
  ghcr.io/your-org/health-api:latest \
  bash

# Verify architecture
uname -m
# Expected: aarch64

# Test application
python -c "import platform; print(platform.machine())"
# Expected: aarch64
```

**On x86-64 Mac/Linux (Intel/AMD):**

```bash
# Use QEMU emulation (slower but works)
docker run --platform linux/arm64 \
  -it \
  ghcr.io/your-org/health-api:latest \
  bash

# Verify emulation is working
uname -m
# Expected: aarch64 (emulated)

# Performance note:
# Emulation is 5-10x slower, only for compatibility testing
```

---

### When to Use Dev OKE Cluster for ARM Testing

**Use Case:** ARM-specific issues that can't be resolved via emulation

**Cost:** ~$30-50 for a week of testing (non-free tier resources)

**Scenario 1: Performance Validation**
- Need to measure actual ARM performance
- Optimize for ARM-specific characteristics
- Compare against x86 benchmarks

**Scenario 2: Binary Compatibility**
- Complex native dependencies
- Custom compiled code
- Edge cases that fail in emulation

**Scenario 3: Final Pre-Production Validation**
- Confidence check before production deployment
- End-to-end testing on actual hardware
- Validate all services together on ARM

**Setup Dev OKE Cluster:**

```bash
# Create minimal dev cluster
cd terraform/environments/dev-arm-test

# dev-arm-test.tfvars
cat > dev-arm-test.tfvars <<EOF
cluster_name = "health-platform-arm-test"
compartment_id = "ocid1.compartment.oc1..xxx"
cluster_type = "BASIC_CLUSTER"  # Free tier
node_pool_size = 1
node_pool_ocpu = 2
node_pool_memory_gb = 12
EOF

# Create cluster
terraform init
terraform plan -var-file=dev-arm-test.tfvars
terraform apply -var-file=dev-arm-test.tfvars

# Wait 10-15 minutes for cluster creation

# Deploy and test
kubectl apply -f test-deployment.yaml

# Validate
kubectl exec -it test-pod -- uname -m
# Expected: aarch64

# Run performance tests
kubectl apply -f performance-test-job.yaml

# IMPORTANT: Destroy when done to avoid costs
terraform destroy -var-file=dev-arm-test.tfvars
```

---

## Storage Class Validation

### Local vs OKE Storage Differences

| Feature | minikube (local-path) | Oracle OKE (oci-bv) |
|---------|---------------------|-------------------|
| **Type** | HostPath | Block Volume (iSCSI) |
| **Performance** | Depends on local SSD | 60 IOPS/GB (balanced) |
| **Encryption** | None | At-rest encryption |
| **Backup** | Manual | OCI snapshot integration |
| **Expansion** | Limited | Online expansion |
| **Replication** | None | Built-in redundancy |
| **Access Mode** | ReadWriteOnce | ReadWriteOnce |

---

### Testing Storage Locally

**Create Test PVC:**

```bash
# Test PVC
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-storage-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: standard
EOF

# Verify provisioning
kubectl get pvc test-storage-pvc
# Expected: STATUS = Bound
```

**Test Data Persistence:**

```bash
# Create pod with volume
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-storage-pod
spec:
  containers:
  - name: app
    image: busybox
    command: ["/bin/sh", "-c"]
    args:
      - |
        echo "Initial data" > /data/test.txt
        cat /data/test.txt
        sleep 3600
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: test-storage-pvc
EOF

# Wait for pod to start
kubectl wait --for=condition=ready pod/test-storage-pod --timeout=60s

# Verify data written
kubectl exec test-storage-pod -- cat /data/test.txt
# Expected: Initial data

# Delete pod (NOT PVC)
kubectl delete pod test-storage-pod

# Recreate pod
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-storage-pod-2
spec:
  containers:
  - name: app
    image: busybox
    command: ["/bin/sh", "-c", "cat /data/test.txt && sleep 3600"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: test-storage-pvc
EOF

# Verify data persisted
kubectl logs test-storage-pod-2
# Expected: Initial data

# Cleanup
kubectl delete pod test-storage-pod-2
kubectl delete pvc test-storage-pvc
```

**Test PostgreSQL Persistence:**

```bash
# Deploy PostgreSQL with persistent storage
helm install postgresql-test bitnami/postgresql \
  --set persistence.size=10Gi \
  --set auth.postgresPassword=testpass123

# Wait for ready
kubectl wait --for=condition=ready pod/postgresql-test-0 --timeout=300s

# Create test data
kubectl exec -it postgresql-test-0 -- \
  psql -U postgres -c "CREATE TABLE test (id INT, data TEXT);"

kubectl exec -it postgresql-test-0 -- \
  psql -U postgres -c "INSERT INTO test VALUES (1, 'persistent data');"

# Verify
kubectl exec -it postgresql-test-0 -- \
  psql -U postgres -c "SELECT * FROM test;"

# Delete pod (StatefulSet will recreate)
kubectl delete pod postgresql-test-0

# Wait for recreation
kubectl wait --for=condition=ready pod/postgresql-test-0 --timeout=300s

# Verify data persisted
kubectl exec -it postgresql-test-0 -- \
  psql -U postgres -c "SELECT * FROM test;"
# Expected: (1, 'persistent data')

# Cleanup
helm uninstall postgresql-test
```

---

### Expected Differences in OKE

**Performance:**
- Local: Depends on SSD speed (typically 500+ MB/s)
- OKE: 60 IOPS/GB baseline (balanced volumes)
- OKE: Up to 25,000 IOPS (high-performance volumes)

**Provisioning Time:**
- Local: Instant (hostPath)
- OKE: 1-2 minutes (block volume creation)

**Snapshot/Backup:**
- Local: Manual copy operations
- OKE: OCI snapshot API integration

**Encryption:**
- Local: None (unless disk-level encryption)
- OKE: Automatic encryption at rest

**Expansion:**
- Local: Delete and recreate PVC
- OKE: Online expansion (`kubectl patch pvc`)

---

## Complete Testing Checklist

Use this comprehensive checklist to validate your deployment before production.

### Phase 1: Infrastructure Validation

```bash
[ ] Terraform validate succeeds
[ ] Terraform fmt passes
[ ] Terraform plan reviewed (no unexpected deletions)
[ ] Cost estimates reviewed ($0 for Always Free tier)
[ ] OCI credentials configured correctly
[ ] Compartment and region verified
```

### Phase 2: Helm Chart Validation

```bash
[ ] helm lint passes for all charts
[ ] helm template renders correctly
[ ] kubeval validates all manifests
[ ] No YAML syntax errors
[ ] All required values provided
[ ] No hardcoded secrets in templates
[ ] Conftest policy checks pass (if using OPA)
[ ] Helm unit tests pass (if implemented)
```

### Phase 3: Local Kubernetes Testing (minikube)

```bash
[ ] minikube starts successfully (6 CPU, 12GB RAM)
[ ] Calico CNI installed and running
[ ] Metrics-server addon enabled
[ ] Ingress addon enabled
[ ] All namespaces created
[ ] Storage provisioner working
```

### Phase 4: Infrastructure Layer Deployment

```bash
[ ] PostgreSQL pods running (health-data namespace)
[ ] PostgreSQL auth pods running (health-auth namespace)
[ ] Redis pods running (2 instances)
[ ] MinIO pods running and healthy
[ ] RabbitMQ pods running and healthy
[ ] No pod restart loops
[ ] Resource limits not exceeded
[ ] PVCs bound and storage allocated
```

### Phase 5: Application Layer Deployment

```bash
[ ] Health API pods running (2-5 replicas)
[ ] ETL Engine pods running (1-3 replicas)
[ ] WebAuthn Server pods running
[ ] Envoy Gateway pods running
[ ] All pods pass readiness probes
[ ] No ImagePullBackOff errors
[ ] Init containers completed successfully
```

### Phase 6: Application Functionality

```bash
[ ] Health API /health endpoint responds (200 OK)
[ ] Health API /ready endpoint responds (200 OK)
[ ] WebAuthn authentication flow works
[ ] PostgreSQL connections successful
[ ] Redis connections successful
[ ] MinIO object storage operations work
[ ] RabbitMQ message publishing works
[ ] RabbitMQ message consuming works
[ ] ETL pipeline processes test data
[ ] API can upload data to MinIO
[ ] API can publish messages to RabbitMQ
```

### Phase 7: Security Testing

```bash
[ ] NetworkPolicies created and enforced
[ ] Default deny policy applied
[ ] Allowed traffic flows work
[ ] Blocked traffic correctly denied
[ ] RBAC roles and bindings created
[ ] ServiceAccounts have correct permissions
[ ] Pod Security Standards enforced
[ ] Pods run as non-root user
[ ] Read-only root filesystem (where applicable)
[ ] Secrets not exposed in logs
[ ] Sealed Secrets controller installed (for production)
```

### Phase 8: Observability Testing

```bash
[ ] Prometheus scrapes all targets
[ ] All ServiceMonitors configured
[ ] Grafana accessible
[ ] Grafana dashboards loaded
[ ] Jaeger UI accessible
[ ] Distributed traces appear in Jaeger
[ ] Loki aggregates logs from all pods
[ ] AlertManager configured
[ ] Test alerts fire correctly
```

### Phase 9: Storage Testing

```bash
[ ] PVCs provision successfully
[ ] PostgreSQL data persists across pod restart
[ ] MinIO data persists across pod restart
[ ] RabbitMQ data persists across pod restart
[ ] Volume expansion works (if needed)
[ ] Storage class selected correctly
[ ] No "Pending" PVCs
```

### Phase 10: Load and Performance

```bash
[ ] Application handles simulated load (ab, k6, or wrk)
[ ] CPU utilization within limits under load
[ ] Memory utilization within limits under load
[ ] No OOMKilled pods
[ ] API latency acceptable (p95 < 500ms)
[ ] HPA scales up under load
[ ] HPA scales down after load decreases
[ ] Database connection pooling works under load
```

### Phase 11: Disaster Recovery

```bash
[ ] Pod restart works (kubectl delete pod)
[ ] Deployment rollback works
[ ] Database backup procedure documented
[ ] Database restore tested
[ ] Velero backup created (if using)
[ ] Velero restore tested (if using)
[ ] Data recovery from PVC snapshots tested
```

### Phase 12: ARM Compatibility

```bash
[ ] All container images support arm64
[ ] Docker buildx multi-arch builds successful
[ ] KubeArchInspect validates all images
[ ] Images pushed to registry
[ ] No "exec format error" in pod logs
[ ] Application runs correctly on ARM (if tested in dev OKE)
```

---

## Practical Setup Instructions

### Complete Setup: Start to Finish

**Prerequisites:**

```bash
# Install required tools
brew install minikube kubectl helm docker
brew install --cask docker  # Docker Desktop (if not already installed)

# Verify installations
minikube version
kubectl version --client
helm version
docker --version
```

**Step 1: Start minikube**

```bash
# Start with recommended configuration
minikube start \
  --cpus=6 \
  --memory=12288 \
  --disk-size=150g \
  --driver=docker \
  --cni=calico \
  --kubernetes-version=1.28.0

# Enable addons
minikube addons enable metrics-server
minikube addons enable ingress
minikube addons enable dashboard

# Verify
kubectl get nodes
kubectl get pods -n kube-system
```

**Step 2: Create Namespaces**

```bash
# Create all required namespaces
kubectl create namespace health-api
kubectl create namespace health-data
kubectl create namespace health-etl
kubectl create namespace health-auth
kubectl create namespace health-observability
kubectl create namespace health-system

# Verify
kubectl get namespaces
```

**Step 3: Deploy Infrastructure (Module 2)**

```bash
# PostgreSQL (health data)
helm install postgresql-health bitnami/postgresql \
  --namespace health-data \
  --set auth.postgresPassword=devpass123 \
  --set primary.persistence.size=10Gi \
  --set primary.resources.requests.cpu=200m \
  --set primary.resources.requests.memory=512Mi

# PostgreSQL (auth)
helm install postgresql-auth bitnami/postgresql \
  --namespace health-auth \
  --set auth.postgresPassword=authpass123 \
  --set primary.persistence.size=5Gi \
  --set primary.resources.requests.cpu=100m \
  --set primary.resources.requests.memory=256Mi

# Redis (health)
helm install redis-health bitnami/redis \
  --namespace health-data \
  --set auth.password=redispass123 \
  --set master.resources.requests.cpu=100m \
  --set master.resources.requests.memory=256Mi

# Redis (auth)
helm install redis-auth bitnami/redis \
  --namespace health-auth \
  --set auth.password=redisauthpass123 \
  --set master.resources.requests.cpu=100m \
  --set master.resources.requests.memory=256Mi

# MinIO
helm install minio bitnami/minio \
  --namespace health-data \
  --set auth.rootUser=minioadmin \
  --set auth.rootPassword=minioadmin123 \
  --set persistence.size=20Gi \
  --set resources.requests.cpu=200m \
  --set resources.requests.memory=512Mi

# RabbitMQ
helm install rabbitmq bitnami/rabbitmq \
  --namespace health-data \
  --set auth.username=admin \
  --set auth.password=rabbitpass123 \
  --set persistence.size=5Gi \
  --set resources.requests.cpu=200m \
  --set resources.requests.memory=512Mi

# Wait for all infrastructure
kubectl wait --for=condition=ready pod \
  --all \
  -n health-data \
  --timeout=600s

kubectl wait --for=condition=ready pod \
  --all \
  -n health-auth \
  --timeout=600s
```

**Step 4: Verify Infrastructure**

```bash
# Check all pods
kubectl get pods -n health-data
kubectl get pods -n health-auth

# Check PVCs
kubectl get pvc -n health-data
kubectl get pvc -n health-auth

# Test PostgreSQL
kubectl exec -it postgresql-health-0 -n health-data -- \
  psql -U postgres -c "SELECT version();"

# Test Redis
kubectl exec -it redis-health-master-0 -n health-data -- \
  redis-cli -a redispass123 PING
# Expected: PONG

# Test MinIO (port-forward first)
kubectl port-forward -n health-data svc/minio 9000:9000 &
curl http://localhost:9000/minio/health/live
# Expected: HTTP 200
```

**Step 5: Deploy Application Services**

```bash
# Build and push images (if not already done)
# See ARM Architecture Testing section

# Deploy Health API
helm install health-api ./helm-charts/health-platform/charts/health-api \
  --namespace health-api \
  --values ./helm-charts/values-dev.yaml

# Deploy ETL Engine
helm install etl-engine ./helm-charts/health-platform/charts/etl-engine \
  --namespace health-etl \
  --values ./helm-charts/values-dev.yaml

# Wait for applications
kubectl wait --for=condition=ready pod \
  -l app=health-api \
  -n health-api \
  --timeout=300s
```

**Step 6: Test Application Functionality**

```bash
# Port-forward Health API
kubectl port-forward -n health-api svc/health-api 8001:8001 &

# Test endpoints
curl http://localhost:8001/health
curl http://localhost:8001/health/ready

# View logs
kubectl logs -f deployment/health-api -n health-api
```

**Step 7: Deploy Observability (Module 5)**

```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace health-observability \
  --set prometheus.prometheusSpec.retention=7d \
  --set prometheus.prometheusSpec.resources.requests.cpu=200m \
  --set prometheus.prometheusSpec.resources.requests.memory=512Mi

# Wait for Prometheus
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=prometheus \
  -n health-observability \
  --timeout=300s

# Access Grafana
kubectl port-forward -n health-observability svc/kube-prometheus-stack-grafana 3000:80 &

# Get Grafana admin password
kubectl get secret -n health-observability kube-prometheus-stack-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode
echo

# Open browser: http://localhost:3000
# Username: admin
# Password: (from above command)
```

**Step 8: Cleanup**

```bash
# Delete everything
helm uninstall health-api -n health-api
helm uninstall etl-engine -n health-etl
helm uninstall postgresql-health -n health-data
helm uninstall postgresql-auth -n health-auth
helm uninstall redis-health -n health-data
helm uninstall redis-auth -n health-auth
helm uninstall minio -n health-data
helm uninstall rabbitmq -n health-data
helm uninstall kube-prometheus-stack -n health-observability

# Delete PVCs
kubectl delete pvc --all -n health-data
kubectl delete pvc --all -n health-auth
kubectl delete pvc --all -n health-observability

# Stop minikube
minikube stop

# Or delete entirely
minikube delete
```

---

## GitHub Actions Integration

Automate validation with GitHub Actions for every commit.

### Workflow File

**File: `.github/workflows/validate-deployment.yml`**

```yaml
name: Validate Kubernetes Deployment

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  helm-lint:
    name: Helm Lint
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Install Helm
        uses: azure/setup-helm@v3
        with:
          version: '3.12.0'

      - name: Lint all Helm charts
        run: |
          helm lint ./helm-charts/health-platform
          helm lint ./helm-charts/health-platform/charts/health-api
          helm lint ./helm-charts/health-platform/charts/etl-engine

  helm-template:
    name: Helm Template Validation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Install Helm
        uses: azure/setup-helm@v3

      - name: Install kubeval
        run: |
          wget https://github.com/instrumenta/kubeval/releases/latest/download/kubeval-linux-amd64.tar.gz
          tar xf kubeval-linux-amd64.tar.gz
          sudo mv kubeval /usr/local/bin

      - name: Render templates
        run: |
          helm template health-platform ./helm-charts/health-platform \
            --values ./helm-charts/values-ci.yaml \
            --output-dir /tmp/rendered

      - name: Validate with kubeval
        run: |
          kubeval /tmp/rendered/**/*.yaml --kubernetes-version 1.28.0 --strict

  deploy-test:
    name: Deploy to k3d
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Install k3d
        run: |
          curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

      - name: Create k3d cluster
        run: |
          k3d cluster create test-cluster --wait
          kubectl cluster-info

      - name: Deploy Helm charts
        run: |
          kubectl create namespace health-api
          kubectl create namespace health-data

          helm install postgresql-test bitnami/postgresql \
            --namespace health-data \
            --set auth.postgresPassword=testpass \
            --set primary.persistence.enabled=false \
            --wait --timeout 5m

          helm install health-api ./helm-charts/health-platform/charts/health-api \
            --namespace health-api \
            --values ./helm-charts/values-ci.yaml \
            --wait --timeout 5m

      - name: Run tests
        run: |
          kubectl get pods -A
          kubectl wait --for=condition=ready pod -l app=health-api -n health-api --timeout=300s

          # Port-forward and test
          kubectl port-forward -n health-api svc/health-api 8001:8001 &
          sleep 5
          curl http://localhost:8001/health

      - name: Cleanup
        if: always()
        run: k3d cluster delete test-cluster

  terraform-validate:
    name: Terraform Validation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0

      - name: Terraform Format Check
        run: |
          cd terraform/environments/production
          terraform fmt -check -recursive

      - name: Terraform Init
        run: |
          cd terraform/environments/production
          terraform init -backend=false

      - name: Terraform Validate
        run: |
          cd terraform/environments/production
          terraform validate

  build-multi-arch:
    name: Build Multi-Arch Images
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Health API
        uses: docker/build-push-action@v4
        with:
          context: ./services/health-api-service
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name == 'push' }}
          tags: |
            ghcr.io/${{ github.repository_owner }}/health-api:${{ github.sha }}
            ghcr.io/${{ github.repository_owner }}/health-api:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push ETL Engine
        uses: docker/build-push-action@v4
        with:
          context: ./services/etl-narrative-engine
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name == 'push' }}
          tags: |
            ghcr.io/${{ github.repository_owner }}/etl-engine:${{ github.sha }}
            ghcr.io/${{ github.repository_owner }}/etl-engine:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## Recommended Timeline

### Week 1: Local Testing Setup and Infrastructure

**Monday:**
- Install minikube, kubectl, helm
- Start minikube with recommended configuration
- Deploy infrastructure layer (PostgreSQL, Redis, MinIO, RabbitMQ)
- Verify all infrastructure pods running

**Tuesday-Wednesday:**
- Build multi-architecture container images
- Push images to container registry
- Deploy application layer (Health API, ETL Engine)
- Test basic application functionality

**Thursday:**
- Deploy observability stack (Prometheus, Grafana, Jaeger)
- Configure dashboards
- Test metrics collection and tracing

**Friday:**
- Implement NetworkPolicies
- Test RBAC configurations
- Document any issues found
- Week 1 retrospective

---

### Week 2: Validation and Optimization

**Monday:**
- Load testing with ab, k6, or wrk
- Monitor resource usage
- Identify bottlenecks
- Adjust resource limits

**Tuesday:**
- Test HPA autoscaling
- Validate disaster recovery procedures
- Test backup and restore
- Document recovery procedures

**Wednesday:**
- Security audit
- Validate Pod Security Standards
- Test secret management
- Review RBAC permissions

**Thursday:**
- Performance tuning
- Optimize resource requests/limits
- Test under constrained resources (4 vCPU, 24GB RAM)
- Ensure fits within Always Free tier limits

**Friday:**
- Complete testing checklist
- Document all findings
- Create runbook for production deployment
- Week 2 retrospective

---

### Week 3: Dev OKE Testing (Optional - ARM Validation)

**Monday:**
- Create minimal dev OKE cluster (2 vCPU, 12GB RAM)
- Cost: ~$30-50 for the week
- Deploy same Helm charts as local testing

**Tuesday-Wednesday:**
- Validate ARM compatibility
- Test all services on actual ARM hardware
- Performance benchmarking
- Identify any ARM-specific issues

**Thursday:**
- Test OCI-specific features
- Load balancer behavior
- Block volume performance
- Snapshot/backup procedures

**Friday:**
- **IMPORTANT: Destroy dev cluster to stop costs**
- Document findings
- Update production deployment plan
- Week 3 retrospective

---

### Week 4: Production Deployment

**Monday:**
- Final review of Terraform plan
- Review production values.yaml
- Ensure all secrets prepared
- Backup existing data (if migrating)

**Tuesday:**
- Apply Terraform (create OKE cluster)
- Wait for cluster provisioning (15-20 minutes)
- Verify cluster health
- Deploy infrastructure layer

**Wednesday:**
- Deploy application layer
- Configure ingress and SSL
- Deploy observability stack
- Initial smoke tests

**Thursday:**
- Comprehensive testing in production
- Monitor for issues
- Performance validation
- Security validation

**Friday:**
- Enable ArgoCD GitOps
- Configure disaster recovery
- Document production runbook
- Celebrate successful deployment! 🎉

---

## Troubleshooting

### Common Issues and Solutions

**Issue: minikube won't start**

```bash
# Error: Exiting due to PROVIDER_DOCKER_NOT_RUNNING

# Solution: Start Docker Desktop
open -a Docker  # macOS
# Or systemctl start docker  # Linux

# Verify Docker is running
docker ps
```

**Issue: Not enough resources**

```bash
# Error: Requested cpu 6000m is more than available

# Solution 1: Reduce resource allocation
minikube start --cpus=4 --memory=8192

# Solution 2: Increase Docker Desktop resources
# Docker Desktop → Preferences → Resources
# Set CPUs: 6, Memory: 12GB
```

**Issue: Calico pods not starting**

```bash
# Check Calico status
kubectl get pods -n kube-system | grep calico

# If failing, reinstall Calico
minikube delete
minikube start --cni=calico --wait=false
kubectl wait --for=condition=ready pod -l k8s-app=calico-node -n kube-system --timeout=600s
```

**Issue: Pod stuck in Pending**

```bash
# Diagnose
kubectl describe pod <pod-name> -n <namespace>

# Common causes:
# 1. Insufficient resources
#    Solution: kubectl top nodes, reduce resource requests

# 2. PVC not bound
#    Solution: kubectl get pvc -A, check storage provisioner

# 3. Node selector mismatch
#    Solution: Check pod spec nodeSelector
```

**Issue: ImagePullBackOff**

```bash
# Diagnose
kubectl describe pod <pod-name> -n <namespace>

# Common causes:
# 1. Image doesn't exist
#    Solution: Verify image name and tag

# 2. Registry authentication
#    Solution: Create imagePullSecret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<username> \
  --docker-password=<token>

# 3. Wrong architecture
#    Solution: Verify image supports current architecture
docker manifest inspect <image>
```

**Issue: Service unreachable**

```bash
# Test DNS resolution
kubectl run test-pod --image=busybox --rm -it -- \
  nslookup <service-name>.<namespace>.svc.cluster.local

# Test connectivity
kubectl run test-pod --image=nicolaka/netshoot --rm -it -- \
  curl -v http://<service-name>.<namespace>.svc.cluster.local:<port>

# Check NetworkPolicy
kubectl get networkpolicy -n <namespace>
kubectl describe networkpolicy <policy-name> -n <namespace>
```

**Issue: Database connection refused**

```bash
# Check if PostgreSQL is running
kubectl get pods -n health-data

# Check PostgreSQL logs
kubectl logs postgresql-health-0 -n health-data

# Test connection from another pod
kubectl run psql-test --image=postgres:15 --rm -it -- \
  psql -h postgresql-health.health-data.svc.cluster.local \
       -U postgres \
       -d postgres

# Check credentials
kubectl get secret postgresql-health -n health-data -o yaml
```

**Issue: Out of disk space**

```bash
# Check disk usage
minikube ssh -- df -h

# Clean up old images
docker system prune -a

# Clean up old volumes
docker volume prune

# Increase disk size (requires recreate)
minikube delete
minikube start --disk-size=200g
```

---

## Summary

### Key Takeaways

1. **minikube is the recommended primary local testing environment**
   - Best production fidelity
   - Supports NetworkPolicies (critical for Module 6)
   - Built-in addons reduce complexity

2. **Multi-layer validation catches different issues**
   - Layer 1: Helm lint (YAML syntax, templates)
   - Layer 2: Dry-run (API server validation)
   - Layer 3: Full deployment (actual functionality)
   - Layer 4: Terraform plan (infrastructure changes)
   - Layer 5: ARM compatibility (architecture support)

3. **ARM architecture requires attention from day one**
   - Build multi-arch images with Docker Buildx
   - Validate with KubeArchInspect
   - Consider optional dev OKE cluster for final validation

4. **Local testing catches 90%+ of issues**
   - Application logic: 100%
   - Service communication: 100%
   - RBAC and NetworkPolicies: 95%
   - Storage: 80%
   - OCI-specific: 0% (requires actual OKE)

5. **Resource requirements are significant**
   - Minimum: 4 vCPU, 8GB RAM
   - Recommended: 6 vCPU, 12GB RAM
   - Optimal: 8 vCPU, 16GB RAM

6. **Testing timeline: 2-4 weeks**
   - Week 1-2: Local testing and validation
   - Week 3: Optional ARM testing in dev OKE
   - Week 4: Production deployment

### Next Steps

After completing local testing:

1. **Review Testing Checklist** (all phases complete)
2. **Proceed to Module 1:** Terraform Infrastructure
3. **Deploy to Oracle OKE** with confidence
4. **Monitor and optimize** in production

---

**Module 0 Complete**: Ready for cloud deployment

**Continue to:** [Module 1: Terraform Infrastructure](./terraform-infrastructure-module.md)
