import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type Marker, type Project } from '@/services/api'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const markers = ref<Record<string, Marker[]>>({})
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

  async function sendMarkers(projectId: string, clientId: string) {
    return api.sendMarkers(projectId, clientId)
  }

  function getProjectName(id: string | null): string {
    if (!id) return ''
    return projects.value.find(p => p.id === id)?.name ?? ''
  }

  return {
    projects, markers, loading,
    fetchProjects, createProject, deleteProject,
    fetchMarkers, createMarker, deleteMarker, sendMarkers,
    getProjectName,
  }
})
