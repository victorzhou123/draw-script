<template>
  <a-drawer
    :open="open"
    title="日志中心"
    placement="right"
    :width="'80vw'"
    :body-style="{ padding: 0, background: '#0d0d0d', display: 'flex', flexDirection: 'column', height: '100%' }"
    :header-style="{ background: '#141414', borderBottom: '1px solid #222' }"
    @close="emit('close')"
  >
    <a-tabs
      v-model:activeKey="activeTab"
      size="small"
      class="log-tabs"
      :tab-bar-style="{ margin: 0, padding: '0 16px', background: '#141414', borderBottom: '1px solid #1e1e1e' }"
    >
      <!-- ── 日志查询 ──────────────────────────────────────── -->
      <a-tab-pane key="logs" tab="日志查询" class="log-pane">

        <!-- Time bar -->
        <div class="time-bar">
          <span class="time-label">时间范围</span>
          <a-radio-group
            v-model:value="timePreset"
            size="small"
            button-style="solid"
            class="preset-group"
            @change="onPresetChange"
          >
            <a-radio-button v-for="p in TIME_PRESETS" :key="p.value" :value="p.value">{{ p.label }}</a-radio-button>
            <a-radio-button value="custom">自定义</a-radio-button>
          </a-radio-group>
          <template v-if="timePreset === 'custom'">
            <a-date-picker
              v-model:value="customStart"
              show-time
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DDTHH:mm:ss"
              size="small"
              placeholder="开始时间"
              style="width:175px"
              :allow-clear="true"
            />
            <span class="time-sep">→</span>
            <a-date-picker
              v-model:value="customEnd"
              show-time
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DDTHH:mm:ss"
              size="small"
              placeholder="结束时间"
              style="width:175px"
              :allow-clear="true"
            />
          </template>
        </div>

        <!-- Filter bar -->
        <div class="filter-bar">
          <a-select v-model:value="filters.source" size="small" style="width:90px" :options="sourceOptions" />
          <a-select v-model:value="filters.level" size="small" style="width:100px" :options="levelOptions" />
          <a-select
            v-model:value="filters.script_id"
            size="small"
            style="width:140px"
            placeholder="脚本"
            allow-clear
            show-search
            :filter-option="(input, opt) => (opt?.label as string)?.toLowerCase().includes(input.toLowerCase())"
            :options="scriptOptions"
          />
          <a-select
            v-model:value="filters.client_id"
            size="small"
            style="width:120px"
            placeholder="客户端"
            allow-clear
            :options="clientOptions"
          />
          <a-input
            v-model:value="filters.keyword"
            size="small"
            placeholder="关键字搜索..."
            allow-clear
            style="width:180px"
            @press-enter="doQuery"
          >
            <template #prefix><SearchOutlined style="color:#444" /></template>
          </a-input>
          <a-button size="small" type="primary" ghost @click="doQuery">查询</a-button>
          <a-button size="small" class="ctrl-btn" @click="resetFilters">重置</a-button>
          <div style="flex:1" />
          <a-button size="small" class="ctrl-btn" :class="{ 'btn-active': autoRefresh }" @click="toggleAutoRefresh">
            {{ autoRefresh ? `自动刷新 (${refreshInterval}s)` : '自动刷新' }}
          </a-button>
          <a-button size="small" class="ctrl-btn" :loading="loading" @click="doQuery">
            <ReloadOutlined /> 刷新
          </a-button>
          <a-popconfirm title="清空所有持久化日志？此操作不可撤销。" @confirm="clearLogs">
            <a-button size="small" danger class="ctrl-btn">清空</a-button>
          </a-popconfirm>
        </div>

        <!-- Log table -->
        <div class="table-wrap">
          <a-table
            :data-source="records"
            :columns="columns"
            :pagination="false"
            :loading="loading"
            size="small"
            row-key="id"
            :scroll="{ y: 'calc(100vh - 300px)' }"
            class="log-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'timestamp'">
                <span class="cell-time">{{ formatTime(record.timestamp) }}</span>
              </template>
              <template v-else-if="column.key === 'level'">
                <span :class="`tag-level level-${record.level.toLowerCase()}`">{{ record.level }}</span>
              </template>
              <template v-else-if="column.key === 'source'">
                <a-tag :color="record.source === 'system' ? 'blue' : 'purple'" style="font-size:11px">
                  {{ record.source === 'system' ? '系统' : '执行' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'message'">
                <a-tooltip :title="record.message" placement="topLeft" :overlay-style="{ maxWidth: '600px' }">
                  <span class="cell-msg" v-html="highlight(record.message)" />
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'client_id'">
                <span class="cell-meta">{{ clientName(record.client_id) }}</span>
              </template>
              <template v-else-if="column.key === 'script_id'">
                <span class="cell-meta">{{ scriptName(record.script_id) }}</span>
              </template>
              <template v-else-if="column.key === 'node'">
                <span v-if="record.node_label || record.node_type" class="cell-node">
                  <span class="node-label">{{ record.node_label || '-' }}</span>
                  <span v-if="record.node_type" class="node-type">{{ record.node_type }}</span>
                </span>
                <span v-else class="cell-meta">{{ record.logger_name || '-' }}</span>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-tooltip v-if="record.script_id && record.node_id" title="跳转到节点">
                  <a-button
                    type="text"
                    size="small"
                    class="nav-btn"
                    @click="emit('navigate', record.script_id!, record.node_id!)"
                  >→</a-button>
                </a-tooltip>
              </template>
            </template>
          </a-table>
        </div>

        <!-- Pagination -->
        <div class="pagination-bar">
          <span class="total-hint">共 {{ total }} 条</span>
          <a-pagination
            v-model:current="page"
            :total="total"
            :page-size="pageSize"
            :show-size-changer="true"
            :page-size-options="['50', '100', '200', '500']"
            size="small"
            @change="onPageChange"
            @show-size-change="onSizeChange"
          />
        </div>
      </a-tab-pane>

      <!-- ── 日志设置 ──────────────────────────────────────── -->
      <a-tab-pane key="settings" tab="日志设置" class="settings-pane">
        <div class="settings-body">
          <a-form :model="settingsForm" layout="vertical" style="max-width:400px">
            <a-form-item label="日志保留天数" help="超过此天数的日志将在每次启动时自动清理">
              <a-input-number
                v-model:value="settingsForm.log_retention_days"
                :min="1"
                :max="365"
                addon-after="天"
                style="width:160px"
              />
            </a-form-item>
            <a-form-item label="自动刷新间隔" help="日志查询页面开启自动刷新时的轮询间隔">
              <a-input-number
                v-model:value="settingsForm.log_auto_refresh_interval"
                :min="2"
                :max="300"
                addon-after="秒"
                style="width:160px"
              />
            </a-form-item>
            <a-form-item>
              <a-button type="primary" :loading="savingSettings" @click="saveSettings">保存设置</a-button>
            </a-form-item>
          </a-form>
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, reactive } from 'vue'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { api, type AppLogEntry, type Script, type Client } from '../services/api'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'navigate', scriptId: string, nodeId: string): void
}>()

// ── Constants ─────────────────────────────────────────────────────────────────
const TIME_PRESETS = [
  { label: '1h',  value: '1h'  },
  { label: '6h',  value: '6h'  },
  { label: '12h', value: '12h' },
  { label: '24h', value: '24h' },
  { label: '48h', value: '48h' },
  { label: '7d',  value: '7d'  },
  { label: '14d', value: '14d' },
  { label: '30d', value: '30d' },
]

// ── State ─────────────────────────────────────────────────────────────────────
const activeTab = ref('logs')
const loading = ref(false)
const records = ref<AppLogEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const autoRefresh = ref(false)
const refreshInterval = ref(5)
const savingSettings = ref(false)

const scripts = ref<Script[]>([])
const clients = ref<Client[]>([])

// Time range state
const timePreset = ref('24h')
const customStart = ref<string | null>(null)
const customEnd = ref<string | null>(null)

const filters = reactive({
  source: 'ALL',
  level: 'ALL',
  script_id: undefined as string | undefined,
  client_id: undefined as string | undefined,
  keyword: '',
})

const settingsForm = reactive({
  log_retention_days: 7,
  log_auto_refresh_interval: 5,
})

// ── Options ───────────────────────────────────────────────────────────────────
const sourceOptions = [
  { label: '全部来源', value: 'ALL' },
  { label: '系统', value: 'system' },
  { label: '执行', value: 'execution' },
]

const levelOptions = [
  { label: '全部级别', value: 'ALL' },
  { label: 'DEBUG', value: 'DEBUG' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' },
]

const scriptOptions = computed(() =>
  scripts.value.map(s => ({ label: s.name, value: s.id }))
)

const clientOptions = computed(() =>
  clients.value.map(c => ({ label: c.name, value: c.id }))
)

// ── Lookup maps ───────────────────────────────────────────────────────────────
const scriptMap = computed(() => Object.fromEntries(scripts.value.map(s => [s.id, s.name])))
const clientMap = computed(() => Object.fromEntries(clients.value.map(c => [c.id, c.name])))

function scriptName(id: string | null) {
  return id ? (scriptMap.value[id] ?? id.slice(0, 8)) : '-'
}
function clientName(id: string | null) {
  return id ? (clientMap.value[id] ?? id) : '-'
}

// ── Columns ───────────────────────────────────────────────────────────────────
const columns = [
  { title: '时间', key: 'timestamp', width: 165, fixed: 'left' },
  { title: '级别', key: 'level', width: 75 },
  { title: '来源', key: 'source', width: 70 },
  { title: '消息', key: 'message', ellipsis: true },
  { title: '节点', key: 'node', width: 180, ellipsis: true },
  { title: '客户端', key: 'client_id', width: 110, ellipsis: true },
  { title: '脚本', key: 'script_id', width: 110, ellipsis: true },
  { title: '', key: 'action', width: 36, fixed: 'right' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatTime(iso: string) {
  // Stored as local time (no timezone), display as-is
  return iso.replace('T', ' ').slice(0, 19)
}

function escapeHtml(text: string) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlight(text: string) {
  const kw = filters.keyword.trim()
  const escaped = escapeHtml(text)
  if (!kw) return escaped
  const escapedKw = escapeHtml(kw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped.replace(new RegExp(escapedKw, 'gi'), m => `<mark class="log-hl">${m}</mark>`)
}

// ── Data loading ──────────────────────────────────────────────────────────────
function buildTimeParams() {
  if (timePreset.value !== 'custom') {
    return { time_range: timePreset.value }
  }
  return {
    start_time: customStart.value || undefined,
    end_time: customEnd.value || undefined,
  }
}

async function doQuery() {
  loading.value = true
  try {
    const res = await api.getLogs({
      level: filters.level === 'ALL' ? undefined : filters.level,
      source: filters.source === 'ALL' ? undefined : filters.source,
      script_id: filters.script_id || undefined,
      client_id: filters.client_id || undefined,
      keyword: filters.keyword || undefined,
      ...buildTimeParams(),
      page: page.value,
      page_size: pageSize.value,
    })
    records.value = res.items
    total.value = res.total
  } catch {
    message.error('获取日志失败')
  } finally {
    loading.value = false
  }
}

function onPresetChange() {
  if (timePreset.value !== 'custom') {
    page.value = 1
    doQuery()
  }
}

function resetFilters() {
  filters.source = 'ALL'
  filters.level = 'ALL'
  filters.script_id = undefined
  filters.client_id = undefined
  filters.keyword = ''
  timePreset.value = '24h'
  customStart.value = null
  customEnd.value = null
  page.value = 1
  doQuery()
}

async function clearLogs() {
  await api.clearPersistentLogs()
  records.value = []
  total.value = 0
  message.success('日志已清空')
}

function onPageChange(p: number) {
  page.value = p
  doQuery()
}

function onSizeChange(_: number, size: number) {
  pageSize.value = size
  page.value = 1
  doQuery()
}

// ── Auto-refresh ──────────────────────────────────────────────────────────────
let timer: ReturnType<typeof setInterval> | null = null

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    timer = setInterval(doQuery, refreshInterval.value * 1000)
  } else {
    if (timer) { clearInterval(timer); timer = null }
  }
}

function restartTimer() {
  if (timer) { clearInterval(timer); timer = null }
  if (autoRefresh.value) {
    timer = setInterval(doQuery, refreshInterval.value * 1000)
  }
}

// ── Settings ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const s = await api.getAppSettings()
    settingsForm.log_retention_days = s.log_retention_days
    settingsForm.log_auto_refresh_interval = s.log_auto_refresh_interval
    refreshInterval.value = s.log_auto_refresh_interval
    restartTimer()
  } catch {
    // ignore
  }
}

async function saveSettings() {
  savingSettings.value = true
  try {
    await api.updateAppSettings({
      log_retention_days: settingsForm.log_retention_days,
      log_auto_refresh_interval: settingsForm.log_auto_refresh_interval,
    })
    refreshInterval.value = settingsForm.log_auto_refresh_interval
    restartTimer()
    message.success('设置已保存')
  } catch {
    message.error('保存失败')
  } finally {
    savingSettings.value = false
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
watch(() => props.open, async (val) => {
  if (val) {
    const [s, c] = await Promise.all([api.getScripts(), api.getClients()])
    scripts.value = s
    clients.value = c
    await Promise.all([doQuery(), loadSettings()])
  } else {
    if (timer) { clearInterval(timer); timer = null }
    autoRefresh.value = false
  }
}, { immediate: true })

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.log-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
}
:deep(.ant-tabs-content-holder) {
  flex: 1;
  overflow: hidden;
}
:deep(.ant-tabs-content) {
  height: 100%;
}
:deep(.ant-tabs-tabpane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Time bar */
.time-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  background: #0f0f0f;
  border-bottom: 1px solid #1a1a1a;
  flex-wrap: wrap;
}
.time-label { color: #555; font-size: 12px; flex-shrink: 0; }
.time-sep { color: #444; font-size: 13px; }

.preset-group :deep(.ant-radio-button-wrapper) {
  background: transparent;
  border-color: #2a2a2a;
  color: #666;
  font-size: 12px;
  padding: 0 9px;
  height: 24px;
  line-height: 22px;
}
.preset-group :deep(.ant-radio-button-wrapper:hover) { color: #aaa; border-color: #444; }
.preset-group :deep(.ant-radio-button-wrapper-checked) {
  background: #177ddc !important;
  border-color: #177ddc !important;
  color: #fff !important;
}

:deep(.ant-picker) { background: #141414 !important; border-color: #2a2a2a !important; }
:deep(.ant-picker-input > input) { color: #ccc !important; font-size: 12px; }
:deep(.ant-picker-suffix) { color: #444; }
:deep(.ant-picker-clear) { background: #141414; }

/* Filter bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: #111;
  border-bottom: 1px solid #1e1e1e;
  flex-wrap: wrap;
}

.ctrl-btn {
  background: transparent !important;
  border-color: #303030 !important;
  color: #888 !important;
  font-size: 12px;
}
.ctrl-btn:hover { color: #ccc !important; border-color: #555 !important; }
.btn-active { color: #1890ff !important; border-color: #1890ff !important; }

/* Table */
.table-wrap {
  flex: 1;
  overflow: hidden;
}

.log-table {
  font-family: 'Consolas', 'Monaco', 'Menlo', monospace;
  font-size: 12px;
}

:deep(.ant-table) { background: #0d0d0d; }
:deep(.ant-table-thead > tr > th) {
  background: #141414 !important;
  color: #666 !important;
  border-bottom: 1px solid #1e1e1e !important;
  font-size: 11px;
  padding: 5px 8px !important;
}
:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #141414 !important;
  padding: 4px 8px !important;
  color: #bbb;
}
:deep(.ant-table-tbody > tr:hover > td) { background: #161616 !important; }
:deep(.ant-table-tbody > tr.ant-table-row:hover > td) { background: #161616 !important; }

.cell-time { color: #555; white-space: nowrap; font-size: 11px; }
.cell-meta { color: #555; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
.cell-msg { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 600px; }

.cell-node { display: flex; align-items: center; gap: 4px; min-width: 0; }
.node-label { color: #ccc; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-type { color: #444; font-size: 10px; flex-shrink: 0; background: #1a1a1a; border-radius: 3px; padding: 0 4px; }

.nav-btn {
  color: #555 !important;
  font-size: 13px;
  padding: 0 4px !important;
  height: 20px !important;
  line-height: 20px !important;
}
.nav-btn:hover { color: #1890ff !important; }

.tag-level {
  font-size: 11px;
  font-weight: 600;
  font-family: 'Consolas', monospace;
}
.level-debug   { color: #555; }
.level-info    { color: #1890ff; }
.level-warning { color: #faad14; }
.level-error   { color: #ff4d4f; }
.level-critical { color: #ff4d4f; }

:deep(.log-hl) {
  background: #b8860b;
  color: #fff;
  border-radius: 2px;
  padding: 0 1px;
}

/* Pagination */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 8px 14px;
  background: #111;
  border-top: 1px solid #1e1e1e;
}
.total-hint { color: #555; font-size: 12px; }

:deep(.ant-pagination-item) { background: transparent; border-color: #303030; }
:deep(.ant-pagination-item a) { color: #666; }
:deep(.ant-pagination-item-active) { border-color: #1890ff !important; }
:deep(.ant-pagination-item-active a) { color: #1890ff !important; }
:deep(.ant-pagination-prev .ant-pagination-item-link),
:deep(.ant-pagination-next .ant-pagination-item-link) {
  background: transparent; border-color: #303030; color: #666;
}

/* Settings tab */
.settings-pane { padding: 24px; }
.settings-body { max-width: 500px; }

:deep(.ant-form-item-label > label) { color: #aaa; }
:deep(.ant-form-item-explain) { color: #555; font-size: 12px; }
:deep(.ant-input-number) { background: #141414; border-color: #303030; color: #ccc; }
:deep(.ant-input-number-group-addon) { background: #1a1a1a; border-color: #303030; color: #666; }
</style>
