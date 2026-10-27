{{- define "bxmesh.labels" -}}
app.kubernetes.io/part-of: bxmesh.net
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}

{{/* The pod and container security the dmz zone's Pod Security (restricted) requires. */}}
{{- define "bxmesh.podSecurity" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .uid }}
fsGroup: {{ .uid }}
fsGroupChangePolicy: OnRootMismatch
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "bxmesh.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: [ALL]
{{- end }}

{{- define "bxmesh.image" -}}
{{- printf "%s:%s" .repository (required (printf "%s: tag is required (CI writes it)" .repository) .tag) | quote -}}
{{- end }}
