<template>
  <a-drawer
    :open="open"
    title="后端日志"
    placement="bottom"
    :height="420"
    :body-style="{ padding: 0, background: '#0d0d0d', display: 'flex', flexDirection: 'column', height: '100%' }"
    :header-style="{ background: '#141414', borderBottom: '1px solid #222' }"
    @close="emit('close')"
  >
    <template #extra>
      <div style="display:flex;align-items:center;gap:8px">
        <a-input
          v-model:value="searchKeyword"
          size="small"
          placeholder="搜索日志..."
          allow-clear
          style="width:180px"
        >
          <template #prefix><SearchOutlined style="color:#444" /></template>
        </a-input>
        <a-select
          v-model:value="levelFilter"
          size="small"
          style="width:100px"
          :options="levelOptions"
        />
        <a-button size="small" class="log-ctrl-btn" :class="{ 'btn-active': hideNoise }" @click="hideNoise = !hideNoise">
          {{ hideNoise ? '已屏蔽噪音' : '屏蔽噪音' }}
        </a-button>
        <a-button size="small" class="log-ctrl-btn" @click="loadLogs">
          <ReloadOutlined /> 刷新
        </a-button>
        <a-button size="small" class="log-ctrl-btn" @click="toggleAutoRefresh">
          {{ autoRefresh ? '停止自动刷新' : '自动刷新' }}
        </a-button>
        <a-popconfirm title="清空日志缓冲区？" @confirm="clearLogs">
          <a-button size="small" danger class="log-ctrl-btn">清空</a-button>
        </a-popconfirm>
      </div>
    </template>

    <div ref="logContainer" class="log-container">
      <div
        v-for="(rec, i) in filtered"
        :key="i"
        class="log-line"
        :class="`level-${rec.level.toLowerCase()}`"
      >
        <span class="log-time">{{ rec.time }}</span>
        <span class="log-level">{{ rec.level.padEnd(8) }}</span>
        <span class="log-name">{{ rec.name }}</span>
        <span class="log-msg" v-html="highlight(rec.msg)"></span>
      </div>
      <div v-if="filtered.length === 0" class="log-empty">暂无日志</div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import axios from 'axios'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

interface LogRecord {
  time: string
  level: string
  name: string
  msg: string
}

const WS_NOISE_RE = /^[<>%] /

function isNoise(r: LogRecord): boolean {
  if (r.name === 'uvicorn.error' && WS_NOISE_RE.test(r.msg)) return true
  if (r.name === 'uvicorn.access' && r.msg.includes('/api/logs')) return true
  return false
}

const records = ref<LogRecord[]>([])
const levelFilter = ref('ALL')
const searchKeyword = ref('')
const hideNoise = ref(true)
const autoRefresh = ref(true)
const logContainer = ref<HTMLElement>()

const levelOptions = [
  { label: '全部', value: 'ALL' },
  { label: 'DEBUG', value: 'DEBUG' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' },
]

const filtered = computed(() => {
  let list = records.value
  if (hideNoise.value) list = list.filter(r => !isNoise(r))
  if (levelFilter.value !== 'ALL') list = list.filter(r => r.level === levelFilter.value)
  const kw = searchKeyword.value.trim().toLowerCase()
  if (kw) list = list.filter(r => r.msg.toLowerCase().includes(kw) || r.name.toLowerCase().includes(kw))
  return list
})

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlight(text: string): string {
  const kw = searchKeyword.value.trim()
  if (!kw) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const escapedKw = escapeHtml(kw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped.replace(new RegExp(escapedKw, 'gi'), m => `<mark class="log-highlight">${m}</mark>`)
}

async function loadLogs() {
  try {
    const res = await axios.get<LogRecord[]>('/api/logs', { params: { limit: 300 } })
    records.value = res.data
    await nextTick()
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  } catch {
    message.error('获取日志失败')
  }
}

async function clearLogs() {
  await axios.delete('/api/logs')
  records.value = []
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
}

let timer: ReturnType<typeof setInterval> | null = null

watch(() => props.open, (val) => {
  if (val) {
    loadLogs()
    timer = setInterval(() => { if (autoRefresh.value) loadLogs() }, 2000)
  } else {
    if (timer) { clearInterval(timer); timer = null }
  }
}, { immediate: true })

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
  font-family: 'Consolas', 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.7;
}

.log-line {
  display: flex;
  gap: 10px;
  padding: 0 14px;
  white-space: pre-wrap;
  word-break: break-all;
}
.log-line:hover { background: #161616; }

.log-time  { color: #444; flex-shrink: 0; }
.log-level { flex-shrink: 0; font-weight: 600; white-space: pre; }
.log-name  { color: #555; flex-shrink: 0; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-msg   { color: #ccc; flex: 1; }

.level-debug   .log-level { color: #555; }
.level-debug   .log-msg   { color: #555; }
.level-info    .log-level { color: #1890ff; }
.level-warning .log-level { color: #faad14; }
.level-warning .log-msg   { color: #faad14; }
.level-error   .log-level { color: #ff4d4f; }
.level-error   .log-msg   { color: #ff4d4f; }
.level-critical .log-level { color: #ff4d4f; }
.level-critical .log-msg   { color: #ff4d4f; }

.log-empty { color: #333; text-align: center; padding: 40px 0; font-size: 12px; }

.log-ctrl-btn {
  background: transparent !important;
  border-color: #303030 !important;
  color: #888 !important;
  font-size: 12px;
}
.log-ctrl-btn:hover { color: #ccc !important; border-color: #555 !important; }
.btn-active {
  color: #1890ff !important;
  border-color: #1890ff !important;
}

:deep(.log-highlight) {
  background: #b8860b;
  color: #fff;
  border-radius: 2px;
  padding: 0 1px;
}
</style>
