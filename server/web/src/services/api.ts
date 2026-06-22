import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

export interface NodeCheckResult {
  node_id: string
  status: string  // "ok" | "warning" | "error"
  message: string
}

export interface Script {
  id: string
  name: string
  description: string
  flow_json: string
  project_id: string | null
  default_client_id: string | null
  created_at: string
  updated_at: string
  checks?: NodeCheckResult[]
}

export interface Client {
  id: string
  name: string
  platform: string
  last_seen: string
  status: string
  project_ids: string[]
  gpu_enabled: boolean
}

export interface Execution {
  id: string
  script_id: string
  client_id: string
  status: string
  started_at: string | null
  finished_at: string | null
  log: string
}

export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface Marker {
  id: string
  project_id: string
  name: string
  type: 'point' | 'box'
  created_at: string
}

export interface MarkerCapture {
  id: string
  name: string
  type: 'point' | 'box'
  captured: boolean
}

export interface MarkerCaptureData {
  id: string
  name: string
  type: 'point' | 'box'
  captured: boolean
  x: number | null
  y: number | null
  w: number | null
  h: number | null
  window_x: number | null
  window_y: number | null
  window_w: number | null
  window_h: number | null
}

export interface Template {
  id: string
  project_id: string
  name: string
  filename: string
  source_w: number | null
  source_h: number | null
  window_title: string | null
  created_at: string
}

export interface ClientWindow {
  title: string
  process: string
  x: number
  y: number
  w: number
  h: number
}

export interface MarkerWindow {
  window_title: string
  window_w: number
  window_h: number
  client_count: number
  client_ids: string[]
}

export interface WindowBinding {
  window_title: string
  window_process: string | null
  window_x: number | null
  window_y: number | null
  window_w: number
  window_h: number
  updated_at: string | null
}

export interface GlobalVariable {
  id: string
  project_id: string
  name: string
  value: any
  updated_at: string
}

export interface AIModel {
  id: string
  type: 'local' | 'third_party'
  provider: 'paddleocr' | 'qwen' | 'glm'
  name: string
  api_key: string
  base_url: string
  model_name: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface OCRStatus {
  installed: boolean
  loaded: boolean
  loading: boolean
  error: string | null
  variant: 'mobile' | 'server'
}

export const api = {
  // Scripts
  getScripts: () => http.get<Script[]>('/scripts').then(r => r.data),
  getScript: (id: string) => http.get<Script>(`/scripts/${id}`).then(r => r.data),
  createScript: (data: { name: string; description?: string; flow_json?: string }) =>
    http.post<Script>('/scripts', data).then(r => r.data),
  updateScript: (id: string, data: Partial<Script>) =>
    http.put<Script>(`/scripts/${id}`, data).then(r => r.data),
  deleteScript: (id: string) => http.delete(`/scripts/${id}`).then(r => r.data),
  runScript: (id: string, client_id: string) =>
    http.post<Execution>(`/scripts/${id}/run`, { client_id }).then(r => r.data),
  stopScript: (id: string, execution_id: string) =>
    http.post(`/scripts/${id}/stop`, null, { params: { execution_id } }).then(r => r.data),
  getExecutions: (id: string) =>
    http.get<Execution[]>(`/scripts/${id}/executions`).then(r => r.data),
  debugExecuteNode: (id: string, node_id: string, client_id: string, flow_json: any, initial_variables: Record<string, any> = {}) =>
    http.post(`/scripts/${id}/debug/execute-node`, { client_id, node_id, flow_json, initial_variables }).then(r => r.data),
  debugRunToNode: (id: string, node_id: string, client_id: string, flow_json: any) =>
    http.post(`/scripts/${id}/debug/run-to-node`, { client_id, node_id, flow_json }).then(r => r.data),

  // Clients
  getClients: () => http.get<Client[]>('/clients').then(r => r.data),
  stopClient: (clientId: string) =>
    http.post(`/clients/${clientId}/stop`).then(r => r.data),
  updateClientGpu: (clientId: string, gpuEnabled: boolean) =>
    http.patch(`/clients/${clientId}/gpu`, { gpu_enabled: gpuEnabled }).then(r => r.data),
  captureTemplateAsync: (projectId: string, clientId: string, name: string) =>
    http.post(`/projects/${projectId}/templates/capture_async`, { client_id: clientId, name }).then(r => r.data),
  recaptureTemplateAsync: (projectId: string, templateId: string, clientId: string, name: string) =>
    http.post(`/projects/${projectId}/templates/${templateId}/recapture_async`, { client_id: clientId, name }).then(r => r.data),
  addClientToProject: (projectId: string, clientId: string) =>
    http.post(`/projects/${projectId}/clients/${clientId}`).then(r => r.data),
  removeClientFromProject: (projectId: string, clientId: string) =>
    http.delete(`/projects/${projectId}/clients/${clientId}`).then(r => r.data),

  // Projects
  getProjects: () => http.get<Project[]>('/projects').then(r => r.data),
  createProject: (data: { name: string; description?: string }) =>
    http.post<Project>('/projects', data).then(r => r.data),
  updateProject: (id: string, data: Partial<Project>) =>
    http.put<Project>(`/projects/${id}`, data).then(r => r.data),
  deleteProject: (id: string) => http.delete(`/projects/${id}`).then(r => r.data),

  // Markers
  getMarkers: (projectId: string) =>
    http.get<Marker[]>(`/projects/${projectId}/markers`).then(r => r.data),
  createMarker: (projectId: string, data: { name: string; type: 'point' | 'box' }) =>
    http.post<Marker>(`/projects/${projectId}/markers`, data).then(r => r.data),
  deleteMarker: (projectId: string, markerId: string) =>
    http.delete(`/projects/${projectId}/markers/${markerId}`).then(r => r.data),
  getMarkerCaptures: (projectId: string, clientId: string) =>
    http.get<MarkerCapture[]>(`/projects/${projectId}/markers/captures`, { params: { client_id: clientId } }).then(r => r.data),
  getMarkerCaptureData: (projectId: string, clientId: string) =>
    http.get<MarkerCaptureData[]>(`/projects/${projectId}/markers/captures/data`, { params: { client_id: clientId } }).then(r => r.data),
  captureClientScreenshot: (clientId: string, projectId?: string) =>
    http.post<{ data: string }>(`/clients/${clientId}/screenshot`, null, { params: projectId ? { project_id: projectId } : undefined }).then(r => r.data.data),
  getWindowBinding: (projectId: string, clientId: string) =>
    http.get<WindowBinding>(`/projects/${projectId}/window-binding`, { params: { client_id: clientId } })
      .then(r => r.data)
      .catch((e: any) => e?.response?.status === 404 ? null : Promise.reject(e)) as Promise<WindowBinding | null>,

  sendMarkers: (projectId: string, clientId: string, markerNames?: string[]) =>
    http.post(`/projects/${projectId}/markers/send`, {
      client_id: clientId,
      ...(markerNames ? { marker_names: markerNames } : {}),
    }).then(r => r.data),
  restoreWindow: (projectId: string, clientId: string) =>
    http.post(`/projects/${projectId}/markers/restore-window`, { client_id: clientId }).then(r => r.data),
  resizeWindowInteractive: (projectId: string, clientId: string) =>
    http.post(`/projects/${projectId}/markers/resize-window-interactive`, { client_id: clientId }).then(r => r.data),
  getMarkerWindows: (projectId: string) =>
    http.get<MarkerWindow[]>(`/projects/${projectId}/marker-windows`).then(r => r.data),

  copyCapturesByWindow: (
    projectId: string,
    sourceWindowTitle: string,
    sourceWindowW: number,
    sourceWindowH: number,
    targetClientIds: string[],
    mode: 'overwrite' | 'fill_missing',
  ) =>
    http.post(`/projects/${projectId}/markers/copy-captures`, {
      source_window_title: sourceWindowTitle,
      source_window_w: sourceWindowW,
      source_window_h: sourceWindowH,
      target_client_ids: targetClientIds,
      mode,
      auto_scale: true,
    }).then(r => r.data),

  copyCapturesBetweenClients: (
    projectId: string,
    sourceClientId: string,
    targetClientIds: string[],
    mode: 'overwrite' | 'fill_missing',
    autoScale = true,
  ) =>
    http.post(`/projects/${projectId}/markers/copy-captures`, {
      source_client_id: sourceClientId,
      target_client_ids: targetClientIds,
      mode,
      auto_scale: autoScale,
    }).then(r => r.data),

  // Templates
  getTemplates: (projectId: string) =>
    http.get<Template[]>(`/projects/${projectId}/templates`).then(r => r.data),
  uploadTemplate: (projectId: string, name: string, file: File) => {
    const form = new FormData()
    form.append('name', name)
    form.append('file', file)
    return http.post<Template>(`/projects/${projectId}/templates`, form).then(r => r.data)
  },
  renameTemplate: (projectId: string, templateId: string, name: string) => {
    const form = new FormData()
    form.append('name', name)
    return http.patch<Template>(`/projects/${projectId}/templates/${templateId}`, form).then(r => r.data)
  },
  deleteTemplate: (projectId: string, templateId: string) =>
    http.delete(`/projects/${projectId}/templates/${templateId}`).then(r => r.data),
  updateTemplateImage: (projectId: string, templateId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.put<Template>(`/projects/${projectId}/templates/${templateId}/image`, form).then(r => r.data)
  },
  templateImageUrl: (projectId: string, templateId: string) =>
    `/api/projects/${projectId}/templates/${templateId}/image`,
  createTemplateFromCapture: (
    projectId: string,
    data: { name: string; image_b64: string; source_w: number | null; source_h: number | null },
  ) =>
    http.post<Template>(`/projects/${projectId}/templates/from_capture`, data).then(r => r.data),

  // Global Variables
  getGlobalVars: (projectId: string) =>
    http.get<GlobalVariable[]>(`/projects/${projectId}/global-vars`).then(r => r.data),
  upsertGlobalVar: (projectId: string, varName: string, value: any) =>
    http.put<GlobalVariable>(`/projects/${projectId}/global-vars/${encodeURIComponent(varName)}`, { value }).then(r => r.data),
  deleteGlobalVar: (projectId: string, varName: string) =>
    http.delete(`/projects/${projectId}/global-vars/${encodeURIComponent(varName)}`).then(r => r.data),

  // Syntax check
  syntaxCheck: (code: string) =>
    http.post<{ ok: boolean; line?: number; col?: number; msg?: string }>('/scripts/syntax-check', { code }).then(r => r.data),

  // Persistent logs
  getLogs: (params: {
    level?: string
    source?: string
    script_id?: string
    client_id?: string
    keyword?: string
    time_range?: string
    start_time?: string
    end_time?: string
    page?: number
    page_size?: number
  }) => http.get<LogQueryResult>('/logs/entries', { params }).then(r => r.data),
  clearPersistentLogs: () => http.delete('/logs/entries').then(r => r.data),

  // App settings
  getAppSettings: () => http.get<AppSettings>('/app-settings').then(r => r.data),
  updateAppSettings: (data: Partial<AppSettings>) =>
    http.put('/app-settings', data).then(r => r.data),

  // AI Models
  getModels: () => http.get<AIModel[]>('/models').then(r => r.data),
  createModel: (data: Omit<AIModel, 'id' | 'created_at' | 'updated_at'>) =>
    http.post<AIModel>('/models', data).then(r => r.data),
  updateModel: (id: string, data: Partial<Omit<AIModel, 'id' | 'type' | 'provider' | 'created_at' | 'updated_at'>>) =>
    http.put<AIModel>(`/models/${id}`, data).then(r => r.data),
  deleteModel: (id: string) => http.delete(`/models/${id}`).then(r => r.data),
  getLocalModelStatus: () =>
    http.get<{ paddleocr: OCRStatus }>('/models/local/status').then(r => r.data),
  initLocalModel: (variant: 'mobile' | 'server' = 'mobile') =>
    http.post('/models/local/init', { variant }).then(r => r.data),
  reinitLocalModel: (variant: 'mobile' | 'server' = 'mobile') =>
    http.post('/models/local/reinit', { variant }).then(r => r.data),
  testModelCredentials: (data: { api_key: string; base_url: string; model_name: string }) =>
    http.post<ModelTestResult>('/models/test', data).then(r => r.data),
  testSavedModel: (id: string) =>
    http.post<ModelTestResult>(`/models/${id}/test`).then(r => r.data),

  // Service API Keys
  getServiceKeys: () => http.get<ServiceApiKey[]>('/service-keys').then(r => r.data),
  createServiceKey: (data: { service_name: string; api_key?: string; base_url?: string }) =>
    http.post<ServiceApiKey>('/service-keys', data).then(r => r.data),
  updateServiceKey: (id: string, data: { service_name?: string; api_key?: string; base_url?: string }) =>
    http.put<ServiceApiKey>(`/service-keys/${id}`, data).then(r => r.data),
  deleteServiceKey: (id: string) => http.delete(`/service-keys/${id}`).then(r => r.data),
}

export interface ModelTestResult {
  success: boolean
  message: string
  latency_ms: number | null
}

export interface AppLogEntry {
  id: number
  timestamp: string
  level: string
  source: string
  logger_name: string | null
  message: string
  client_id: string | null
  script_id: string | null
  execution_id: string | null
  node_id: string | null
  node_label: string | null
  node_type: string | null
}

export interface LogQueryResult {
  total: number
  page: number
  page_size: number
  items: AppLogEntry[]
}

export interface AppSettings {
  log_retention_days: number
  log_auto_refresh_interval: number
}

export interface ServiceApiKey {
  id: string
  service_name: string
  api_key: string
  base_url: string
  created_at: string
  updated_at: string
}
