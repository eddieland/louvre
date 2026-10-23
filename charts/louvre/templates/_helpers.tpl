{{/* The chart's name, cut to the 63 characters a Kubernetes name allows. */}}
{{- define "louvre.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* The release's full name: the release name, with the chart's name unless the release name already holds it. */}}
{{- define "louvre.fullname" -}}
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

{{- define "louvre.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "louvre.labels" -}}
helm.sh/chart: {{ include "louvre.chart" . }}
{{ include "louvre.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "louvre.selectorLabels" -}}
app.kubernetes.io/name: {{ include "louvre.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: web
{{- end }}

{{- define "louvre.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "louvre.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* An image reference from a block with repository, tag, and digest; the digest wins when set. */}}
{{- define "louvre.imageRef" -}}
{{- $image := index . 0 }}
{{- $defaultTag := index . 1 }}
{{- if $image.digest }}
{{- printf "%s@%s" $image.repository $image.digest }}
{{- else }}
{{- printf "%s:%s" $image.repository (toString ($image.tag | default $defaultTag)) }}
{{- end }}
{{- end }}

{{- define "louvre.postgresql.fullname" -}}
{{- printf "%s-postgresql" (include "louvre.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "louvre.postgresql.selectorLabels" -}}
app.kubernetes.io/name: {{ include "louvre.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: postgresql
{{- end }}

{{- define "louvre.postgresql.labels" -}}
helm.sh/chart: {{ include "louvre.chart" . }}
{{ include "louvre.postgresql.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.postgresql.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
The Secret and key holding the database password, from whichever database is in use. A password given in values, or
the bundled database's generated one, lives in the chart's own Secret.
*/}}
{{- define "louvre.database.secretName" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.existingSecret | default (include "louvre.postgresql.fullname" .) }}
{{- else }}
{{- .Values.externalDatabase.existingSecret | default (printf "%s-database" (include "louvre.fullname" .)) }}
{{- end }}
{{- end }}

{{- define "louvre.database.secretKey" -}}
{{- if and .Values.postgresql.enabled .Values.postgresql.auth.existingSecret }}
{{- .Values.postgresql.auth.existingSecretPasswordKey }}
{{- else if and (not .Values.postgresql.enabled) .Values.externalDatabase.existingSecret }}
{{- .Values.externalDatabase.existingSecretPasswordKey }}
{{- else }}
{{- "password" }}
{{- end }}
{{- end }}

{{/* libpq's variables for the database in use: Louvre's container and the chart's test both read them. */}}
{{- define "louvre.database.env" -}}
{{- if .Values.postgresql.enabled }}
- name: PGHOST
  value: {{ include "louvre.postgresql.fullname" . | quote }}
- name: PGPORT
  value: "5432"
- name: PGDATABASE
  value: {{ .Values.postgresql.auth.database | quote }}
- name: PGUSER
  value: {{ .Values.postgresql.auth.username | quote }}
# Inside the cluster, to a database without a certificate.
- name: PGSSLMODE
  value: disable
{{- else }}
{{- $missing := "Name a database: set externalDatabase.host, or postgresql.enabled=true for a bundled one." }}
- name: PGHOST
  value: {{ required $missing .Values.externalDatabase.host | quote }}
- name: PGPORT
  value: {{ .Values.externalDatabase.port | quote }}
- name: PGDATABASE
  value: {{ .Values.externalDatabase.database | quote }}
- name: PGUSER
  value: {{ .Values.externalDatabase.username | quote }}
- name: PGSSLMODE
  value: {{ .Values.externalDatabase.sslMode | quote }}
{{- end }}
- name: PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "louvre.database.secretName" . }}
      key: {{ include "louvre.database.secretKey" . }}
{{- end }}
