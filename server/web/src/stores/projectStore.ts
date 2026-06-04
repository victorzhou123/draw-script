import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type GlobalVariable, type Marker, type Project, type Template } from '@/services/api'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const markers = ref<Record<string, Marker[]>>({})
  const templates = ref<Record<string, Template[]>>({})
  const globalVars = ref<Record<string, GlobalVariable[]>>({})
  const loading = ref(false)

  async function fetchProjects() {
    loading.value = true
    try {
      projects.value = await api.getProjects()
    } finally {
      loading.value = false
    }
  }

  async function createProject(name: string, description = '') {
    const p = await api.createProject({ name, description })
    projects.value.unshift(p)
    return p
  }

  async function deleteProject(id: string) {
    await api.deleteProject(id)
    projects.value = projects.value.filter(p => p.id !== id)
    delete markers.value[id]
    delete templates.value[id]
  }

  async function fetchMarkers(projectId: string) {
    markers.value[projectId] = await api.getMarkers(projectId)
  }

  async function createMarker(projectId: string, name: string, type: 'point' | 'box') {
    const m = await api.createMarker(projectId, { name, type })
    if (!markers.value[projectId]) markers.value[projectId] = []
    markers.value[projectId].push(m)
    return m
  }

  async function deleteMarker(projectId: string, markerId: string) {
    await api.deleteMarker(projectId, markerId)
    if (markers.value[projectId]) {
      markers.value[projectId] = markers.value[projectId].filter(m => m.id !== markerId)
    }
  }

  async function sendMarkers(projectId: string, clientId: string, markerNames?: string[]) {
    return api.sendMarkers(projectId, clientId, markerNames)
  }

  async function fetchTemplates(projectId: string) {
    templates.value[projectId] = await api.getTemplates(projectId)
  }

  async function uploadTemplate(projectId: string, name: string, file: File) {
    const t = await api.uploadTemplate(projectId, name, file)
    if (!templates.value[projectId]) templates.value[projectId] = []
    templates.value[projectId].push(t)
    return t
  }

  async function deleteTemplate(projectId: string, templateId: string) {
    await api.deleteTemplate(projectId, templateId)
    if (templates.value[projectId]) {
      templates.value[projectId] = templates.value[projectId].filter(t => t.id !== templateId)
    }
  }

  async function fetchGlobalVars(projectId: string) {
    globalVars.value[projectId] = await api.getGlobalVars(projectId)
  }

  async function deleteGlobalVar(projectId: string, varName: string) {
    await api.deleteGlobalVar(projectId, varName)
    if (globalVars.value[projectId]) {
      globalVars.value[projectId] = globalVars.value[projectId].filter(v => v.name !== varName)
    }
  }

  function getProjectName(id: string | null): string {
    if (!id) return ''
    return projects.value.find(p => p.id === id)?.name ?? ''
  }

  return {
    projects, markers, templates, globalVars, loading,
    fetchProjects, createProject, deleteProject,
    fetchMarkers, createMarker, deleteMarker, sendMarkers,
    fetchTemplates, uploadTemplate, deleteTemplate,
    fetchGlobalVars, deleteGlobalVar,
    getProjectName,
  }
})
