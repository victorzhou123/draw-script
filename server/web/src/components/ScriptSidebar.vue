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
        <a-button
          type="text"
          size="small"
          danger
          class="delete-btn"
          @click.stop="onDelete(script.id)"
        >✕</a-button>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useScriptStore } from '@/stores/scriptStore'
import { message, Modal } from 'ant-design-vue'

const emit = defineEmits<{
  (e: 'scriptSelected', id: string): void
}>()

const scriptStore = useScriptStore()

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

function formatDate(d: string) {
  return new Date(d).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
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
.script-item {
  position: relative;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  border: 1px solid #303030;
  background: #262626;
  cursor: pointer;
  transition: all 0.15s;
}
.script-item:hover { border-color: #1890ff; background: #111d2c; }
.script-item.active { border-color: #1890ff; background: #111d2c; font-weight: 600; }
.script-name { font-size: 13px; color: #d0d0d0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.script-meta { font-size: 11px; color: #555; margin-top: 2px; }
.delete-btn { position: absolute; right: 4px; top: 4px; opacity: 0; transition: opacity 0.15s; }
.script-item:hover .delete-btn { opacity: 1; }
</style>
