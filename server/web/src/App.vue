<template>
  <a-config-provider :theme="darkTheme">
    <a-layout class="app-layout">
      <!-- Toolbar -->
      <a-layout-header class="app-header">
        <Toolbar
          :save-status="saveStatus"
          @undo="graphEditor?.undo()"
          @redo="graphEditor?.redo()"
          @open-projects="projectGroupDrawerOpen = true"
          @open-clients="clientsDrawerOpen = true"
          @open-models="aiModelsDrawerOpen = true"
          @open-logs="logsDrawerOpen = true"
          @open-help="helpDrawerOpen = true"
        />
      </a-layout-header>

      <!-- Main body: full height -->
      <a-layout class="app-body">
        <!-- Left sider: scripts + node palette -->
        <a-layout-sider class="left-sider" :width="190" theme="dark">
          <a-tabs v-model:activeKey="leftTabKey" size="small" class="left-tabs">
            <a-tab-pane key="scripts" tab="脚本">
              <ScriptSidebar @script-selected="onScriptSelected" />
            </a-tab-pane>
            <a-tab-pane key="nodes" tab="节点">
              <NodePalette @drag-start="onDragStart" />
            </a-tab-pane>
          </a-tabs>
        </a-layout-sider>

        <!-- Center: graph canvas -->
        <a-layout-content class="graph-area">
          <div v-if="!scriptStore.currentScript" class="empty-canvas">
            <div class="empty-hint">
              <FileAddOutlined class="empty-icon" />
              <div class="empty-text">选择或新建一个脚本开始编辑</div>
            </div>
          </div>
          <GraphEditor
            v-else
            ref="graphEditor"
            @node-selected="onNodeSelected"
            @edge-selected="onEdgeSelected"
            @selection-cleared="selectedNode = null"
            @graph-changed="triggerAutoSave"
            @node-context-menu="onNodeContextMenu"
          />
        </a-layout-content>

        <!-- Right: property panel — only visible when node selected -->
        <transition name="slide-right">
          <div v-if="selectedNode" class="right-sider">
            <PropertyPanel
              :selected-node="selectedNode"
              :graph-cells="graphCells"
              @update="onNodeDataUpdate"
              @close="selectedNode = null"
            />
          </div>
        </transition>
      </a-layout>
    </a-layout>

    <!-- Node right-click context menu -->
    <div
      v-if="ctxMenu.visible"
      class="node-ctx-menu"
      :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
    >
      <div
        v-if="ctxMenu.data?.type === 'script' && ctxMenu.data?.script_id"
        class="ctx-menu-item"
        @click="ctxMenuOpen"
      >打开</div>
      <div v-else class="ctx-menu-item ctx-menu-disabled">打开（未绑定脚本）</div>
    </div>

    <ProjectGroupDrawer :open="projectGroupDrawerOpen" @close="projectGroupDrawerOpen = false" />
    <ClientsDrawer :open="clientsDrawerOpen" @close="clientsDrawerOpen = false" />
    <AIModelsDrawer :open="aiModelsDrawerOpen" @close="aiModelsDrawerOpen = false" />
    <LogsDrawer :open="logsDrawerOpen" @close="logsDrawerOpen = false" />
    <HelpDrawer :open="helpDrawerOpen" @close="helpDrawerOpen = false" />
  </a-config-provider>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { theme } from 'ant-design-vue'
import { FileAddOutlined } from '@ant-design/icons-vue'
import GraphEditor from './components/GraphEditor.vue'
import NodePalette from './components/NodePalette.vue'
import PropertyPanel from './components/PropertyPanel.vue'
import ScriptSidebar from './components/ScriptSidebar.vue'
import Toolbar from './components/Toolbar.vue'
import ClientsDrawer from './components/ClientsDrawer.vue'
import ProjectGroupDrawer from './components/ProjectGroupDrawer.vue'
import AIModelsDrawer from './components/AIModelsDrawer.vue'
import LogsDrawer from './components/LogsDrawer.vue'
import HelpDrawer from './components/HelpDrawer.vue'
import { useScriptStore } from './stores/scriptStore'
import { useProjectStore } from './stores/projectStore'
import { useClientStore } from './stores/clientStore'
import { uiWS } from './services/websocket'

const darkTheme = { algorithm: theme.darkAlgorithm }

const scriptStore = useScriptStore()
const projectStore = useProjectStore()
const clientStore = useClientStore()
const graphEditor = ref<InstanceType<typeof GraphEditor>>()
const selectedNode = ref<{ id: string; data: any } | null>(null)
const graphCells = ref<any[]>([])
const clientsDrawerOpen = ref(false)
const projectGroupDrawerOpen = ref(false)
const aiModelsDrawerOpen = ref(false)
const logsDrawerOpen = ref(false)
const helpDrawerOpen = ref(false)
const leftTabKey = ref('scripts')
const saveStatus = ref<'saving' | 'saved' | ''>('')

let saveTimer: ReturnType<typeof setTimeout> | null = null

function refreshGraphCells() {
  graphCells.value = graphEditor.value?.getJSON()?.cells ?? []
}

function triggerAutoSave() {
  if (!scriptStore.currentScript) return
  refreshGraphCells()
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    saveStatus.value = 'saving'
    const json = graphEditor.value?.getJSON()
    if (json) await scriptStore.saveScript(json)
    saveStatus.value = 'saved'
    setTimeout(() => { if (saveStatus.value === 'saved') saveStatus.value = '' }, 2000)
  }, 800)
}

onMounted(() => {
  uiWS.connect()
  clientStore.fetchClients()
  document.addEventListener('click', closeCtxMenu)
  document.addEventListener('contextmenu', closeCtxMenu)
})

async function onScriptSelected(id: string) {
  const script = await scriptStore.selectScript(id)
  try {
    const flow = JSON.parse(script.flow_json || '{"cells":[]}')
    graphEditor.value?.loadJSON(flow)
  } catch {
    graphEditor.value?.loadJSON({ cells: [] })
  }
  leftTabKey.value = 'nodes'
  if (script.project_id) {
    projectStore.fetchMarkers(script.project_id)
  }
}

function onDragStart(shape: string, defaultData: object, event: MouseEvent) {
  graphEditor.value?.startDragNode(shape, defaultData, event)
}

function onNodeSelected(node: { id: string; data: any }) {
  selectedNode.value = node
  refreshGraphCells()
}

function onEdgeSelected() {
  selectedNode.value = null
}

const ctxMenu = reactive({ visible: false, x: 0, y: 0, data: null as any })

function onNodeContextMenu(payload: { id: string; data: any; clientX: number; clientY: number }) {
  if (payload.data?.type !== 'script') return
  ctxMenu.data = payload.data
  ctxMenu.x = payload.clientX
  ctxMenu.y = payload.clientY
  ctxMenu.visible = true
}

function closeCtxMenu() { ctxMenu.visible = false }

async function ctxMenuOpen() {
  closeCtxMenu()
  if (ctxMenu.data?.script_id) {
    await onScriptSelected(ctxMenu.data.script_id)
    leftTabKey.value = 'scripts'
  }
}

function onNodeDataUpdate(nodeId: string, data: any) {
  if (!nodeId) return
  graphEditor.value?.updateNodeData(nodeId, data)
  triggerAutoSave()
  refreshGraphCells()
}

</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #app { height: 100%; background: #141414; }

.app-layout { height: 100vh; overflow: hidden; background: #141414 !important; }
.app-header { padding: 0 !important; height: 48px !important; line-height: 48px !important; background: #1a1a1a !important; }
.app-body { height: calc(100vh - 48px); overflow: hidden; background: #141414; }
.left-sider { border-right: 1px solid #222 !important; overflow: hidden; background: #161616 !important; }
.left-tabs { height: 100%; }
.left-tabs .ant-tabs-nav { padding: 0 6px; background: #161616; }
.left-tabs .ant-tabs-content-holder { height: calc(100% - 38px); overflow: hidden; }
.left-tabs .ant-tabs-content { height: 100%; }
.left-tabs .ant-tabs-tabpane { height: 100%; overflow: hidden; }
.graph-area { overflow: hidden; position: relative; background: #1a1a1a; }

.right-sider {
  width: 340px;
  flex-shrink: 0;
  border-left: 1px solid #222;
  overflow: hidden;
  background: #1a1a1a;
}

/* Node context menu */
.node-ctx-menu {
  position: fixed;
  z-index: 9999;
  min-width: 120px;
  background: #252525;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  padding: 4px 0;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}
.ctx-menu-item {
  padding: 7px 16px;
  font-size: 13px;
  color: #d0d0d0;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.12s;
}
.ctx-menu-item:hover { background: #1890ff22; color: #4dabf7; }
.ctx-menu-disabled { color: #555 !important; cursor: default; }
.ctx-menu-disabled:hover { background: none !important; }

/* Empty canvas */
.empty-canvas {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a1a;
}
.empty-hint { text-align: center; }
.empty-icon { font-size: 40px; color: #2a2a2a; display: block; }
.empty-text { font-size: 13px; color: #3a3a3a; margin-top: 14px; }

/* Right panel slide transition */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: width 0.22s ease, opacity 0.22s ease;
  overflow: hidden;
}
.slide-right-enter-from,
.slide-right-leave-to {
  width: 0 !important;
  opacity: 0;
}
</style>
