# Module 3: Helm Chart - WebAuthn Stack
## Authentication & Authorization Services

**Estimated Time:** 1 week
**Dependencies:** Module 1 (OKE cluster), Module 2 (PostgreSQL, Redis for auth)
**Deliverables:** WebAuthn authentication fully operational in Kubernetes

---

## Objectives

Deploy the existing WebAuthn stack (currently in `webauthn-stack/docker/`) to Kubernetes:
1. WebAuthn Server (FIDO2 authentication)
2. Envoy Gateway (reverse proxy + JWT verification)
3. Connect to PostgreSQL (webauthn-auth) and Redis (webauthn-sessions)
4. Configure Ingress for public access
5. Integrate Jaeger tracing

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  health-auth namespace                                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Internet                                                │
│      │                                                   │
│      ▼                                                   │
│  ┌────────────────┐                                     │
│  │ Ingress (NGINX)│                                     │
│  │ auth.domain    │                                     │
│  └────────┬───────┘                                     │
│           │                                              │
│           ▼                                              │
│  ┌────────────────┐                                     │
│  │ Envoy Gateway  │ (JWT verification, rate limiting)   │
│  │  Port: 8080    │                                     │
│  └────────┬───────┘                                     │
│           │                                              │
│           ▼                                              │
│  ┌────────────────┐                                     │
│  │ WebAuthn Server│ (FIDO2 registration/authentication)│
│  │  Port: 8080    │                                     │
│  └────┬───────┬───┘                                     │
│       │       │                                          │
│       │       └──────────┐                              │
│       ▼                  ▼                               │
│  PostgreSQL          Redis                              │
│  (webauthn-auth)     (sessions)                         │
│  health-data ns      health-data ns                     │
└──────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Create WebAuthn Chart Structure

```bash
mkdir -p helm-charts/health-platform/charts/webauthn-stack/templates
cd helm-charts/health-platform/charts/webauthn-stack
```

**File: `Chart.yaml`**

```yaml
apiVersion: v2
name: webauthn-stack
description: WebAuthn authentication stack (FIDO2 + Envoy Gateway)
type: application
version: 1.0.0
appVersion: "1.0.0"
```

**File: `values.yaml`**

```yaml
namespace: health-auth

# WebAuthn Server
webauthn:
  enabled: true
  replicaCount: 2

  image:
    repository: ghcr.io/your-org/webauthn-server
    tag: "latest"
    pullPolicy: IfNotPresent

  service:
    type: ClusterIP
    port: 8080

  resources:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi

  config:
    relyingPartyId: "auth.yourdomain.com"
    relyingPartyName: "Health Data Platform"
    relyingPartyOrigin: "https://auth.yourdomain.com"

  # Database connection (PostgreSQL in health-data namespace)
  database:
    host: postgresql-auth.health-data.svc.cluster.local
    port: 5432
    name: webauthn
    user: webauthn
    # Password from secret

  # Redis connection
  redis:
    host: redis-auth.health-data.svc.cluster.local
    port: 6379
    # Password from secret

  # Jaeger tracing
  jaeger:
    enabled: true
    agentHost: jaeger-agent.health-observability.svc.cluster.local
    agentPort: 6831

# Envoy Gateway
envoy:
  enabled: true
  replicaCount: 2

  image:
    repository: envoyproxy/envoy
    tag: "v1.28-latest"
    pullPolicy: IfNotPresent

  service:
    type: ClusterIP
    port: 8000

  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi

  config:
    jwksUri: "http://webauthn-server.health-auth.svc.cluster.local:8080/.well-known/jwks.json"
    jwtIssuer: "https://auth.yourdomain.com"
    cacheDuration: 300  # 5 minutes

# Ingress
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
  host: auth.yourdomain.com
  tls:
    secretName: webauthn-tls

# Horizontal Pod Autoscaler
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70

# Secrets (use Sealed Secrets in production)
secrets:
  database:
    password: "CHANGE_ME"
  redis:
    password: "CHANGE_ME"
  jwt:
    privateKey: "CHANGE_ME_BASE64_ENCODED_RSA_PRIVATE_KEY"
    publicKey: "CHANGE_ME_BASE64_ENCODED_RSA_PUBLIC_KEY"
```

### Step 2: Create WebAuthn Server Deployment

**File: `templates/webauthn-deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webauthn-server
  namespace: {{ .Values.namespace }}
  labels:
    app: webauthn-server
spec:
  replicas: {{ .Values.webauthn.replicaCount }}
  selector:
    matchLabels:
      app: webauthn-server
  template:
    metadata:
      labels:
        app: webauthn-server
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: webauthn-sa
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      containers:
      - name: webauthn-server
        image: "{{ .Values.webauthn.image.repository }}:{{ .Values.webauthn.image.tag }}"
        imagePullPolicy: {{ .Values.webauthn.image.pullPolicy }}

        ports:
        - name: http
          containerPort: 8080
          protocol: TCP

        env:
        - name: RELYING_PARTY_ID
          value: {{ .Values.webauthn.config.relyingPartyId | quote }}
        - name: RELYING_PARTY_NAME
          value: {{ .Values.webauthn.config.relyingPartyName | quote }}
        - name: RELYING_PARTY_ORIGIN
          value: {{ .Values.webauthn.config.relyingPartyOrigin | quote }}

        - name: DATABASE_URL
          value: "postgresql://{{ .Values.webauthn.database.user }}:$(DB_PASSWORD)@{{ .Values.webauthn.database.host }}:{{ .Values.webauthn.database.port }}/{{ .Values.webauthn.database.name }}"
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: webauthn-secrets
              key: database-password

        - name: REDIS_URL
          value: "redis://:$(REDIS_PASSWORD)@{{ .Values.webauthn.redis.host }}:{{ .Values.webauthn.redis.port }}/0"
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: webauthn-secrets
              key: redis-password

        - name: JWT_PRIVATE_KEY
          valueFrom:
            secretKeyRef:
              name: webauthn-secrets
              key: jwt-private-key
        - name: JWT_PUBLIC_KEY
          valueFrom:
            secretKeyRef:
              name: webauthn-secrets
              key: jwt-public-key

        {{- if .Values.webauthn.jaeger.enabled }}
        - name: JAEGER_AGENT_HOST
          value: {{ .Values.webauthn.jaeger.agentHost | quote }}
        - name: JAEGER_AGENT_PORT
          value: {{ .Values.webauthn.jaeger.agentPort | quote }}
        {{- end }}

        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10

        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5

        resources:
          {{- toYaml .Values.webauthn.resources | nindent 12 }}

        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000

        volumeMounts:
        - name: tmp
          mountPath: /tmp

      volumes:
      - name: tmp
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: webauthn-server
  namespace: {{ .Values.namespace }}
spec:
  type: {{ .Values.webauthn.service.type }}
  ports:
  - port: {{ .Values.webauthn.service.port }}
    targetPort: http
    protocol: TCP
    name: http
  selector:
    app: webauthn-server
```

### Step 3: Create Envoy Gateway Deployment

**File: `templates/envoy-deployment.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: envoy-config
  namespace: {{ .Values.namespace }}
data:
  envoy.yaml: |
    admin:
      address:
        socket_address:
          address: 127.0.0.1
          port_value: 9901

    static_resources:
      listeners:
      - name: listener_0
        address:
          socket_address:
            address: 0.0.0.0
            port_value: 8000
        filter_chains:
        - filters:
          - name: envoy.filters.network.http_connection_manager
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
              stat_prefix: ingress_http
              access_log:
              - name: envoy.access_loggers.stdout
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
              http_filters:
              - name: envoy.filters.http.jwt_authn
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.http.jwt_authn.v3.JwtAuthentication
                  providers:
                    webauthn_jwt:
                      issuer: {{ .Values.envoy.config.jwtIssuer | quote }}
                      remote_jwks:
                        http_uri:
                          uri: {{ .Values.envoy.config.jwksUri | quote }}
                          cluster: webauthn_server
                          timeout: 5s
                        cache_duration:
                          seconds: {{ .Values.envoy.config.cacheDuration }}
                  rules:
                  - match:
                      prefix: /api
                    requires:
                      provider_name: webauthn_jwt
              - name: envoy.filters.http.router
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
              route_config:
                name: local_route
                virtual_hosts:
                - name: backend
                  domains: ["*"]
                  routes:
                  - match:
                      prefix: "/"
                    route:
                      cluster: webauthn_server

      clusters:
      - name: webauthn_server
        connect_timeout: 0.25s
        type: STRICT_DNS
        lb_policy: ROUND_ROBIN
        load_assignment:
          cluster_name: webauthn_server
          endpoints:
          - lb_endpoints:
            - endpoint:
                address:
                  socket_address:
                    address: webauthn-server.{{ .Values.namespace }}.svc.cluster.local
                    port_value: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: envoy-gateway
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.envoy.replicaCount }}
  selector:
    matchLabels:
      app: envoy-gateway
  template:
    metadata:
      labels:
        app: envoy-gateway
    spec:
      containers:
      - name: envoy
        image: "{{ .Values.envoy.image.repository }}:{{ .Values.envoy.image.tag }}"
        ports:
        - name: http
          containerPort: 8000
        - name: admin
          containerPort: 9901
        volumeMounts:
        - name: config
          mountPath: /etc/envoy
        resources:
          {{- toYaml .Values.envoy.resources | nindent 12 }}
      volumes:
      - name: config
        configMap:
          name: envoy-config
---
apiVersion: v1
kind: Service
metadata:
  name: envoy-gateway
  namespace: {{ .Values.namespace }}
spec:
  type: {{ .Values.envoy.service.type }}
  ports:
  - port: {{ .Values.envoy.service.port }}
    targetPort: http
    name: http
  selector:
    app: envoy-gateway
```

### Step 4: Create Ingress

**File: `templates/ingress.yaml`**

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: webauthn-ingress
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
            name: envoy-gateway
            port:
              number: 8000
{{- end }}
```

### Step 5: Create Secrets and RBAC

**File: `templates/secrets.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.namespace }}
---
apiVersion: v1
kind: Secret
metadata:
  name: webauthn-secrets
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  database-password: {{ .Values.secrets.database.password | quote }}
  redis-password: {{ .Values.secrets.redis.password | quote }}
  jwt-private-key: {{ .Values.secrets.jwt.privateKey | quote }}
  jwt-public-key: {{ .Values.secrets.jwt.publicKey | quote }}
```

**File: `templates/rbac.yaml`**

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: webauthn-sa
  namespace: {{ .Values.namespace }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: webauthn-role
  namespace: {{ .Values.namespace }}
rules:
- apiGroups: [""]
  resources: ["secrets", "configmaps"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: webauthn-rolebinding
  namespace: {{ .Values.namespace }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: webauthn-role
subjects:
- kind: ServiceAccount
  name: webauthn-sa
  namespace: {{ .Values.namespace }}
```

---

## Deployment

```bash
# 1. Generate JWT keys
ssh-keygen -t rsa -b 4096 -m PEM -f jwt_rsa_key
openssl rsa -in jwt_rsa_key -pubout -outform PEM -out jwt_rsa_key.pub

# Base64 encode for secrets
JWT_PRIVATE=$(cat jwt_rsa_key | base64)
JWT_PUBLIC=$(cat jwt_rsa_key.pub | base64)

# 2. Update values
cat > values-production.yaml <<EOF
webauthn-stack:
  ingress:
    host: auth.health-platform.example.com
  secrets:
    database:
      password: "$(openssl rand -base64 32)"
    redis:
      password: "$(openssl rand -base64 32)"
    jwt:
      privateKey: "$JWT_PRIVATE"
      publicKey: "$JWT_PUBLIC"
EOF

# 3. Deploy
helm install webauthn-stack ./helm-charts/health-platform/charts/webauthn-stack \
  --namespace health-auth \
  --create-namespace \
  --values values-production.yaml

# 4. Verify
kubectl get pods -n health-auth
kubectl get ingress -n health-auth
```

---

## Testing

```bash
# Test registration endpoint
curl -X POST https://auth.yourdomain.com/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","displayName":"Test User"}'

# Test authentication endpoint
curl https://auth.yourdomain.com/authenticate \
  -H "Content-Type: application/json"

# Check logs
kubectl logs -f deployment/webauthn-server -n health-auth

# Check Envoy stats
kubectl port-forward deployment/envoy-gateway 9901:9901 -n health-auth
curl http://localhost:9901/stats
```

---

## Success Criteria

- [ ] WebAuthn Server pods running (2 replicas)
- [ ] Envoy Gateway pods running (2 replicas)
- [ ] Ingress configured with SSL
- [ ] Connected to PostgreSQL (webauthn-auth database)
- [ ] Connected to Redis (sessions)
- [ ] JWT signing/verification working
- [ ] Registration flow functional
- [ ] Authentication flow functional
- [ ] Jaeger traces visible

---

**Module 3 Complete**: WebAuthn authentication operational
