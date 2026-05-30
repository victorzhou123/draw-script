<template>
  <div class="toolbar">
    <div class="toolbar-brand">
      <span class="brand-name">Draw<span class="brand-accent">Script</span></span>
      <span v-if="scriptStore.currentScript" class="script-chip">
        <FileTextOutlined />
        {{ scriptStore.currentScript.name }}
      </span>
    </div>

    <div class="toolbar-divider" />

    <div class="toolbar-group">
      <a-tooltip title="撤销 (Ctrl+Z)">
        <a-button size="small" class="tool-btn" @click="emit('undo')">
          <UndoOutlined /> 撤销
        </a-button>
      </a-tooltip>
      <a-tooltip title="重做 (Ctrl+Y)">
        <a-button size="small" class="tool-btn" @click="emit('redo')">
          <RedoOutlined /> 重做
        </a-button>
      </a-tooltip>
    </div>

    <div class="toolbar-spacer" />

    <transition name="fade">
      <span v-if="saveStatus === 'saving'" class="save-status saving">
        <LoadingOutlined spin /> 保存中…
      </span>
      <span v-else-if="saveStatus === 'saved'" class="save-status saved">
        <CheckOutlined /> 已保存
      </span>
    </transition>

    <div class="toolbar-group">
      <a-tooltip title="项目组管理">
        <a-button size="small" class="tool-btn" @click="emit('openProjects')">
          <FolderOutlined /> 项目组
        </a-button>
      </a-tooltip>
      <a-tooltip title="客户端管理">
        <a-button size="small" class="tool-btn" @click="emit('openClients')">
          <LaptopOutlined />
          客户端
          <span v-if="connectedCount > 0" class="client-badge">{{ connectedCount }}</span>
        </a-button>
      </a-tooltip>
      <a-tooltip title="AI 模型管理">
        <a-button size="small" class="tool-btn ai-btn" @click="emit('openModels')">
          <RobotOutlined /> AI 模型
        </a-button>
      </a-tooltip>
      <div class="toolbar-divider" />
      <a-tooltip title="使用帮助">
        <a-button size="small" class="tool-btn help-btn" @click="emit('openHelp')">
          <QuestionCircleOutlined /> 帮助
        </a-button>
      </a-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  UndoOutlined, RedoOutlined, LoadingOutlined, CheckOutlined,
  FileTextOutlined, LaptopOutlined, FolderOutlined, QuestionCircleOutlined, RobotOutlined,
} from '@ant-design/icons-vue'
import { useScriptStore } from '@/stores/scriptStore'
import { useClientStore } from '@/stores/clientStore'

defineProps<{
  saveStatus: 'saving' | 'saved' | ''
}>()

const emit = defineEmits<{
  (e: 'undo'): void
  (e: 'redo'): void
  (e: 'openProjects'): void
  (e: 'openClients'): void
  (e: 'openModels'): void
  (e: 'openHelp'): void
}>()

const scriptStore = useScriptStore()
const clientStore = useClientStore()

const connectedCount = computed(() => clientStore.connectedIds.size)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0 12px;
  height: 48px;
  background: #1a1a1a;
  border-bottom: 1px solid #252525;
}
.toolbar-brand { display: flex; align-items: center; gap: 10px; min-width: 0; margin-right: 4px; }
.brand-name { font-size: 15px; font-weight: 700; color: #e0e0e0; letter-spacing: -0.3px; white-space: nowrap; }
.brand-accent { color: #1890ff; }
.script-chip {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; color: #555;
  background: #252525; border: 1px solid #2e2e2e; border-radius: 4px;
  padding: 2px 8px; max-width: 180px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.toolbar-divider { width: 1px; height: 20px; background: #2a2a2a; margin: 0 8px; flex-shrink: 0; }
.toolbar-group { display: flex; align-items: center; gap: 4px; }
.toolbar-spacer { flex: 1; }
.tool-btn {
  background: transparent !important; border-color: transparent !important;
  color: #888 !important; font-size: 12px; padding: 0 8px;
  display: flex; align-items: center; gap: 4px;
}
.tool-btn:hover { color: #ccc !important; background: #252525 !important; }
.client-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 16px; height: 16px; background: #52c41a; color: #000;
  font-size: 10px; font-weight: 700; border-radius: 8px; padding: 0 4px; margin-left: 2px;
}
.save-status {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; margin-right: 8px;
}
.save-status.saving { color: #888; }
.save-status.saved  { color: #52c41a; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.help-btn { color: #597ef7 !important; }
.help-btn:hover { color: #85a5ff !important; background: #1f2a4a !important; }
.ai-btn { color: #9254de !important; }
.ai-btn:hover { color: #b37feb !important; background: #1a0a2e !important; }
</style>
