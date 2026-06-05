<template>
  <a-drawer
    :open="open"
    title="客户端管理"
    placement="right"
    :width="540"
    :body-style="{ padding: 0, background: '#1a1a1a', display: 'flex', flexDirection: 'column', height: '100%' }"
    :header-style="{ background: '#1f1f1f', borderBottom: '1px solid #252525' }"
    @close="emit('close')"
  >
    <div class="drawer-body">

      <!-- ── 项目筛选 ───────────────────────────────── -->
      <div class="filter-bar">
        <span class="filter-chip" :class="{ active: !filterProjectId }" @click="filterProjectId = null">全部</span>
        <span
          v-for="p in projectStore.projects" :key="p.id"
          class="filter-chip" :class="{ active: filterProjectId === p.id }"
          @click="filterProjectId = p.id"
        >{{ p.name }}</span>
      </div>

      <!-- ── 批量操作（项目级）──────────────────────── -->
      <div v-if="filterProjectId" class="batch-bar">
        <FolderOutlined class="batch-icon" />
        <span class="batch-label">{{ projectStore.getProjectName(filterProjectId) }}</span>
        <a-select
          v-model:value="batchScriptId"
          size="small" placeholder="选择脚本" style="flex:1; min-width:0"
          :options="batchScripts.map(s => ({ label: s.name, value: s.id }))"
        />
        <a-button size="small" type="primary" :loading="batchRunning"
          :disabled="!batchScriptId || filteredConnected.length === 0"
          @click="runOnProject">
          <PlayCircleOutlined /> 全部运行
        </a-button>
        <a-button size="small" danger :disabled="!anyProjectRunning" @click="stopOnProject">
          <PauseCircleOutlined /> 全部停止
        </a-button>
      </div>

      <!-- ── 客户端列表 ─────────────────────────────── -->
      <div class="section">
        <div class="section-header">
          <span class="section-title"><LaptopOutlined /> 客户端</span>
          <a-button size="small" type="text" class="icon-btn" @click="refresh"><ReloadOutlined /></a-button>
        </div>

        <div v-if="filteredClients.length === 0" class="empty-hint">
          {{ filterProjectId ? '此项目组下暂无客户端' : '暂无客户端' }}
        </div>

        <div v-for="c in filteredClients" :key="c.id"
          class="client-card" :class="{ selected: selectedClientId === c.id, running: executionStore.isRunning(c.id) }">

          <!-- 主行 -->
          <div class="client-main" @click="toggleClient(c.id)">
            <div class="client-left">
              <span class="status-dot" :class="`dot-${runtimeStatus(c)}`" />
              <div class="client-info">
                <span class="client-name">{{ c.name }}</span>
                <span class="client-meta">{{ c.id }} · {{ c.platform }}</span>
              </div>
            </div>
            <div class="client-right">
              <span class="status-label" :class="`label-${runtimeStatus(c)}`">{{ statusLabel(runtimeStatus(c)) }}</span>
              <CaretDownOutlined class="expand-icon" :class="{ expanded: selectedClientId === c.id }" />
            </div>
          </div>

          <!-- 只读项目标签 -->
          <div v-if="c.project_ids.length > 0" class="client-projects">
            <span v-for="pid in c.project_ids" :key="pid" class="project-tag">
              <FolderOutlined /> {{ projectStore.getProjectName(pid) }}
            </span>
          </div>

          <!-- 展开详情 -->
          <div v-if="selectedClientId === c.id" class="client-detail">
            <!-- 运行控制 -->
            <div class="detail-section">
              <span class="detail-label">运行脚本</span>
              <div class="run-row">
                <a-select
                  v-model:value="clientScriptSelections[c.id]"
                  size="small" placeholder="选择脚本" style="flex:1; min-width:0"
                  :options="clientScripts(c).map(s => ({ label: s.name, value: s.id }))"
                  :disabled="executionStore.isRunning(c.id)"
                />
                <a-button
                  v-if="!isClientBusy(c)"
                  size="small" type="primary"
                  :disabled="!clientScriptSelections[c.id] || !clientStore.connectedIds.has(c.id)"
                  :loading="runningClients.has(c.id)"
                  @click="runClient(c.id)"
                >
                  <PlayCircleOutlined /> 运行
                </a-button>
                <a-button v-else size="small" danger :loading="stoppingClients.has(c.id)" @click="stopClient(c.id)">
                  <PauseCircleOutlined /> 停止
                </a-button>
              </div>
              <div v-if="!clientStore.connectedIds.has(c.id)" class="warn-hint">客户端未连接</div>
              <div v-else-if="clientScripts(c).length === 0" class="warn-hint">需在项目组中关联含脚本后方可运行</div>
            </div>

            <!-- GPU 加速 -->
            <div class="detail-section">
              <span class="detail-label">GPU 加速</span>
              <div class="gpu-row">
                <a-switch
                  :checked="c.gpu_enabled"
                  size="small"
                  :loading="gpuUpdating.has(c.id)"
                  @change="(val: boolean) => toggleGpu(c.id, val)"
                />
                <span class="gpu-label">{{ c.gpu_enabled ? 'CUDA 加速' : 'CPU 模式' }}</span>
                <span class="gpu-hint">仅影响模板匹配，需客户端安装 opencv-python-cuda</span>
              </div>
            </div>

            <!-- 可用脚本 -->
            <div class="detail-section">
              <span class="detail-label">可用脚本</span>
              <div class="scripts-chips">
                <span v-for="s in clientScripts(c)" :key="s.id" class="script-chip">
                  <FileTextOutlined /> {{ s.name }}
                </span>
                <span v-if="clientScripts(c).length === 0" class="no-scripts">在项目组中关联脚本后自动可用</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 执行日志 ────────────────────────────────── -->
      <div class="divider" />
      <div class="log-section">
        <div class="section-header">
          <span class="section-title"><CodeOutlined /> 执行日志</span>
          <span v-if="selectedClientId" class="log-client-tag">{{ clientName(selectedClientId) }}</span>
          <a-button size="small" type="text" class="icon-btn" :disabled="!selectedClientId" @click="executionStore.clearLogs(selectedClientId!)">
            <ClearOutlined />
          </a-button>
        </div>
        <div class="log-box" ref="logBoxEl">
          <template v-if="selectedClientId">
            <div v-for="(line, i) in executionStore.logsFor(selectedClientId)" :key="i" class="log-line">{{ line }}</div>
            <div v-if="!executionStore.logsFor(selectedClientId).length" class="log-empty">等待执行...</div>
          </template>
          <div v-else class="log-empty">点击客户端卡片查看日志</div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import {
  LaptopOutlined, ReloadOutlined, FolderOutlined,
  PlayCircleOutlined, PauseCircleOutlined,
  FileTextOutlined, CodeOutlined, ClearOutlined, CaretDownOutlined,
} from '@ant-design/icons-vue'
import { useClientStore } from '@/stores/clientStore'
import { useProjectStore } from '@/stores/projectStore'
import { useScriptStore } from '@/stores/scriptStore'
import { useExecutionStore } from '@/stores/executionStore'
import type { Client } from '@/services/api'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const clientStore = useClientStore()
const projectStore = useProjectStore()
const scriptStore = useScriptStore()
const executionStore = useExecutionStore()

const filterProjectId = ref<string | null>(null)
const selectedClientId = ref<string | null>(null)
const clientScriptSelections = ref<Record<string, string>>({})
const runningClients = ref(new Set<string>())
const stoppingClients = ref(new Set<string>())
const gpuUpdating = ref(new Set<string>())
const batchScriptId = ref<string | null>(null)
const batchRunning = ref(false)
const logBoxEl = ref<HTMLElement>()

const filteredClients = computed(() =>
  filterProjectId.value
    ? clientStore.clients.filter(c => c.project_ids.includes(filterProjectId.value!))
    : clientStore.clients
)
const filteredConnected = computed(() => filteredClients.value.filter(c => clientStore.connectedIds.has(c.id)))
const batchScripts = computed(() => filterProjectId.value ? scriptStore.scripts.filter(s => s.project_id === filterProjectId.value) : [])
const anyProjectRunning = computed(() => filteredConnected.value.some(c => isClientBusy(c)))

function clientScripts(c: Client) {
  return scriptStore.scripts.filter(s => s.project_id && c.project_ids.includes(s.project_id))
}
function isClientBusy(c: Client) { return executionStore.isRunning(c.id) || c.status === 'busy' }
function runtimeStatus(c: Client) { return isClientBusy(c) ? 'running' : c.status }
function statusLabel(s: string) { return { idle: '空闲', running: '运行中', disconnected: '离线', timeout: '超时' }[s] ?? s }
function clientName(cid: string) { return clientStore.clients.find(c => c.id === cid)?.name ?? cid }
function toggleClient(id: string) { selectedClientId.value = selectedClientId.value === id ? null : id }
async function refresh() { await clientStore.fetchClients() }

async function runClient(clientId: string) {
  const scriptId = clientScriptSelections.value[clientId]
  if (!scriptId) return
  runningClients.value.add(clientId)
  try { await executionStore.runOnClient(scriptId, clientId) }
  catch (e: any) { message.error(e.response?.data?.detail || '启动失败') }
  finally { runningClients.value.delete(clientId) }
}
async function stopClient(clientId: string) {
  stoppingClients.value.add(clientId)
  try { await executionStore.stopOnClient(clientId) }
  finally { stoppingClients.value.delete(clientId) }
}
async function toggleGpu(clientId: string, enabled: boolean) {
  gpuUpdating.value.add(clientId)
  try { await clientStore.updateGpu(clientId, enabled) }
  catch (e: any) { message.error(e.response?.data?.detail || 'GPU 设置失败') }
  finally { gpuUpdating.value.delete(clientId) }
}
async function runOnProject() {
  if (!batchScriptId.value) return
  batchRunning.value = true
  try {
    await executionStore.runOnProject(batchScriptId.value, filteredConnected.value.map(c => c.id))
    message.success(`已启动 ${filteredConnected.value.length} 个客户端`)
  } finally { batchRunning.value = false }
}
async function stopOnProject() {
  await executionStore.stopOnProject(filteredConnected.value.map(c => c.id))
}
watch(() => props.open, async (v) => {
  if (v) await Promise.all([clientStore.fetchClients(), projectStore.fetchProjects(), scriptStore.fetchScripts()])
})
watch(
  () => selectedClientId.value ? executionStore.logsFor(selectedClientId.value).length : 0,
  async () => {
    await nextTick()
    if (logBoxEl.value) logBoxEl.value.scrollTop = logBoxEl.value.scrollHeight
  },
)
</script>

<style scoped>
.drawer-body { flex: 1; overflow: hidden; display: flex; flex-direction: column; min-height: 0; }
.filter-bar { display: flex; align-items: center; gap: 6px; padding: 10px 16px; border-bottom: 1px solid #222; flex-wrap: wrap; flex-shrink: 0; }
.filter-chip { font-size: 11px; padding: 3px 10px; border-radius: 12px; border: 1px solid #2e2e2e; color: #555; cursor: pointer; transition: all 0.15s; user-select: none; }
.filter-chip:hover { border-color: #444; color: #888; }
.filter-chip.active { border-color: #1890ff44; background: #111d2c; color: #1890ff; }
.batch-bar { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #1f1f1f; border-bottom: 1px solid #222; flex-shrink: 0; }
.batch-icon { color: #1890ff; font-size: 13px; }
.batch-label { font-size: 12px; color: #1890ff; font-weight: 500; white-space: nowrap; }
.section { padding: 10px 16px; overflow-y: auto; flex-shrink: 0; max-height: 55vh; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.section-title { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 1px; }
.divider { height: 1px; background: #222; flex-shrink: 0; }
.icon-btn { color: #444 !important; }
.icon-btn:hover { color: #888 !important; }
.empty-hint { font-size: 12px; color: #3a3a3a; padding: 8px 0; }
.client-card { border: 1px solid #252525; border-radius: 6px; background: #1f1f1f; margin-bottom: 6px; transition: border-color 0.15s; }
.client-card:hover { border-color: #2e2e2e; }
.client-card.selected { border-color: #1890ff33; }
.client-card.running { border-color: #1890ff55; }
.client-main { display: flex; align-items: center; justify-content: space-between; padding: 9px 12px 5px; cursor: pointer; user-select: none; }
.client-left { display: flex; align-items: center; gap: 8px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-idle { background: #52c41a; }
.dot-running { background: #1890ff; box-shadow: 0 0 5px #1890ff; animation: blink 1s infinite; }
.dot-disconnected { background: #333; }
.dot-timeout { background: #faad14; }
.client-info { display: flex; flex-direction: column; }
.client-name { font-size: 13px; color: #d0d0d0; font-weight: 500; }
.client-meta { font-size: 11px; color: #444; }
.client-right { display: flex; align-items: center; gap: 8px; }
.status-label { font-size: 11px; }
.label-idle { color: #52c41a; }
.label-running { color: #1890ff; }
.label-disconnected { color: #444; }
.label-timeout { color: #faad14; }
.expand-icon { font-size: 10px; color: #3a3a3a; transition: transform 0.2s; }
.expand-icon.expanded { transform: rotate(180deg); }
.client-projects { display: flex; flex-wrap: wrap; gap: 4px; padding: 0 12px 8px 27px; }
.project-tag { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #555; background: #222; border: 1px solid #2a2a2a; border-radius: 12px; padding: 1px 8px; }
.project-tag .anticon { font-size: 10px; color: #444; }
.client-detail { border-top: 1px solid #252525; padding: 10px 12px; display: flex; flex-direction: column; gap: 12px; }
.detail-section { display: flex; flex-direction: column; gap: 6px; }
.detail-label { font-size: 10px; color: #444; text-transform: uppercase; letter-spacing: 0.8px; }
.run-row { display: flex; gap: 6px; align-items: center; }
.gpu-row { display: flex; align-items: center; gap: 8px; }
.gpu-label { font-size: 12px; color: #888; }
.gpu-hint { font-size: 11px; color: #3a3a3a; margin-left: auto; }
.warn-hint { font-size: 11px; color: #4a4a4a; }
.scripts-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.script-chip { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; color: #555; background: #222; border: 1px solid #2a2a2a; border-radius: 3px; padding: 2px 6px; }
.no-scripts { font-size: 11px; color: #333; }
.log-section { flex: 1; display: flex; flex-direction: column; padding: 10px 16px 12px; min-height: 0; }
.log-box { flex: 1; overflow-y: auto; background: #111; border: 1px solid #222; border-radius: 4px; padding: 8px 10px; font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; min-height: 60px; }
.log-line { color: #7ec87e; line-height: 1.7; white-space: pre-wrap; word-break: break-all; }
.log-empty { color: #2e2e2e; font-size: 11px; }
.log-client-tag { font-size: 11px; color: #1890ff; background: #111d2c; border: 1px solid #1890ff33; padding: 1px 8px; border-radius: 10px; margin-left: auto; margin-right: 4px; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
</style>
