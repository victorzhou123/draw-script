<template>
  <div class="script-sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">脚本列表</span>
      <a-button type="primary" size="small" @click="onNew">+ 新建</a-button>
    </div>
    <a-spin :spinning="scriptStore.loading">
      <div
        v-for="script in scriptStore.scripts"
        :key="script.id"
        class="script-item"
        :class="{ active: scriptStore.currentScript?.id === script.id }"
        @click="onSelect(script.id)"
      >
        <div class="script-name">{{ script.name }}</div>
        <div class="script-meta">{{ formatDate(script.updated_at) }}</div>

        <!-- top-right: delete -->
        <a-button
          type="text" size="small" danger
          class="delete-btn"
          @click.stop="onDelete(script.id)"
        >✕</a-button>

        <!-- bottom-right: three-dot menu -->
        <div class="more-wrap" @click.stop>
          <a-dropdown :trigger="['click']" placement="bottomRight">
            <a-button type="text" size="small" class="more-btn">⋮</a-button>
            <template #overlay>
              <a-menu>
                <a-menu-item key="info" @click="openInfo(script)">
                  <InfoCircleOutlined /> 信息
                </a-menu-item>
                <a-menu-item key="duplicate" @click="onDuplicate(script.id)">
                  <CopyOutlined /> 复制成新脚本
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </div>
    </a-spin>

    <!-- Info Modal -->
    <a-modal
      v-model:open="infoModalOpen"
      title="脚本信息"
      :footer="null"
      width="640px"
      :body-style="{ padding: '20px 24px' }"
    >
      <a-spin :spinning="infoLoading">
        <div v-if="infoScript" class="info-grid">
          <!-- Script ID -->
          <div class="info-label">脚本 ID</div>
          <div class="info-value id-row">
            <span class="id-text">{{ infoScript.id }}</span>
            <a-tooltip :title="idCopied ? '已复制' : '复制 ID'">
              <a-button type="text" size="small" class="copy-btn" @click="copyId">
                <CheckOutlined v-if="idCopied" style="color:#52c41a" />
                <CopyOutlined v-else />
              </a-button>
            </a-tooltip>
          </div>

          <!-- Project group -->
          <div class="info-label">所在项目组</div>
          <div class="info-value">
            <span v-if="infoProject" class="tag-project">{{ infoProject.name }}</span>
            <span v-else class="no-data">未分配</span>
          </div>

          <!-- Clients -->
          <div class="info-label">组内客户端</div>
          <div class="info-value">
            <template v-if="infoClients.length">
              <div v-for="c in infoClients" :key="c.id" class="client-row">
                <span
                  class="status-dot"
                  :class="c.status === 'disconnected' ? 'offline' : 'online'"
                />
                <span class="client-name">{{ c.name }}</span>
                <span class="client-platform">{{ c.platform }}</span>
              </div>
            </template>
            <span v-else class="no-data">—</span>
          </div>

          <!-- Markers -->
          <div class="info-label">涉及标记</div>
          <div class="info-value markers-row">
            <template v-if="infoMarkers.length">
              <span v-for="m in infoMarkers" :key="m" class="tag-marker">{{ m }}</span>
            </template>
            <span v-else class="no-data">—</span>
          </div>

          <!-- Curl -->
          <div class="info-label curl-label">调用方式</div>
          <div class="info-value curl-block-wrap">
            <pre class="curl-block">{{ curlCommand }}</pre>
            <a-tooltip :title="curlCopied ? '已复制' : '复制'">
              <a-button type="text" size="small" class="curl-copy-btn" @click="copyCurl">
                <CheckOutlined v-if="curlCopied" style="color:#52c41a" />
                <CopyOutlined v-else />
              </a-button>
            </a-tooltip>
          </div>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { InfoCircleOutlined, CopyOutlined, CheckOutlined } from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { useScriptStore } from '@/stores/scriptStore'
import { useProjectStore } from '@/stores/projectStore'
import { useClientStore } from '@/stores/clientStore'
import type { Script } from '@/services/api'

function getStartFields(script: Script): { name: string; default: string }[] {
  try {
    const flow = JSON.parse(script.flow_json || '{}')
    const startCell = (flow.cells ?? []).find((c: any) => c.shape === 'node-start')
    return startCell?.data?.fields ?? []
  } catch {
    return []
  }
}

function collectMarkers(script: Script, allScripts: Script[], names: Set<string>, visited: Set<string>): void {
  if (visited.has(script.id)) return
  visited.add(script.id)
  try {
    const flow = JSON.parse(script.flow_json || '{}')
    for (const cell of (flow.cells ?? [])) {
      const data = cell.data ?? {}
      if (data.range_marker && typeof data.range_marker === 'string') {
        names.add(data.range_marker)
      }
      for (const val of Object.values(data.params ?? {})) {
        if (typeof val === 'string') {
          for (const m of val.matchAll(/\{\{markers\.([^.}]+)/g)) names.add(m[1])
          const dm = val.match(/^\$markers\.([^.]+)/)
          if (dm) names.add(dm[1])
        }
      }
      const nodeType = data.type || data.node_type || cell.shape
      if (nodeType === 'script' && data.script_id) {
        const sub = allScripts.find(s => s.id === data.script_id)
        if (sub) collectMarkers(sub, allScripts, names, visited)
      }
    }
  } catch { }
}

function getScriptMarkers(script: Script, allScripts: Script[]): string[] {
  const names = new Set<string>()
  collectMarkers(script, allScripts, names, new Set())
  return Array.from(names).sort()
}

const emit = defineEmits<{
  (e: 'scriptSelected', id: string): void
}>()

const scriptStore  = useScriptStore()
const projectStore = useProjectStore()
const clientStore  = useClientStore()

// ── list ──────────────────────────────────────────────────────────────────────

import { onMounted } from 'vue'
onMounted(() => scriptStore.fetchScripts())

async function onNew() {
  const name = prompt('脚本名称:')
  if (!name?.trim()) return
  await scriptStore.createScript(name.trim())
  emit('scriptSelected', scriptStore.currentScript!.id)
}

async function onSelect(id: string) {
  await scriptStore.selectScript(id)
  emit('scriptSelected', id)
}

async function onDelete(id: string) {
  Modal.confirm({
    title: '确认删除',
    content: '删除后无法恢复，确认吗？',
    okType: 'danger',
    async onOk() {
      await scriptStore.deleteScript(id)
      message.success('已删除')
    },
  })
}

async function onDuplicate(id: string) {
  await scriptStore.duplicateScript(id)
  message.success('已复制为新脚本')
}

function formatDate(d: string) {
  return new Date(d).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ── info modal ────────────────────────────────────────────────────────────────

const infoModalOpen = ref(false)
const infoLoading   = ref(false)
const infoScript    = ref<Script | null>(null)
const idCopied      = ref(false)

const infoProject = computed(() => {
  if (!infoScript.value?.project_id) return null
  return projectStore.projects.find(p => p.id === infoScript.value!.project_id) ?? null
})

const infoClients = computed(() => {
  if (!infoScript.value?.project_id) return []
  return clientStore.clients.filter(c => c.project_ids.includes(infoScript.value!.project_id!))
})

const infoMarkers = computed(() =>
  infoScript.value ? getScriptMarkers(infoScript.value, scriptStore.scripts) : []
)

const curlCommand = computed(() => {
  if (!infoScript.value) return ''
  const base = `${window.location.protocol}//${window.location.host}`
  const url = `${base}/api/scripts/${infoScript.value.id}/run`
  const fields = getStartFields(infoScript.value)
  const params: Record<string, string> = {}
  for (const f of fields) {
    if (f.name) params[f.name] = f.default ?? ''
  }
  const body: Record<string, any> = {
    client_id: '<client_id>',
    wait: true,
  }
  if (Object.keys(params).length > 0) body.params = params
  const bodyStr = JSON.stringify(body, null, 2)
    .split('\n')
    .map((line, i) => i === 0 ? line : '      ' + line)
    .join('\n')
  return `curl -X POST ${url} \\\n    -H "Content-Type: application/json" \\\n    -d '${bodyStr}'`
})

async function openInfo(script: Script) {
  infoScript.value = script
  idCopied.value = false
  infoModalOpen.value = true
  infoLoading.value = true
  await Promise.all([
    projectStore.projects.length === 0 ? projectStore.fetchProjects() : Promise.resolve(),
    clientStore.clients.length === 0   ? clientStore.fetchClients()   : Promise.resolve(),
  ])
  infoLoading.value = false
}

function copyId() {
  if (!infoScript.value) return
  navigator.clipboard.writeText(infoScript.value.id)
  idCopied.value = true
  setTimeout(() => { idCopied.value = false }, 2000)
}

const curlCopied = ref(false)
async function copyCurl() {
  const text = curlCommand.value
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  curlCopied.value = true
  message.success('已复制')
  setTimeout(() => { curlCopied.value = false }, 2000)
}
</script>

<style scoped>
.script-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 8px;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding: 4px 0;
}
.sidebar-title { font-weight: 600; font-size: 14px; color: #d0d0d0; }

/* card */
.script-item {
  position: relative;
  padding: 10px 12px 10px 12px;
  margin-bottom: 10px;
  border-radius: 8px;
  border: 1px solid #303030;
  background: #262626;
  cursor: pointer;
  transition: all 0.15s;
}
.script-item:hover { border-color: #1890ff; background: #111d2c; }
.script-item.active { border-color: #1890ff; background: #111d2c; font-weight: 600; }
.script-name { font-size: 13px; color: #d0d0d0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 20px; }
.script-meta { font-size: 11px; color: #555; margin-top: 2px; }

/* delete btn – top right */
.delete-btn {
  position: absolute; right: 4px; top: 4px;
  width: 22px; padding: 0 !important;
  opacity: 0; transition: opacity 0.15s;
  color: #666 !important;
}
.script-item:hover .delete-btn { opacity: 1; }

/* more-wrap: positioned container so dropdown doesn't affect alignment */
.more-wrap {
  position: absolute; right: 4px; bottom: 3px;
  width: 22px;
  opacity: 0; transition: opacity 0.15s;
}
.script-item:hover .more-wrap { opacity: 1; }

/* three-dot btn */
.more-btn {
  width: 22px; padding: 0 !important;
  color: #666 !important; font-size: 14px; line-height: 1;
}

/* info modal */
.info-grid {
  display: grid;
  grid-template-columns: 80px 1fr;
  row-gap: 14px;
  align-items: start;
}
.info-label {
  font-size: 12px; color: #666;
  padding-top: 2px;
}
.info-value { font-size: 13px; color: #d0d0d0; min-width: 0; }

.id-row { display: flex; align-items: center; gap: 6px; }
.id-text {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px; color: #7ec8e3;
  background: #1e1e1e; border: 1px solid #2a2a2a;
  border-radius: 4px; padding: 2px 6px;
  word-break: break-all; flex: 1;
}
.copy-btn { flex-shrink: 0; color: #555 !important; }
.copy-btn:hover { color: #aaa !important; }

.tag-project {
  display: inline-block;
  background: #1f2a4a; border: 1px solid #2d4a8a;
  color: #85a5ff; border-radius: 4px;
  padding: 1px 8px; font-size: 12px;
}
.no-data { color: #444; font-size: 12px; }

.client-row {
  display: flex; align-items: center; gap: 7px;
  margin-bottom: 6px;
}
.status-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.status-dot.online  { background: #52c41a; }
.status-dot.offline { background: #444; }
.client-name { font-size: 12px; color: #ccc; }
.client-platform { font-size: 11px; color: #555; margin-left: auto; }

.markers-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-marker {
  display: inline-block;
  background: #1f3a2a; border: 1px solid #2d6a4a;
  color: #7ec8a0; border-radius: 4px;
  padding: 1px 8px; font-size: 12px;
}

.curl-label { padding-top: 6px; }
.curl-block-wrap {
  position: relative;
  min-width: 0;
  overflow: hidden;
}
.curl-block {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px; color: #abb2bf;
  background: #1a1a1a; border: 1px solid #2a2a2a;
  border-radius: 6px; padding: 10px 36px 10px 12px;
  margin: 0; white-space: pre; overflow-x: auto;
  line-height: 1.6;
}
.curl-copy-btn {
  position: absolute; top: 6px; right: 4px;
  color: #888 !important;
}
.curl-copy-btn:hover { color: #d0d0d0 !important; }
</style>
