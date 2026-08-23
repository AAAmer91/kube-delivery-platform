{{/*
Expand the name of the chart.
*/}}
{{- define "kube-delivery.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "kube-delivery.fullname" -}}
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
Common labels
*/}}
{{- define "kube-delivery.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "kube-delivery.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: kube-delivery-platform
{{- end }}

{{/*
Shipment API Selector labels
*/}}
{{- define "kube-delivery.shipmentApi.selectorLabels" -}}
app.kubernetes.io/name: shipment-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Tracking Worker Selector labels
*/}}
{{- define "kube-delivery.trackingWorker.selectorLabels" -}}
app.kubernetes.io/name: tracking-worker
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Resolve application images by immutable digest when provided, otherwise by tag.
*/}}
{{- define "kube-delivery.shipmentApi.image" -}}
{{- if .Values.shipmentApi.image.digest -}}
{{- printf "%s@%s" .Values.shipmentApi.image.repository .Values.shipmentApi.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.shipmentApi.image.repository .Values.shipmentApi.image.tag -}}
{{- end -}}
{{- end }}

{{- define "kube-delivery.trackingWorker.image" -}}
{{- if .Values.trackingWorker.image.digest -}}
{{- printf "%s@%s" .Values.trackingWorker.image.repository .Values.trackingWorker.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.trackingWorker.image.repository .Values.trackingWorker.image.tag -}}
{{- end -}}
{{- end }}

{{/*
PostgreSQL Selector labels
*/}}
{{- define "kube-delivery.postgres.selectorLabels" -}}
app.kubernetes.io/name: postgres
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: database
{{- end }}

{{/*
NATS Selector labels
*/}}
{{- define "kube-delivery.nats.selectorLabels" -}}
app.kubernetes.io/name: nats
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: message-broker
{{- end }}
