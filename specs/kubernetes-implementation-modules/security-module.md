# Module 6: Security & RBAC
## NetworkPolicies, RBAC, Pod Security, Sealed Secrets

**Estimated Time:** 3 days
**Dependencies:** Modules 1-4 (Cluster and services deployed)
**Deliverables:** Production-grade security hardening

---

## Objectives

Implement comprehensive security controls:
1. NetworkPolicies - Service-to-service isolation
2. RBAC - Role-Based Access Control
3. Pod Security Standards - Enforce security best practices
4. Sealed Secrets - Encrypt secrets in Git
5. Security scanning - Vulnerability detection

---

## Implementation Steps

### Step 1: Network Policies

**Default Deny Policy:**

```yaml
# default-deny-all.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: health-data
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

**Allow DNS:**

```yaml
# allow-dns.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: health-data
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
```

**Health API Network Policy:**

```yaml
# health-api-netpol.yaml
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
  # Allow from Ingress controller
  - from:
    - namespaceSelector:
        matchLabels:
          name: health-system
      podSelector:
        matchLabels:
          app.kubernetes.io/name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8001

  egress:
  # Allow to PostgreSQL
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-data
      podSelector:
        matchLabels:
          app: postgresql-health
    ports:
    - protocol: TCP
      port: 5432

  # Allow to Redis
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-data
      podSelector:
        matchLabels:
          app: redis-health
    ports:
    - protocol: TCP
      port: 6379

  # Allow to MinIO
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-data
      podSelector:
        matchLabels:
          app: minio
    ports:
    - protocol: TCP
      port: 9000

  # Allow to RabbitMQ
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-data
      podSelector:
        matchLabels:
          app: rabbitmq
    ports:
    - protocol: TCP
      port: 5672

  # Allow to Jaeger
  - to:
    - namespaceSelector:
        matchLabels:
          name: health-observability
      podSelector:
        matchLabels:
          app: jaeger
    ports:
    - protocol: UDP
      port: 6831

  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53

  # Allow HTTPS egress (for external APIs)
  - to:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

Apply all NetworkPolicies:

```bash
kubectl apply -f default-deny-all.yaml
kubectl apply -f allow-dns.yaml
kubectl apply -f health-api-netpol.yaml
# Repeat for other namespaces...

# Verify
kubectl get networkpolicies -A
```

### Step 2: RBAC Configuration

**ServiceAccounts:**

```yaml
# serviceaccounts.yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: health-api-sa
  namespace: health-api
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: etl-engine-sa
  namespace: health-etl
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: webauthn-sa
  namespace: health-auth
```

**Roles:**

```yaml
# health-api-role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: health-api-role
  namespace: health-api
rules:
- apiGroups: [""]
  resources: ["secrets", "configmaps"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
```

**RoleBindings:**

```yaml
# health-api-rolebinding.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: health-api-rolebinding
  namespace: health-api
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: health-api-role
subjects:
- kind: ServiceAccount
  name: health-api-sa
  namespace: health-api
```

**ClusterRoles for Operators:**

```yaml
# developer-clusterrole.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: developer
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "services", "configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: operator
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
```

### Step 3: Pod Security Standards

**Enforce at Namespace Level:**

```yaml
# Add labels to namespaces
kubectl label namespace health-api \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted

kubectl label namespace health-etl \
  pod-security.kubernetes.io/enforce=restricted

kubectl label namespace health-auth \
  pod-security.kubernetes.io/enforce=restricted

kubectl label namespace health-data \
  pod-security.kubernetes.io/enforce=baseline  # Stateful services need some privileges
```

**Verify Pod Security:**

```bash
# Check if pods comply
kubectl get pods -n health-api -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.securityContext}{"\n"}{end}'

# Should show:
# - runAsNonRoot: true
# - runAsUser: 1000
# - fsGroup: 1000
```

### Step 4: Sealed Secrets

**Install Sealed Secrets Controller:**

```bash
# Install controller
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system

# Install kubeseal CLI
brew install kubeseal

# Verify
kubectl get pods -n kube-system | grep sealed-secrets
```

**Create Sealed Secrets:**

```bash
# Create regular secret (locally, NOT committed to Git)
kubectl create secret generic health-api-secrets \
  --from-literal=database-password='MySecurePassword123!' \
  --from-literal=redis-password='RedisPass456!' \
  --from-literal=minio-access-key='minioadmin' \
  --from-literal=minio-secret-key='MinioSecret789!' \
  --from-literal=rabbitmq-password='RabbitPass!' \
  --dry-run=client -o yaml > health-api-secrets.yaml

# Seal it (encrypted, safe to commit)
kubeseal --format yaml < health-api-secrets.yaml > health-api-sealed-secret.yaml

# Apply sealed secret
kubectl apply -f health-api-sealed-secret.yaml -n health-api

# Sealed secret is decrypted by controller in-cluster
kubectl get secrets -n health-api health-api-secrets
```

**Sealed Secret Example:**

```yaml
# health-api-sealed-secret.yaml (safe to commit to Git)
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: health-api-secrets
  namespace: health-api
spec:
  encryptedData:
    database-password: AgBQ8Zl... (encrypted)
    redis-password: AgC7P... (encrypted)
    minio-access-key: AgDf9... (encrypted)
    minio-secret-key: AgEk2... (encrypted)
    rabbitmq-password: AgFx5... (encrypted)
  template:
    metadata:
      name: health-api-secrets
      namespace: health-api
    type: Opaque
```

### Step 5: Security Scanning

**Install Trivy Operator:**

```bash
# Install trivy-operator
helm repo add aqua https://aquasecurity.github.io/helm-charts/
helm install trivy-operator aqua/trivy-operator \
  --namespace health-system \
  --create-namespace

# Wait for scans to complete
kubectl get vulnerabilityreports -A

# Check high/critical vulnerabilities
kubectl get vulnerabilityreports -A -o json | \
  jq '.items[] | select(.report.summary.criticalCount > 0 or .report.summary.highCount > 0) | {name:.metadata.name, critical:.report.summary.criticalCount, high:.report.summary.highCount}'
```

**Run kube-bench:**

```bash
# Run CIS Kubernetes Benchmark
kubectl apply -f https://raw.githubusercontent.com/aquasecurity/kube-bench/main/job.yaml

# Check results
kubectl logs job/kube-bench

# Look for [FAIL] and [WARN] items
```

**Install Falco (Runtime Security):**

```bash
# Install Falco for runtime threat detection
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco \
  --create-namespace \
  --set falco.grpc.enabled=true \
  --set falco.grpcOutput.enabled=true

# Check alerts
kubectl logs -f daemonset/falco -n falco
```

---

## Verification

```bash
# Test NetworkPolicies
# From health-api pod, should be able to reach PostgreSQL
kubectl exec -it deployment/health-api -n health-api -- \
  nc -zv postgresql-health.health-data.svc.cluster.local 5432

# Should NOT be able to reach WebAuthn server
kubectl exec -it deployment/health-api -n health-api -- \
  nc -zv webauthn-server.health-auth.svc.cluster.local 8080
# Expected: Connection timed out (blocked by NetworkPolicy)

# Check RBAC
kubectl auth can-i get pods --as=system:serviceaccount:health-api:health-api-sa -n health-api
# Expected: yes

kubectl auth can-i delete pods --as=system:serviceaccount:health-api:health-api-sa -n health-api
# Expected: no

# Check Pod Security
kubectl get pods -n health-api -o jsonpath='{.items[0].spec.securityContext}'
# Should show restricted security context

# Verify Sealed Secrets working
kubectl get sealedsecrets -n health-api
kubectl get secrets -n health-api health-api-secrets
```

---

## Security Checklist

### Network Security
- [ ] Default deny NetworkPolicies applied to all namespaces
- [ ] Explicit allow rules for service-to-service communication
- [ ] DNS egress allowed
- [ ] Ingress only from ingress controller
- [ ] No direct pod-to-pod communication across namespaces

### Access Control
- [ ] ServiceAccounts created for all applications
- [ ] Roles defined with least privilege
- [ ] RoleBindings applied
- [ ] ClusterRoles for operators/developers
- [ ] No pods running as default ServiceAccount

### Pod Security
- [ ] Pod Security Standards enforced (restricted)
- [ ] All pods run as non-root
- [ ] Read-only root filesystems where possible
- [ ] No privilege escalation
- [ ] Capabilities dropped (drop ALL)
- [ ] Seccomp profiles applied

### Secrets Management
- [ ] Sealed Secrets controller deployed
- [ ] All secrets encrypted with SealedSecrets
- [ ] No plaintext secrets in Git
- [ ] Secrets rotated regularly
- [ ] Secret access audited

### Scanning & Monitoring
- [ ] Trivy operator scanning images
- [ ] No critical vulnerabilities in production images
- [ ] kube-bench CIS benchmark passed
- [ ] Falco runtime security monitoring
- [ ] Security alerts configured

---

## Common Security Issues & Fixes

### Issue: Pod fails Pod Security Standard

```bash
# Error: pods "health-api-xxx" is forbidden: violates PodSecurity "restricted:latest"

# Fix: Update deployment securityContext
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
  containers:
  - name: app
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      readOnlyRootFilesystem: true
```

### Issue: NetworkPolicy blocking required traffic

```bash
# Debug: Check if policy exists
kubectl describe networkpolicy <name> -n <namespace>

# Test connectivity
kubectl run -it --rm debug \
  --image=nicolaka/netshoot \
  --restart=Never \
  -n health-api \
  -- nc -zv postgresql-health.health-data.svc.cluster.local 5432

# Fix: Add explicit allow rule
```

---

## Success Criteria

- [ ] All namespaces have default deny NetworkPolicies
- [ ] Service-to-service communication working with explicit allows
- [ ] All pods run with restricted security context
- [ ] RBAC configured for all ServiceAccounts
- [ ] All secrets managed via Sealed Secrets
- [ ] No critical vulnerabilities in container images
- [ ] kube-bench score > 90%
- [ ] Falco monitoring active
- [ ] Security policies documented in runbook

---

**Module 6 Complete**: Production security hardening implemented
