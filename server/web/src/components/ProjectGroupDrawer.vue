<template>
  <a-drawer
    :open="open"
    title="项目组"
    placement="right"
    :width="600"
    :body-style="{ padding: 0, background: '#1a1a1a', display: 'flex', flexDirection: 'column', height: '100%' }"
    :header-style="{ background: '#1f1f1f', borderBottom: '1px solid #252525' }"
    @close="emit('close')"
  >
    <div class="pg-layout">

      <!-- ═══ 左栏：项目组列表 ══════════════════════ -->
      <div class="pg-left">
        <div class="pg-left-header">
          <span class="section-title">项目组</span>
          <a-button size="small" type="text" class="icon-btn" @click="showNewProject = true">
            <PlusOutlined />
          </a-button>
        </div>

        <div v-if="projectStore.projects.length === 0" class="empty-hint">暂无项目组</div>

        <div
          v-for="p in projectStore.projects" :key="p.id"
          class="project-item" :class="{ active: selectedId === p.id }"
          @click="selectProject(p.id)"
        >
          <div class="project-item-info">
            <span class="project-item-name">{{ p.name }}</span>
            <span class="project-item-stats">
              {{ (projectStore.markers[p.id] ?? []).length }}标 ·
              {{ clientCountFor(p.id) }}端 ·
              {{ scriptCountFor(p.id) }}脚本
            </span>
          </div>
          <div class="project-item-actions">
            <a-button type="text" size="small" class="icon-btn" @click.stop="startRename(p)">
              <EditOutlined />
            </a-button>
            <a-popconfirm title="确认删除此项目组？" @confirm="deleteProject(p.id)">
              <a-button type="text" size="small" class="icon-btn danger-btn" @click.stop>
                <DeleteOutlined />
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </div>

      <!-- ═══ 右栏：项目组详情 ═══════════════════════ -->
      <div class="pg-right">
        <div v-if="!selectedId" class="pg-placeholder">
          <FolderOpenOutlined class="pg-placeholder-icon" />
          <span>选择一个项目组查看详情</span>
        </div>

        <template v-else>
          <div class="pg-right-header">
            <span class="pg-right-title">{{ selectedProject?.name }}</span>
          </div>

          <a-tabs v-model:activeKey="detailTab" size="small" class="pg-tabs">

            <!-- ── 客户端 tab ── -->
            <a-tab-pane key="clients">
              <template #tab><LaptopOutlined /> 客户端 <span class="tab-count">{{ projectClientIds.length }}</span></template>
              <div class="tab-content">
                <div class="tab-toolbar">
                  <a-select
                    v-model:value="addClientId"
                    size="small" placeholder="添加客户端" style="flex:1"
                    :options="addableClients.map(c => ({ label: `${c.name} (${c.id})`, value: c.id }))"
                    show-search
                  />
                  <a-button size="small" type="primary" :disabled="!addClientId" @click="addClient">
                    <PlusOutlined /> 添加
                  </a-button>
                </div>
                <div v-if="projectClientIds.length === 0" class="empty-hint">暂无客户端，从上方添加</div>
                <div v-for="cid in projectClientIds" :key="cid" class="member-row">
                  <span class="status-dot" :class="`dot-${clientStatus(cid)}`" />
                  <div class="member-info">
                    <span class="member-name">{{ clientName(cid) }}</span>
                    <span class="member-meta">{{ cid }}</span>
                  </div>
                  <span class="member-status">{{ statusLabel(clientStatus(cid)) }}</span>
                  <a-popconfirm title="从此项目组移除？" @confirm="removeClient(cid)">
                    <a-button type="text" size="small" class="icon-btn danger-btn"><MinusOutlined /></a-button>
                  </a-popconfirm>
                </div>
              </div>
            </a-tab-pane>

            <!-- ── 标记 tab ── -->
            <a-tab-pane key="markers">
              <template #tab><TagsOutlined /> 标记 <span class="tab-count">{{ currentMarkers.length }}</span></template>
              <div class="tab-content">
                <div class="tab-toolbar">
                  <a-input v-model:value="newMarkerName" size="small" placeholder="标记名称" style="flex:1" @pressEnter="addMarker" />
                  <a-radio-group v-model:value="newMarkerType" size="small" button-style="solid">
                    <a-radio-button value="point"><AimOutlined /> 点</a-radio-button>
                    <a-radio-button value="box"><BorderOutlined /> 框</a-radio-button>
                  </a-radio-group>
                  <a-button size="small" type="primary" :disabled="!newMarkerName.trim()" @click="addMarker">
                    <PlusOutlined />
                  </a-button>
                </div>
                <!-- Marker list with checkboxes and capture status -->
                <div v-if="currentMarkers.length === 0" class="empty-hint">暂无标记，从上方添加</div>
                <div v-else>
                  <div class="marker-list-header">
                    <a-checkbox
                      :indeterminate="markerSelectIndeterminate"
                      :checked="markerSelectAllChecked"
                      @change="(e: any) => toggleAllMarkers(e.target.checked)"
                    >全选</a-checkbox>
                    <a-button
                      v-if="capturePreviewClientId"
                      type="text" size="small" class="select-missing-btn"
                      @click="selectUncaptured"
                    >选未标注</a-button>
                  </div>
                  <div v-for="m in currentMarkers" :key="m.id" class="member-row">
                    <a-checkbox
                      :checked="selectedMarkerNames.has(m.name)"
                      @change="() => toggleMarker(m.name)"
                      style="margin-right:4px"
                    />
                    <span class="marker-type-icon" :class="`icon-${m.type}`">
                      <AimOutlined v-if="m.type === 'point'" />
                      <BorderOutlined v-else />
                    </span>
                    <span class="member-name">{{ m.name }}</span>
                    <span class="marker-type-tag">{{ m.type === 'point' ? '点' : '框' }}</span>
                    <span
                      v-if="capturePreviewClientId"
                      class="capture-badge"
                      :class="markerCaptureMap[m.name] ? 'badge-ok' : 'badge-missing'"
                    >{{ markerCaptureMap[m.name] ? '已标注' : '未标注' }}</span>
                    <!-- Usage info popover -->
                    <a-popover trigger="click" placement="rightTop" overlay-class-name="marker-usage-popover">
                      <template #title>
                        <span style="font-size:12px;color:#aaa">引用此标注的节点</span>
                      </template>
                      <template #content>
                        <div style="min-width:180px;max-width:280px">
                          <div v-if="getMarkerUsages(m.name).length === 0" style="color:#555;font-size:12px;padding:2px 0">
                            未被任何脚本引用
                          </div>
                          <div
                            v-for="(u, i) in getMarkerUsages(m.name)" :key="i"
                            style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:12px"
                          >
                            <span style="color:#888;flex-shrink:0;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="u.scriptName">{{ u.scriptName }}</span>
                            <span style="color:#444">›</span>
                            <span style="color:#ccc;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="u.nodeLabel">{{ u.nodeLabel }}</span>
                            <span style="font-size:10px;color:#555;background:#222;padding:1px 5px;border-radius:3px;flex-shrink:0">{{ u.nodeType }}</span>
                          </div>
                        </div>
                      </template>
                      <a-button type="text" size="small" class="icon-btn usage-info-btn">
                        <InfoCircleOutlined />
                      </a-button>
                    </a-popover>
                    <a-popconfirm title="删除此标记？" @confirm="removeMarker(m.id)">
                      <a-button type="text" size="small" class="icon-btn danger-btn"><DeleteOutlined /></a-button>
                    </a-popconfirm>
                  </div>
                </div>

                <!-- 发送标注 -->
                <div class="send-divider" />
                <div class="send-header">
                  <span class="subsection-title"><SendOutlined /> 发送标注</span>
                  <a-checkbox
                    :indeterminate="sendIndeterminate"
                    :checked="sendAllChecked"
                    @change="toggleSelectAll"
                  >全选</a-checkbox>
                </div>
                <!-- Preview capture status for a specific client -->
                <div class="preview-client-row">
                  <span class="preview-label">预览状态</span>
                  <a-select
                    v-model:value="capturePreviewClientId"
                    size="small"
                    placeholder="选择客户端查看标注状态"
                    style="flex:1"
                    allow-clear
                    :options="projectClientIds.map(cid => ({ label: clientName(cid), value: cid }))"
                  />
                  <a-button
                    size="small" class="icon-btn"
                    :disabled="!capturePreviewClientId"
                    :loading="refreshingCaptures"
                    @click="refreshCaptureStatus"
                    title="刷新标注状态"
                  ><ReloadOutlined /></a-button>
                </div>
                <div v-if="projectClientIds.length === 0" class="empty-hint">暂无客户端</div>
                <div v-for="cid in projectClientIds" :key="cid" class="send-client-row">
                  <a-checkbox
                    :checked="sendClientIds.includes(cid)"
                    @change="() => toggleSendClient(cid)"
                  >
                    <span class="status-dot" :class="`dot-${clientStatus(cid)}`" style="display:inline-block;margin-right:5px;" />
                    <span>{{ clientName(cid) }}</span>
                    <span class="member-status" style="margin-left:6px;">{{ statusLabel(clientStatus(cid)) }}</span>
                  </a-checkbox>
                </div>
                <a-button
                  type="primary" size="small" block style="margin-top:8px"
                  :loading="sending"
                  :disabled="sendClientIds.length === 0 || selectedMarkerNames.size === 0"
                  @click="sendMarkersToClients"
                >
                  <SendOutlined /> 发送选中 {{ selectedMarkerNames.size }} 个标记到 {{ sendClientIds.length }} 个客户端
                </a-button>
                <div v-if="sendResult" class="send-result" :class="sendResult.ok ? 'ok' : 'err'">{{ sendResult.text }}</div>
              </div>
            </a-tab-pane>

            <!-- ── 脚本 tab ── -->
            <a-tab-pane key="scripts">
              <template #tab><FileTextOutlined /> 脚本 <span class="tab-count">{{ projectScripts.length }}</span></template>
              <div class="tab-content">
                <div class="tab-toolbar">
                  <a-select
                    v-model:value="addScriptId"
                    size="small" placeholder="关联脚本" style="flex:1"
                    :options="addableScripts.map(s => ({ label: s.name, value: s.id }))"
                    show-search
                  />
                  <a-button size="small" type="primary" :disabled="!addScriptId" @click="addScript">
                    <PlusOutlined /> 关联
                  </a-button>
                </div>
                <div v-if="projectScripts.length === 0" class="empty-hint">暂无脚本，从上方关联</div>
                <div v-for="s in projectScripts" :key="s.id" class="member-row">
                  <FileTextOutlined class="member-script-icon" />
                  <span class="member-name">{{ s.name }}</span>
                  <a-popconfirm title="从此项目组移除脚本？" @confirm="removeScript(s.id)">
                    <a-button type="text" size="small" class="icon-btn danger-btn"><MinusOutlined /></a-button>
                  </a-popconfirm>
                </div>
              </div>
            </a-tab-pane>

            <!-- ── 模板 tab ── -->
            <a-tab-pane key="templates">
              <template #tab><PictureOutlined /> 模板 <span class="tab-count">{{ currentTemplates.length }}</span></template>
              <div class="tab-content">
                <div class="tab-toolbar">
                  <a-input v-model:value="newTemplateName" size="small" placeholder="模板名称" style="flex:1" />
                  <a-upload
                    :show-upload-list="false"
                    accept="image/*"
                    :before-upload="(f: File) => { handleTemplateUpload(f); return false }"
                  >
                    <a-button size="small" type="primary" :loading="uploadingTemplate" :disabled="!newTemplateName.trim()">
                      <UploadOutlined /> 上传
                    </a-button>
                  </a-upload>
                </div>
                <div v-if="currentTemplates.length === 0" class="empty-hint">暂无模板，输入名称后上传图片</div>
                <div v-for="t in currentTemplates" :key="t.id" class="template-row">
                  <img :src="templateImageUrl(t.id)" class="template-thumb" />
                  <span class="member-name">{{ t.name }}</span>
                  <a-popconfirm title="删除此模板？" @confirm="removeTemplate(t.id)">
                    <a-button type="text" size="small" class="icon-btn danger-btn"><DeleteOutlined /></a-button>
                  </a-popconfirm>
                </div>
              </div>
            </a-tab-pane>

          </a-tabs>
        </template>
      </div>
    </div>

    <!-- 新建项目组 Modal -->
    <a-modal v-model:open="showNewProject" title="新建项目组" @ok="createProject" :ok-button-props="{ loading: creating }">
      <a-form layout="vertical" size="small" style="margin-top:8px">
        <a-form-item label="项目组名称">
          <a-input v-model:value="newProjectName" placeholder="例如：电商自动化" @pressEnter="createProject" />
        </a-form-item>
        <a-form-item label="描述（可选）">
          <a-input v-model:value="newProjectDesc" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 重命名 Modal -->
    <a-modal v-model:open="showRename" title="重命名项目组" @ok="confirmRename" :ok-button-props="{ loading: renaming }">
      <a-form layout="vertical" size="small" style="margin-top:8px">
        <a-form-item label="新名称">
          <a-input v-model:value="renameValue" @pressEnter="confirmRename" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, MinusOutlined,
  LaptopOutlined, TagsOutlined, FileTextOutlined, PictureOutlined, UploadOutlined,
  AimOutlined, BorderOutlined, FolderOpenOutlined, SendOutlined, ReloadOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import { useClientStore } from '@/stores/clientStore'
import { useScriptStore } from '@/stores/scriptStore'
import { api } from '@/services/api'
import type { Project, MarkerCapture } from '@/services/api'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const projectStore = useProjectStore()
const clientStore = useClientStore()
const scriptStore = useScriptStore()

const selectedId = ref<string | null>(null)
const detailTab = ref('clients')

// New project
const showNewProject = ref(false)
const newProjectName = ref('')
const newProjectDesc = ref('')
const creating = ref(false)

// Rename
const showRename = ref(false)
const renameTarget = ref<Project | null>(null)
const renameValue = ref('')
const renaming = ref(false)

// Clients tab
const addClientId = ref<string | null>(null)
const projectClientIds = ref<string[]>([])

// Markers tab
const newMarkerName = ref('')
const newMarkerType = ref<'point' | 'box'>('point')
const sendClientIds = ref<string[]>([])
const sending = ref(false)
const sendResult = ref<{ ok: boolean; text: string } | null>(null)
// Marker capture status preview
const capturePreviewClientId = ref<string | null>(null)
const markerCaptureMap = ref<Record<string, boolean>>({})  // name → captured
const selectedMarkerNames = ref<Set<string>>(new Set())
const refreshingCaptures = ref(false)

// Scripts tab
const addScriptId = ref<string | null>(null)

// Templates tab
const newTemplateName = ref('')
const uploadingTemplate = ref(false)

// ── Computed ──────────────────────────────────────────────────────────

const selectedProject = computed(() => projectStore.projects.find(p => p.id === selectedId.value))
const currentMarkers = computed(() => selectedId.value ? (projectStore.markers[selectedId.value] ?? []) : [])
const sendAllChecked = computed(() => projectClientIds.value.length > 0 && sendClientIds.value.length === projectClientIds.value.length)
const sendIndeterminate = computed(() => sendClientIds.value.length > 0 && sendClientIds.value.length < projectClientIds.value.length)
const markerSelectAllChecked = computed(() =>
  currentMarkers.value.length > 0 && currentMarkers.value.every(m => selectedMarkerNames.value.has(m.name))
)
const markerSelectIndeterminate = computed(() =>
  selectedMarkerNames.value.size > 0 && !markerSelectAllChecked.value
)
const projectScripts = computed(() => selectedId.value ? scriptStore.scripts.filter(s => s.project_id === selectedId.value) : [])

const addableClients = computed(() => clientStore.clients.filter(c => !projectClientIds.value.includes(c.id)))
const addableScripts = computed(() => scriptStore.scripts.filter(s => !s.project_id || s.project_id !== selectedId.value))
const currentTemplates = computed(() => selectedId.value ? (projectStore.templates[selectedId.value] ?? []) : [])

function templateImageUrl(templateId: string) {
  return api.templateImageUrl(selectedId.value!, templateId)
}

function clientCountFor(pid: string) { return clientStore.clients.filter(c => c.project_ids.includes(pid)).length }
function scriptCountFor(pid: string) { return scriptStore.scripts.filter(s => s.project_id === pid).length }
function clientName(cid: string) { return clientStore.clients.find(c => c.id === cid)?.name ?? cid }
function clientStatus(cid: string) {
  if (!clientStore.connectedIds.has(cid)) return 'disconnected'
  return clientStore.clients.find(c => c.id === cid)?.status ?? 'idle'
}
function statusLabel(s: string) { return { idle: '空闲', running: '运行中', disconnected: '离线', timeout: '超时' }[s] ?? s }

// ── Actions ───────────────────────────────────────────────────────────

async function fetchCaptureStatus(projectId: string, clientId: string) {
  const captures = await api.getMarkerCaptures(projectId, clientId)
  markerCaptureMap.value = Object.fromEntries(captures.map(c => [c.name, c.captured]))
  // Default: select uncaptured markers
  selectedMarkerNames.value = new Set(
    captures.filter(c => !c.captured).map(c => c.name)
  )
}

async function refreshCaptureStatus() {
  if (!capturePreviewClientId.value || !selectedId.value) return
  refreshingCaptures.value = true
  try {
    await fetchCaptureStatus(selectedId.value, capturePreviewClientId.value)
  } finally {
    refreshingCaptures.value = false
  }
}

async function selectProject(id: string) {
  selectedId.value = id
  detailTab.value = 'clients'
  addClientId.value = null
  addScriptId.value = null
  sendClientIds.value = []
  sendResult.value = null
  capturePreviewClientId.value = null
  markerCaptureMap.value = {}
  selectedMarkerNames.value = new Set(currentMarkers.value.map(m => m.name))
  // Fetch members
  await Promise.all([
    projectStore.fetchMarkers(id),
    projectStore.fetchTemplates(id),
  ])
  const result = await fetch(`/api/projects/${id}/clients`).then(r => r.json())
  projectClientIds.value = result
}

async function createProject() {
  if (!newProjectName.value.trim()) return
  creating.value = true
  try {
    const p = await projectStore.createProject(newProjectName.value.trim(), newProjectDesc.value.trim())
    showNewProject.value = false
    newProjectName.value = ''
    newProjectDesc.value = ''
    await selectProject(p.id)
    message.success('项目组已创建')
  } finally { creating.value = false }
}

async function deleteProject(id: string) {
  await projectStore.deleteProject(id)
  if (selectedId.value === id) selectedId.value = null
  message.success('项目组已删除')
}

function startRename(p: Project) {
  renameTarget.value = p
  renameValue.value = p.name
  showRename.value = true
}

async function confirmRename() {
  if (!renameTarget.value || !renameValue.value.trim()) return
  renaming.value = true
  try {
    await api.updateProject(renameTarget.value.id, { name: renameValue.value.trim() })
    await projectStore.fetchProjects()
    showRename.value = false
    message.success('重命名成功')
  } finally { renaming.value = false }
}

async function addClient() {
  if (!addClientId.value || !selectedId.value) return
  await clientStore.addToProject(addClientId.value, selectedId.value)
  projectClientIds.value.push(addClientId.value)
  addClientId.value = null
}

async function removeClient(cid: string) {
  if (!selectedId.value) return
  await clientStore.removeFromProject(cid, selectedId.value)
  projectClientIds.value = projectClientIds.value.filter(id => id !== cid)
}

async function addMarker() {
  if (!newMarkerName.value.trim() || !selectedId.value) return
  await projectStore.createMarker(selectedId.value, newMarkerName.value.trim(), newMarkerType.value)
  newMarkerName.value = ''
}

async function removeMarker(markerId: string) {
  if (!selectedId.value) return
  await projectStore.deleteMarker(selectedId.value, markerId)
}

function toggleSelectAll(e: Event) {
  sendClientIds.value = (e.target as HTMLInputElement).checked ? [...projectClientIds.value] : []
}

function toggleSendClient(cid: string) {
  const idx = sendClientIds.value.indexOf(cid)
  if (idx >= 0) sendClientIds.value.splice(idx, 1)
  else sendClientIds.value.push(cid)
}

const NODE_TYPE_LABEL: Record<string, string> = {
  action: '操作', vision: '视觉', condition: '条件', screenshot: '截图',
  http: 'HTTP', compute: '计算', delay: '延时', loop: '循环',
  wait: '等待', script: '子脚本', webhook: 'Webhook',
}

interface MarkerUsage { scriptName: string; nodeLabel: string; nodeType: string }

function getMarkerUsages(markerName: string): MarkerUsage[] {
  const usages: MarkerUsage[] = []
  const scripts = scriptStore.scripts.filter(s => s.project_id === selectedId.value)
  for (const script of scripts) {
    try {
      const flow = JSON.parse(script.flow_json || '{}')
      for (const node of (flow.nodes ?? [])) {
        const data = node.data ?? {}
        const dataStr = JSON.stringify(data)
        const referencedByTemplate = dataStr.includes(`markers.${markerName}.`)
        const referencedByRangeMarker = data.range_marker === markerName
        if (referencedByTemplate || referencedByRangeMarker) {
          const rawType = (node.shape as string || '').replace('node-', '')
          usages.push({
            scriptName: script.name,
            nodeLabel: data.label || rawType || node.id,
            nodeType: NODE_TYPE_LABEL[rawType] || rawType,
          })
        }
      }
    } catch { /* skip malformed flow_json */ }
  }
  return usages
}

function toggleMarker(name: string) {
  const s = selectedMarkerNames.value
  if (s.has(name)) s.delete(name)
  else s.add(name)
  selectedMarkerNames.value = new Set(s)
}

function toggleAllMarkers(checked: boolean) {
  selectedMarkerNames.value = checked
    ? new Set(currentMarkers.value.map(m => m.name))
    : new Set()
}

function selectUncaptured() {
  selectedMarkerNames.value = new Set(
    currentMarkers.value.filter(m => !markerCaptureMap.value[m.name]).map(m => m.name)
  )
}

async function sendMarkersToClients() {
  if (!selectedId.value || sendClientIds.value.length === 0) return
  sending.value = true
  sendResult.value = null
  const names = selectedMarkerNames.value.size > 0
    ? [...selectedMarkerNames.value]
    : undefined
  try {
    await Promise.all(sendClientIds.value.map(cid => projectStore.sendMarkers(selectedId.value!, cid, names)))
    const markerCount = names?.length ?? currentMarkers.value.length
    sendResult.value = { ok: true, text: `已发送 ${markerCount} 个标记到 ${sendClientIds.value.length} 个客户端` }
  } catch (e: any) {
    sendResult.value = { ok: false, text: e?.response?.data?.detail ?? '发送失败' }
  } finally {
    sending.value = false
  }
}

async function addScript() {
  if (!addScriptId.value || !selectedId.value) return
  await api.updateScript(addScriptId.value, { project_id: selectedId.value })
  await scriptStore.fetchScripts()
  addScriptId.value = null
}

async function removeScript(scriptId: string) {
  await api.updateScript(scriptId, { project_id: null })
  await scriptStore.fetchScripts()
}

async function handleTemplateUpload(file: File) {
  if (!selectedId.value || !newTemplateName.value.trim()) return
  uploadingTemplate.value = true
  try {
    await projectStore.uploadTemplate(selectedId.value, newTemplateName.value.trim(), file)
    newTemplateName.value = ''
    message.success('模板已上传')
  } catch {
    message.error('上传失败')
  } finally {
    uploadingTemplate.value = false
  }
}

async function removeTemplate(templateId: string) {
  if (!selectedId.value) return
  await projectStore.deleteTemplate(selectedId.value, templateId)
  message.success('模板已删除')
}

watch(() => props.open, async (v) => {
  if (v) {
    await Promise.all([
      projectStore.fetchProjects(),
      clientStore.fetchClients(),
      scriptStore.fetchScripts(),
    ])
  }
})

watch(capturePreviewClientId, async (cid) => {
  if (cid && selectedId.value) {
    await fetchCaptureStatus(selectedId.value, cid)
  } else {
    markerCaptureMap.value = {}
    selectedMarkerNames.value = new Set(currentMarkers.value.map(m => m.name))
  }
})

watch(currentMarkers, (markers) => {
  // When markers change (e.g. new marker added), ensure all are selected by default
  if (!capturePreviewClientId.value) {
    selectedMarkerNames.value = new Set(markers.map(m => m.name))
  }
}, { deep: true })
</script>

<style scoped>
.pg-layout { display: flex; height: 100%; overflow: hidden; }

/* Left panel */
.pg-left { width: 200px; flex-shrink: 0; border-right: 1px solid #222; display: flex; flex-direction: column; background: #161616; }
.pg-left-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 12px 8px; border-bottom: 1px solid #222; }
.section-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 1px; }
.icon-btn { color: #444 !important; padding: 0 4px !important; height: 22px !important; }
.icon-btn:hover { color: #888 !important; }
.danger-btn:hover { color: #ff4d4f !important; }
.empty-hint { font-size: 12px; color: #333; padding: 12px; }
.project-item { display: flex; align-items: center; padding: 8px 12px; cursor: pointer; transition: background 0.12s; border-left: 2px solid transparent; }
.project-item:hover { background: #1e1e1e; }
.project-item.active { background: #111d2c; border-left-color: #1890ff; }
.project-item-info { flex: 1; min-width: 0; }
.project-item-name { font-size: 13px; color: #ccc; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.project-item-stats { font-size: 10px; color: #444; }
.project-item-actions { display: flex; gap: 2px; opacity: 0; transition: opacity 0.15s; }
.project-item:hover .project-item-actions { opacity: 1; }

/* Right panel */
.pg-right { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.pg-placeholder { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #333; }
.pg-placeholder-icon { font-size: 40px; }
.pg-right-header { padding: 12px 16px 0; border-bottom: 1px solid #222; }
.pg-right-title { font-size: 14px; font-weight: 600; color: #d0d0d0; display: block; padding-bottom: 10px; }

/* Tabs */
.pg-tabs { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.pg-tabs :deep(.ant-tabs-nav) { padding: 0 16px; margin: 0; }
.pg-tabs :deep(.ant-tabs-content-holder) { flex: 1; overflow: hidden; }
.pg-tabs :deep(.ant-tabs-content) { height: 100%; }
.pg-tabs :deep(.ant-tabs-tabpane) { height: 100%; overflow-y: auto; }
.tab-count { display: inline-flex; align-items: center; justify-content: center; min-width: 16px; height: 16px; background: #252525; color: #555; font-size: 10px; border-radius: 8px; padding: 0 4px; margin-left: 4px; }
.tab-content { padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }
.tab-toolbar { display: flex; align-items: center; gap: 6px; }

/* Members */
.member-row { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 5px; background: #1f1f1f; border: 1px solid #252525; }
.member-row:hover .danger-btn { opacity: 1 !important; }
.member-row .danger-btn { opacity: 0; transition: opacity 0.15s; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dot-idle { background: #52c41a; }
.dot-running { background: #1890ff; }
.dot-disconnected { background: #333; }
.dot-timeout { background: #faad14; }
.member-info { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.member-name { font-size: 13px; color: #ccc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.member-meta { font-size: 10px; color: #444; }
.member-status { font-size: 11px; color: #555; flex-shrink: 0; }
.member-script-icon { color: #444; font-size: 13px; }
.marker-type-icon { font-size: 14px; width: 18px; display: flex; justify-content: center; }
.icon-point .anticon { color: #1890ff; }
.icon-box   .anticon { color: #faad14; }
.marker-type-tag { font-size: 10px; color: #444; background: #2a2a2a; padding: 1px 6px; border-radius: 3px; flex-shrink: 0; }

/* Templates */
.template-row { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 5px; background: #1f1f1f; border: 1px solid #252525; }
.template-row:hover .danger-btn { opacity: 1 !important; }
.template-row .danger-btn { opacity: 0; transition: opacity 0.15s; }
.template-thumb { width: 40px; height: 40px; object-fit: cover; border-radius: 3px; border: 1px solid #303030; flex-shrink: 0; }

/* Marker list */
.marker-list-header { display: flex; align-items: center; justify-content: space-between; padding: 4px 2px 6px; }
.select-missing-btn { font-size: 11px; color: #888 !important; padding: 0 6px !important; height: 20px !important; }
.capture-badge { font-size: 10px; padding: 1px 6px; border-radius: 3px; flex-shrink: 0; }
.badge-ok { color: #52c41a; background: #162312; border: 1px solid #52c41a44; }
.badge-missing { color: #888; background: #222; border: 1px solid #333; }
.usage-info-btn { color: #444 !important; padding: 0 3px !important; height: 20px !important; flex-shrink: 0; }
.usage-info-btn:hover { color: #888 !important; }

/* Send annotation */
.send-divider { height: 1px; background: #252525; margin: 10px 0; }
.send-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.subsection-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; gap: 5px; }
.preview-client-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.preview-label { font-size: 11px; color: #555; flex-shrink: 0; }
.send-client-row { padding: 4px 0; }
.send-result { margin-top: 8px; font-size: 12px; padding: 5px 10px; border-radius: 4px; }
.send-result.ok  { color: #52c41a; background: #162312; border: 1px solid #52c41a33; }
.send-result.err { color: #ff4d4f; background: #2a1215; border: 1px solid #ff4d4f33; }
</style>

<style>
.marker-usage-popover .ant-popover-inner { background: #1e1e1e; border: 1px solid #2a2a2a; }
.marker-usage-popover .ant-popover-title { border-bottom: 1px solid #2a2a2a; padding: 6px 12px; }
.marker-usage-popover .ant-popover-inner-content { padding: 8px 12px; }
.marker-usage-popover .ant-popover-arrow::before { background: #1e1e1e; }
</style>
