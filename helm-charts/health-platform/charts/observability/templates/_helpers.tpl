{{/*
Expand the name of the chart.
*/}}
{{- define "observability.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "observability.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "observability.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "observability.labels" -}}
helm.sh/chart: {{ include "observability.chart" . }}
{{ include "observability.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: health-platform
environment: {{ .Values.global.environment }}
cluster: {{ .Values.global.clusterName }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "observability.selectorLabels" -}}
app.kubernetes.io/name: {{ include "observability.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "observability.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "observability.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Jaeger labels
*/}}
{{- define "observability.jaeger.labels" -}}
{{ include "observability.labels" . }}
app.kubernetes.io/component: jaeger
{{- end }}

{{/*
Jaeger selector labels
*/}}
{{- define "observability.jaeger.selectorLabels" -}}
app: jaeger
{{- end }}

{{/*
Return the appropriate apiVersion for NetworkPolicy
*/}}
{{- define "observability.networkPolicy.apiVersion" -}}
{{- if semverCompare ">=1.7-0" .Capabilities.KubeVersion.GitVersion -}}
networking.k8s.io/v1
{{- else -}}
extensions/v1beta1
{{- end -}}
{{- end -}}

{{/*
Return the appropriate apiVersion for Ingress
*/}}
{{- define "observability.ingress.apiVersion" -}}
{{- if semverCompare ">=1.19-0" .Capabilities.KubeVersion.GitVersion -}}
networking.k8s.io/v1
{{- else if semverCompare ">=1.14-0" .Capabilities.KubeVersion.GitVersion -}}
networking.k8s.io/v1beta1
{{- else -}}
extensions/v1beta1
{{- end -}}
{{- end -}}

{{/*
Prometheus instance name
*/}}
{{- define "observability.prometheus.name" -}}
{{- printf "%s-kube-prometheus-prometheus" .Release.Name }}
{{- end }}

{{/*
Grafana instance name
*/}}
{{- define "observability.grafana.name" -}}
{{- printf "%s-grafana" .Release.Name }}
{{- end }}

{{/*
Loki instance name
*/}}
{{- define "observability.loki.name" -}}
{{- printf "%s-loki" .Release.Name }}
{{- end }}

{{/*
Validate values
*/}}
{{- define "observability.validateValues" -}}
{{- if and .Values.jaeger.enabled .Values.jaeger.persistence.enabled }}
  {{- if not .Values.jaeger.persistence.storageClass }}
    {{- if not .Values.global.storageClass }}
      {{- fail "Either jaeger.persistence.storageClass or global.storageClass must be set when persistence is enabled" }}
    {{- end }}
  {{- end }}
{{- end }}
{{- end }}
