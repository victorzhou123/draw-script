<template>
  <div class="script-sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">脚本列表</span>
      <a-button type="primary" size="small" @click="onNew">+ 新建</a-button>
    </div>
    <div class="filter-row">
      <a-select
        v-model:value="filterProjectId"
        size="small"
        style="width: 100%"
        placeholder="全部项目组"
        allow-clear
      >
        <a-select-option value="__none__">未分配项目组</a-select-option>
        <a-select-option v-for="p in projectStore.projects" :key="p.id" :value="p.id">{{ p.name }}</a-select-option>
      </a-select>
    </div>
    <a-spin :spinning="scriptStore.loading">
      <div
        v-for="script in filteredScripts"
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
                <a-menu-item key="settings" @click="openSettings(script)">
                  <SettingOutlined /> 设置
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
          <!-- Script Name -->
          <div class="info-label">脚本名称</div>
          <div class="info-value name-row">
            <template v-if="nameEditing">
              <a-input
                ref="nameInputRef"
                v-model:value="nameValue"
                size="small"
                class="name-input"
                @keyup.enter="saveName"
                @keyup.esc="cancelName"
              />
              <a-button type="text" size="small" class="name-action-btn confirm-btn" @click="saveName">
                <CheckOutlined style="color:#52c41a" />
              </a-button>
              <a-button type="text" size="small" class="name-action-btn" @click="cancelName">
                <CloseOutlined />
              </a-button>
            </template>
            <template v-else>
              <span class="name-text">{{ infoScript.name }}</span>
              <a-tooltip title="重命名">
                <a-button type="text" size="small" class="name-action-btn" @click="startEditName">
                  <EditOutlined />
                </a-button>
              </a-tooltip>
            </template>
          </div>

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

          <!-- References (this script calls) -->
          <div class="info-label">引用脚本</div>
          <div class="info-value ref-scripts-row">
            <template v-if="referencesScripts.length">
              <span v-for="s in referencesScripts" :key="s.id" class="tag-script-ref" @click="goToScript(s.id)">{{ s.name }}</span>
            </template>
            <span v-else class="no-data">—</span>
          </div>

          <!-- Referenced by (other scripts call this) -->
          <div class="info-label">被引用于</div>
          <div class="info-value ref-scripts-row">
            <template v-if="referencedByScripts.length">
              <span v-for="s in referencedByScripts" :key="s.id" class="tag-script-ref" @click="goToScript(s.id)">{{ s.name }}</span>
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
            <template v-if="startFields.length">
              <div class="param-desc-list">
                <div v-for="f in startFields" :key="f.name" class="param-desc-item">
                  <code class="param-fname">{{ f.name }}</code>
                  <code class="param-ftype">{{ f.type }}</code>
                  <span class="param-fdesc">{{ f.description }}</span>
                </div>
              </div>
            </template>
          </div>

          <!-- Return Results -->
          <div class="info-label return-label">返回结果</div>
          <div class="info-value return-block">
            <!-- Success -->
            <div class="return-subsection">
              <div class="return-sub-header">
                <span class="return-badge success">成功</span>
                <code class="return-status-code">status: "completed"</code>
              </div>
              <template v-if="returnInfo.fields.length">
                <div v-for="f in returnInfo.fields" :key="f.name" class="return-field-item">
                  <code class="return-fname">{{ f.name }}</code>
                  <span class="return-fdesc">{{ f.description || '' }}</span>
                </div>
              </template>
              <span v-else class="no-data" style="font-size:11px; display:block; margin: 4px 0 6px;">end 节点无返回字段</span>
              <div class="return-example-label">result_json：</div>
              <pre class="return-example">{{ successJsonExample }}</pre>
            </div>
            <!-- Failure -->
            <div class="return-subsection">
              <div class="return-sub-header">
                <span class="return-badge error">失败</span>
                <code class="return-status-code">status: "error" | "stopped"</code>
              </div>
              <div class="return-example-label">result_json：</div>
              <pre class="return-example">null</pre>
            </div>
          </div>

          <!-- Copy as Markdown -->
          <div class="md-copy-row">
            <a-button size="small" class="md-copy-btn" @click="copyMarkdown">
              <CheckOutlined v-if="mdCopied" style="color:#52c41a" />
              <CopyOutlined v-else />
              {{ mdCopied ? '已复制' : '复制为 Markdown' }}
            </a-button>
          </div>
        </div>
      </a-spin>
    </a-modal>

    <!-- Settings Modal -->
    <a-modal
      v-model:open="settingsModalOpen"
      title="脚本设置"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="settingsSaving"
      @ok="saveSettings"
    >
      <a-spin :spinning="settingsLoading">
        <a-form layout="vertical">
          <a-form-item label="绑定运行 Client">
            <a-select
              v-model:value="settingsClientId"
              style="width: 100%"
              placeholder="未绑定"
              allow-clear
              show-search
              :options="clientStore.clients.map(c => ({ value: c.id, label: `${c.name} (${c.id})` }))"
            />
            <div class="hint-text">绑定后，画布左上角会显示该 client，节点状态（动作/日志）也只跟踪这个 client 的执行情况</div>
          </a-form-item>
        </a-form>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { InfoCircleOutlined, CopyOutlined, CheckOutlined, EditOutlined, CloseOutlined, SettingOutlined } from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { useScriptStore } from '@/stores/scriptStore'
import { useProjectStore } from '@/stores/projectStore'
import { useClientStore } from '@/stores/clientStore'
import type { Script } from '@/services/api'

function getStartFields(script: Script): { name: string; type: string; default: string; description: string }[] {
  try {
    const flow = JSON.parse(script.flow_json || '{}')
    const startCell = (flow.cells ?? []).find((c: any) => c.shape === 'node-start')
    return (startCell?.data?.fields ?? []).map((f: any) => ({
      name: f.name ?? '',
      type: f.type ?? 'any',
      default: f.default ?? '',
      description: f.description ?? '',
    }))
  } catch {
    return []
  }
}

function getReturnInfo(script: Script): { fields: Array<{ name: string; description: string }> } {
  try {
    const flow = JSON.parse(script.flow_json || '{}')
    const endCell = (flow.cells ?? []).find((c: any) => c.shape === 'node-end')
    if (!endCell) return { fields: [] }
    const returnFields: string[] = endCell.data?.return_fields ?? []
    const descriptions: Record<string, string> = endCell.data?.return_field_descriptions ?? {}
    return { fields: returnFields.map(name => ({ name, description: descriptions[name] ?? '' })) }
  } catch {
    return { fields: [] }
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
onMounted(() => {
  scriptStore.fetchScripts()
  projectStore.fetchProjects()
})

const filterProjectId = ref<string | null>(null)

const filteredScripts = computed(() => {
  if (!filterProjectId.value) return scriptStore.scripts
  if (filterProjectId.value === '__none__') return scriptStore.scripts.filter(s => !s.project_id)
  return scriptStore.scripts.filter(s => s.project_id === filterProjectId.value)
})

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

const nameEditing  = ref(false)
const nameValue    = ref('')
const nameInputRef = ref<any>(null)

function startEditName() {
  nameValue.value = infoScript.value?.name ?? ''
  nameEditing.value = true
  nextTick(() => nameInputRef.value?.focus())
}

function cancelName() {
  nameEditing.value = false
}

async function saveName() {
  const newName = nameValue.value.trim()
  if (!newName || !infoScript.value) { cancelName(); return }
  if (newName === infoScript.value.name) { cancelName(); return }
  const updated = await scriptStore.renameScript(infoScript.value.id, newName)
  infoScript.value = { ...infoScript.value, name: updated.name }
  nameEditing.value = false
}

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

const referencesScripts = computed(() => {
  if (!infoScript.value) return []
  try {
    const flow = JSON.parse(infoScript.value.flow_json || '{}')
    const ids = new Set<string>()
    for (const cell of (flow.cells ?? [])) {
      if (cell.data?.type === 'script' && cell.data?.script_id) ids.add(cell.data.script_id)
    }
    return scriptStore.scripts.filter(s => ids.has(s.id))
  } catch { return [] }
})

const referencedByScripts = computed(() => {
  if (!infoScript.value) return []
  const id = infoScript.value.id
  return scriptStore.scripts.filter(s => {
    if (s.id === id) return false
    try {
      const flow = JSON.parse(s.flow_json || '{}')
      return (flow.cells ?? []).some((c: any) => c.data?.type === 'script' && c.data?.script_id === id)
    } catch { return false }
  })
})

async function goToScript(id: string) {
  infoModalOpen.value = false
  await onSelect(id)
}

const startFields = computed(() =>
  infoScript.value ? getStartFields(infoScript.value) : []
)

const returnInfo = computed(() =>
  infoScript.value ? getReturnInfo(infoScript.value) : { fields: [] }
)

const successJsonExample = computed(() => {
  const fields = returnInfo.value.fields
  if (!fields.length) return 'null'
  const obj: Record<string, string> = {}
  for (const f of fields) obj[f.name] = `<${f.name}>`
  return JSON.stringify(obj, null, 2)
})

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
  nameEditing.value = false
  infoModalOpen.value = true
  infoLoading.value = true
  await Promise.all([
    projectStore.projects.length === 0 ? projectStore.fetchProjects() : Promise.resolve(),
    clientStore.clients.length === 0   ? clientStore.fetchClients()   : Promise.resolve(),
  ])
  infoLoading.value = false
}

const settingsModalOpen = ref(false)
const settingsLoading   = ref(false)
const settingsSaving    = ref(false)
const settingsScript    = ref<Script | null>(null)
const settingsClientId  = ref<string | null>(null)

async function openSettings(script: Script) {
  settingsScript.value = script
  settingsClientId.value = script.default_client_id
  settingsModalOpen.value = true
  settingsLoading.value = true
  if (clientStore.clients.length === 0) await clientStore.fetchClients()
  settingsLoading.value = false
}

async function saveSettings() {
  if (!settingsScript.value) return
  settingsSaving.value = true
  try {
    await scriptStore.setDefaultClient(settingsScript.value.id, settingsClientId.value)
    settingsModalOpen.value = false
  } catch (e: any) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    settingsSaving.value = false
  }
}

function copyId() {
  if (!infoScript.value) return
  navigator.clipboard.writeText(infoScript.value.id)
  idCopied.value = true
  setTimeout(() => { idCopied.value = false }, 2000)
}

const mdCopied = ref(false)

function buildMarkdown(): string {
  if (!infoScript.value) return ''
  const lines: string[] = []

  lines.push(`# ${infoScript.value.name}`)
  lines.push('')

  // 调用方式
  lines.push('## 调用方式')
  lines.push('')
  lines.push('```bash')
  lines.push(curlCommand.value)
  lines.push('```')
  lines.push('')

  const fields = startFields.value.filter(f => f.name)
  if (fields.length) {
    lines.push('**请求参数（params）**')
    lines.push('')
    lines.push('| 字段 | 类型 | 说明 |')
    lines.push('| ---- | ---- | ---- |')
    for (const f of fields) {
      lines.push(`| \`${f.name}\` | ${f.type} | ${f.description || ''} |`)
    }
    lines.push('')
  }

  // 返回结果
  lines.push('## 返回结果')
  lines.push('')
  lines.push('**成功** `status: "completed"`')
  lines.push('')

  const rFields = returnInfo.value.fields
  if (rFields.length) {
    lines.push('| 字段 | 说明 |')
    lines.push('| ---- | ---- |')
    for (const f of rFields) {
      lines.push(`| \`${f.name}\` | ${f.description || ''} |`)
    }
    lines.push('')
    lines.push('`result_json` 示例：')
    lines.push('')
    lines.push('```json')
    lines.push(successJsonExample.value)
    lines.push('```')
  } else {
    lines.push('`result_json` 为 `null`（end 节点无返回字段）')
  }
  lines.push('')
  lines.push('**失败** `status: "error" | "stopped"`')
  lines.push('')
  lines.push('`result_json` 为 `null`，错误信息见响应的 `log` 字段。')

  return lines.join('\n')
}

async function copyMarkdown() {
  const text = buildMarkdown()
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
  mdCopied.value = true
  message.success('已复制为 Markdown')
  setTimeout(() => { mdCopied.value = false }, 2000)
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
.hint-text { font-size: 11px; color: #444; margin-top: 6px; line-height: 1.5; }
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

.filter-row { margin-bottom: 8px; }

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

.name-row { display: flex; align-items: center; gap: 4px; min-width: 0; }
.name-text { font-size: 13px; color: #d0d0d0; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.name-input { flex: 1; min-width: 0; font-size: 12px; background: #1a1a1a; border-color: #1890ff; color: #d0d0d0; }
.name-action-btn { flex-shrink: 0; color: #555 !important; padding: 0 4px !important; }
.name-action-btn:hover { color: #aaa !important; }
.confirm-btn { color: #555 !important; }
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

.ref-scripts-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-script-ref {
  display: inline-block;
  background: #2a1f3a; border: 1px solid #5a3a8a;
  color: #b79dff; border-radius: 4px;
  padding: 1px 8px; font-size: 12px;
  cursor: pointer; transition: border-color 0.15s, color 0.15s;
}
.tag-script-ref:hover { border-color: #7a5aaa; color: #d0b8ff; }
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
  position: absolute; bottom: 6px; right: 4px;
  color: #888 !important;
}
.curl-copy-btn:hover { color: #d0d0d0 !important; }

.md-copy-row {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  padding-top: 6px;
  border-top: 1px solid #222;
  margin-top: 4px;
}
.md-copy-btn {
  font-size: 12px !important;
  color: #666 !important;
  border-color: #303030 !important;
  background: transparent !important;
  display: flex; align-items: center; gap: 5px;
}
.md-copy-btn:hover { color: #aaa !important; border-color: #555 !important; }

.param-desc-list {
  margin-top: 8px;
  border-top: 1px solid #222;
  padding-top: 7px;
  display: flex; flex-direction: column; gap: 5px;
}
.param-desc-item { display: flex; align-items: baseline; gap: 6px; }
.param-fname {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px; color: #7ec8e3;
  background: #1e2a30; border-radius: 3px;
  padding: 1px 5px; flex-shrink: 0;
}
.param-ftype {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 10px; color: #555;
  flex-shrink: 0;
}
.param-fdesc { font-size: 11px; color: #666; min-width: 0; word-break: break-word; }

/* return results */
.return-label { padding-top: 6px; }
.return-block { min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.return-subsection {
  border: 1px solid #2a2a2a; border-radius: 6px;
  padding: 8px 10px; background: #1a1a1a;
}
.return-sub-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
}
.return-badge {
  display: inline-block; border-radius: 3px;
  padding: 1px 6px; font-size: 11px; font-weight: 600;
}
.return-badge.success { background: #1f3a2a; border: 1px solid #2d6a4a; color: #7ec8a0; }
.return-badge.error   { background: #3a1f1f; border: 1px solid #6a2d2d; color: #e07070; }
.return-status-code {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px; color: #666;
}
.return-field-item {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 4px;
}
.return-fname {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px; color: #7ec8e3;
  background: #1e2a30; border-radius: 3px;
  padding: 1px 5px; flex-shrink: 0;
}
.return-fdesc { font-size: 11px; color: #555; min-width: 0; word-break: break-word; }
.return-example-label { font-size: 10px; color: #444; margin: 6px 0 3px; }
.return-example {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px; color: #abb2bf;
  background: #111; border-radius: 4px;
  padding: 6px 8px; margin: 0;
  white-space: pre; overflow-x: auto; line-height: 1.5;
}
</style>
