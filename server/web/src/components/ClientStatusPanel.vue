<template>
  <div class="client-panel">
    <div class="panel-header" @click="emit('toggle')">
      <div class="header-left">
        <span class="panel-title">客户端 & 日志</span>
        <span v-if="clientStore.clients.length > 0" class="client-count">
          {{ clientStore.connectedIds.size }}/{{ clientStore.clients.length }}
        </span>
        <span v-if="executionStore.anyRunning()" class="running-badge">运行中</span>
      </div>
      <a-button type="text" size="small" class="toggle-btn">
        <DownOutlined v-if="!collapsed" />
        <UpOutlined v-else />
      </a-button>
    </div>

    <div v-if="!collapsed" class="panel-content">
      <div class="clients-row">
        <div v-if="clientStore.clients.length === 0" class="empty-text">暂无客户端</div>
        <div v-for="c in clientStore.clients" :key="c.id" class="client-chip">
          <span class="chip-dot" :class="`dot-${c.status}`" />
          <span class="chip-name">{{ c.name }}</span>
          <span class="chip-status">{{ statusText(c.status) }}</span>
        </div>
        <a-button type="text" size="small" class="refresh-btn" @click.stop="refresh">
          <ReloadOutlined />
        </a-button>
      </div>

      <div class="log-box" ref="logBoxEl">
        <div v-for="(line, i) in executionStore.logs" :key="i" class="log-line">{{ line }}</div>
        <div v-if="!executionStore.logs.length" class="log-empty">等待执行...</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { UpOutlined, DownOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useClientStore } from '@/stores/clientStore'
import { useExecutionStore } from '@/stores/executionStore'

defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ (e: 'toggle'): void }>()

const clientStore = useClientStore()
const executionStore = useExecutionStore()
const logBoxEl = ref<HTMLElement>()

onMounted(() => clientStore.fetchClients())

function refresh() { clientStore.fetchClients() }

function statusText(s: string) {
  return { idle: '空闲', running: '运行中', disconnected: '离线', timeout: '超时' }[s] ?? s
}

watch(() => executionStore.logs.length, async () => {
  await nextTick()
  if (logBoxEl.value) logBoxEl.value.scrollTop = logBoxEl.value.scrollHeight
})
</script>

<style scoped>
.client-panel { display: flex; flex-direction: column; height: 100%; background: #1a1a1a; }
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  height: 36px;
  border-bottom: 1px solid #252525;
  cursor: pointer;
  flex-shrink: 0;
  user-select: none;
}
.panel-header:hover { background: #1f1f1f; }
.header-left { display: flex; align-items: center; gap: 8px; }
.panel-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 1px; }
.client-count { font-size: 10px; color: #444; background: #252525; padding: 1px 6px; border-radius: 10px; }
.running-badge { font-size: 10px; color: #1890ff; background: #111d2c; padding: 1px 6px; border-radius: 10px; border: 1px solid #1890ff33; }
.toggle-btn { color: #444 !important; padding: 0 4px !important; height: 22px !important; }
.panel-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 6px 10px 8px; gap: 6px; }
.clients-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 26px; }
.client-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  background: #252525;
  border: 1px solid #2e2e2e;
  border-radius: 4px;
  font-size: 11px;
}
.chip-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dot-idle         { background: #52c41a; }
.dot-running      { background: #1890ff; box-shadow: 0 0 4px #1890ff; }
.dot-disconnected { background: #ff4d4f; }
.dot-timeout      { background: #faad14; }
.chip-name { color: #aaa; font-weight: 500; }
.chip-status { color: #555; }
.refresh-btn { color: #444 !important; padding: 0 4px !important; height: 22px !important; margin-left: auto; }
.refresh-btn:hover { color: #888 !important; }
.empty-text { font-size: 11px; color: #3a3a3a; }
.log-box { flex: 1; overflow-y: auto; background: #111; border: 1px solid #252525; border-radius: 4px; padding: 6px 8px; font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; }
.log-line { color: #7ec87e; line-height: 1.7; white-space: pre-wrap; word-break: break-all; }
.log-empty { color: #333; font-size: 11px; }
</style>
