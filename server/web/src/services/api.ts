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

export interface Webhook {
  id: string
  name: string
  url: string
  events: string
  secret: string
  enabled: boolean
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

export interface Template {
  id: string
  project_id: string
  name: string
  filename: string
  created_at: string
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

  // Webhooks
  getWebhooks: () => http.get<Webhook[]>('/webhooks').then(r => r.data),
  createWebhook: (data: Omit<Webhook, 'id'>) =>
    http.post<Webhook>('/webhooks', data).then(r => r.data),
  updateWebhook: (id: string, data: Partial<Webhook>) =>
    http.put<Webhook>(`/webhooks/${id}`, data).then(r => r.data),
  deleteWebhook: (id: string) => http.delete(`/webhooks/${id}`).then(r => r.data),

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
  sendMarkers: (projectId: string, clientId: string) =>
    http.post(`/projects/${projectId}/markers/send`, { client_id: clientId }).then(r => r.data),

  // Templates
  getTemplates: (projectId: string) =>
    http.get<Template[]>(`/projects/${projectId}/templates`).then(r => r.data),
  uploadTemplate: (projectId: string, name: string, file: File) => {
    const form = new FormData()
    form.append('name', name)
    form.append('file', file)
    return http.post<Template>(`/projects/${projectId}/templates`, form).then(r => r.data)
  },
  deleteTemplate: (projectId: string, templateId: string) =>
    http.delete(`/projects/${projectId}/templates/${templateId}`).then(r => r.data),
  templateImageUrl: (projectId: string, templateId: string) =>
    `/api/projects/${projectId}/templates/${templateId}/image`,
}
