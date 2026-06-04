import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

export interface Script {
  id: string
  name: string
  description: string
  flow_json: string
  project_id: string | null
  created_at: string
  updated_at: string
}

export interface Client {
  id: string
  name: string
  platform: string
  last_seen: string
  status: string
  project_ids: string[]
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
  created_at: string
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

  // Clients
  getClients: () => http.get<Client[]>('/clients').then(r => r.data),
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
  captureClientScreenshot: (clientId: string) =>
    http.post<{ data: string }>(`/clients/${clientId}/screenshot`).then(r => r.data.data),
  sendMarkers: (projectId: string, clientId: string, markerNames?: string[]) =>
    http.post(`/projects/${projectId}/markers/send`, {
      client_id: clientId,
      ...(markerNames ? { marker_names: markerNames } : {}),
    }).then(r => r.data),
  restoreWindow: (projectId: string, clientId: string) =>
    http.post(`/projects/${projectId}/markers/restore-window`, { client_id: clientId }).then(r => r.data),

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
  templateImageUrl: (projectId: string, templateId: string) =>
    `/api/projects/${projectId}/templates/${templateId}/image`,

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
}

export interface ModelTestResult {
  success: boolean
  message: string
  latency_ms: number | null
}
