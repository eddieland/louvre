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

{{/*
The database Louvre reads, as DATABASE_URL (docs/DEPLOY.md). A URL the chart composes carries no password: libpq takes
it from PGPASSWORD, so a password from a Secret never has to be spliced into a string. Louvre's container and the
chart's test both read these.
*/}}
{{- define "louvre.database.env" -}}
{{- $external := .Values.externalDatabase }}
{{- if and (not .Values.postgresql.enabled) $external.existingSecretUrlKey }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      {{- $missing := "externalDatabase.existingSecretUrlKey needs externalDatabase.existingSecret." }}
      name: {{ required $missing $external.existingSecret }}
      key: {{ $external.existingSecretUrlKey }}
{{- else }}
- name: DATABASE_URL
{{- if .Values.postgresql.enabled }}
{{- $auth := .Values.postgresql.auth }}
  {{- /* Inside the cluster, to a database without a certificate. */}}
  {{- $host := include "louvre.postgresql.fullname" . }}
  {{- $where := printf "%s:5432/%s" $host (urlquery $auth.database) }}
  value: {{ printf "postgresql://%s@%s?sslmode=disable" (urlquery $auth.username) $where | quote }}
{{- else }}
{{- $missing := "Name a database: set externalDatabase.host, or postgresql.enabled=true for a bundled one." }}
{{- $host := required $missing $external.host }}
  {{- $where := printf "%s:%v/%s" $host $external.port (urlquery $external.database) }}
  value: {{ printf "postgresql://%s@%s?sslmode=%s" (urlquery $external.username) $where $external.sslMode | quote }}
{{- end }}
- name: PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "louvre.database.secretName" . }}
      key: {{ include "louvre.database.secretKey" . }}
{{- end }}
{{- end }}

{{/* Louvre's own settings (docs/DEPLOY.md), each set only when it is given. */}}
{{- define "louvre.config.env" -}}
{{- $config := .Values.config }}
{{- with $config.baseUrl }}
- name: LOUVRE_BASE_URL
  value: {{ . | trimSuffix "/" | quote }}
{{- end }}
{{- with $config.allowedLogins }}
- name: LOUVRE_ALLOWED_LOGINS
  value: {{ join "," . | quote }}
{{- end }}
{{- if $config.secureCookies }}
- name: LOUVRE_SECURE_COOKIES
  value: "1"
{{- end }}
{{- if $config.demo }}
- name: LOUVRE_DEMO
  value: "1"
{{- end }}
{{- if $config.devSignIn }}
- name: LOUVRE_DEV_SIGN_IN
  value: "1"
{{- end }}
{{- with $config.github.clientId }}
- name: LOUVRE_GITHUB_CLIENT_ID
  value: {{ . | quote }}
- name: LOUVRE_GITHUB_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      {{- if $config.github.existingSecret }}
      name: {{ $config.github.existingSecret }}
      key: {{ $config.github.existingSecretKey }}
      {{- else }}
      name: {{ printf "%s-github" (include "louvre.fullname" $) }}
      key: client-secret
      {{- end }}
{{- end }}
{{- end }}
