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
                    <!-- Preview button -->
                    <a-tooltip :title="capturePreviewClientId ? '预览标注' : '请先选择预览客户端'">
                      <a-button
                        type="text" size="small" class="icon-btn preview-marker-btn"
                        :disabled="!capturePreviewClientId"
                        @click.stop="openMarkerPreview(m.name)"
                      >
                        <EyeOutlined />
                      </a-button>
                    </a-tooltip>
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

                <!-- ── 预览 / 窗口管理 ── -->
                <div class="ops-section">
                  <div class="ops-section-header">
                    <EyeOutlined class="ops-icon" />
                    <span>预览 / 窗口</span>
                  </div>
                  <div class="ops-row">
                    <span class="ops-label">预览客户端</span>
                    <a-select
                      v-model:value="capturePreviewClientId"
                      size="small"
                      placeholder="选择客户端"
                      style="flex:1;min-width:0"
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
                  <div class="ops-row" style="gap:6px">
                    <a-tooltip title="还原窗口到标注时的位置和大小">
                      <a-button
                        size="small" class="icon-btn window-ctrl-btn"
                        :disabled="!capturePreviewClientId"
                        :loading="restoringWindow"
                        @click="restoreWindow"
                      >还原窗口</a-button>
                    </a-tooltip>
                    <a-tooltip title="在客户端调整窗口大小，标注坐标自动按比例缩放">
                      <a-button
                        size="small" class="icon-btn resize-window-btn"
                        :disabled="!capturePreviewClientId"
                        :loading="resizingWindow"
                        @click="resizeWindowInteractive"
                      >自定义大小</a-button>
                    </a-tooltip>
                  </div>
                </div>

                <!-- ── 发送标注 ── -->
                <div class="ops-section">
                  <div class="ops-section-header">
                    <div style="display:flex;align-items:center;gap:6px;flex:1">
                      <SendOutlined class="ops-icon" />
                      <span>发送标注</span>
                    </div>
                    <a-checkbox
                      :indeterminate="sendIndeterminate"
                      :checked="sendAllChecked"
                      @change="toggleSelectAll"
                      style="font-size:11px;color:#555"
                    >全选</a-checkbox>
                  </div>
                  <div v-if="projectClientIds.length === 0" class="empty-hint" style="margin:0">暂无客户端</div>
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
                    type="primary" size="small" block style="margin-top:6px"
                    :loading="sending"
                    :disabled="sendClientIds.length === 0 || selectedMarkerNames.size === 0"
                    @click="sendMarkersToClients"
                  >
                    <SendOutlined /> 发送选中 {{ selectedMarkerNames.size }} 个标记到 {{ sendClientIds.length }} 个客户端
                  </a-button>
                  <div v-if="sendResult" class="send-result" :class="sendResult.ok ? 'ok' : 'err'">{{ sendResult.text }}</div>
                </div>

                <!-- ── 复制标注数据 ── -->
                <div class="ops-section">
                  <div class="ops-section-header">
                    <CopyOutlined class="ops-icon" />
                    <span>复制标注数据</span>
                  </div>
                  <div class="ops-row">
                    <span class="ops-label">来源</span>
                    <a-select
                      v-model:value="copySourceClientId"
                      size="small"
                      placeholder="选择来源客户端"
                      style="flex:1;min-width:0"
                      allow-clear
                      :options="projectClientIds.map(cid => ({ label: clientName(cid), value: cid }))"
                    />
                  </div>
                  <div class="ops-row">
                    <span class="ops-label">目标</span>
                    <a-select
                      v-model:value="copyTargetClientIds"
                      mode="multiple"
                      size="small"
                      placeholder="选择目标客户端（可多选）"
                      style="flex:1;min-width:0"
                      :options="copyTargetOptions"
                      :max-tag-count="2"
                    />
                  </div>
                  <div class="ops-row">
                    <span class="ops-label">模式</span>
                    <a-radio-group v-model:value="copyMode" size="small" button-style="solid">
                      <a-radio-button value="overwrite">覆盖已有</a-radio-button>
                      <a-radio-button value="fill_missing">仅补充缺失</a-radio-button>
                    </a-radio-group>
                  </div>
                  <a-button
                    type="primary" size="small" block style="margin-top:6px"
                    :loading="copying"
                    :disabled="!copySourceClientId || copyTargetClientIds.length === 0"
                    @click="copyCaptures"
                  >
                    <CopyOutlined /> 复制到 {{ copyTargetClientIds.length }} 个客户端
                  </a-button>
                  <div v-if="copyResult" class="send-result" :class="copyResult.ok ? 'ok' : 'err'">{{ copyResult.text }}</div>
                </div>
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
                  <a-upload
                    :show-upload-list="false"
                    accept="image/*"
                    :before-upload="(f: File) => { handleTemplateImageUpdate(t.id, f); return false }"
                  >
                    <a-tooltip title="点击替换图片" placement="right">
                      <div class="template-thumb-wrap">
                        <img :src="templateImageUrl(t.id)" class="template-thumb" />
                        <div v-if="updatingTemplateId === t.id" class="template-thumb-overlay">
                          <a-spin size="small" />
                        </div>
                        <div v-else class="template-thumb-hover">替换</div>
                      </div>
                    </a-tooltip>
                  </a-upload>
                  <template v-if="renamingTemplateId === t.id">
                    <a-input
                      v-model:value="renameTemplateValue"
                      size="small"
                      style="flex:1"
                      @press-enter="confirmTemplateRename(t.id)"
                      @blur="confirmTemplateRename(t.id)"
                      autofocus
                    />
                  </template>
                  <template v-else>
                    <span class="member-name">{{ t.name }}</span>
                    <a-button type="text" size="small" class="icon-btn" @click="startTemplateRename(t)">
                      <EditOutlined />
                    </a-button>
                  </template>
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

    <!-- 标注预览 Modal -->
    <a-modal
      v-model:open="previewOpen"
      :title="`标注预览 — ${previewFocusMarker}`"
      :width="900"
      :footer="null"
      :body-style="{ padding: '12px', background: '#141414' }"
    >
      <div v-if="previewLoading" style="text-align:center;padding:40px">
        <a-spin tip="获取截图中..." />
      </div>
      <template v-else-if="previewScreenshot">
        <div class="annotation-preview-wrapper">
          <img
            ref="previewImgRef"
            :src="'data:image/png;base64,' + previewScreenshot"
            class="annotation-preview-img"
            @load="onPreviewImgLoad"
          />
          <!-- Captured point markers -->
          <template v-for="m in previewMarkerData" :key="m.name">
            <div
              v-if="m.captured && m.type === 'point' && m.x !== null"
              class="overlay-point"
              :class="{ focused: m.name === previewFocusMarker }"
              :style="pointOverlayStyle(m)"
            >
              <span class="overlay-label">{{ m.name }}</span>
            </div>
            <div
              v-else-if="m.captured && m.type === 'box' && m.x !== null && m.w && m.h"
              class="overlay-box"
              :class="{ focused: m.name === previewFocusMarker }"
              :style="boxOverlayStyle(m)"
            >
              <span class="overlay-label">{{ m.name }}</span>
            </div>
          </template>
        </div>
        <!-- Uncaptured markers legend -->
        <div v-if="previewMarkerData.some(m => !m.captured)" class="uncaptured-legend">
          <span class="uncaptured-legend-title">未标注：</span>
          <span
            v-for="m in previewMarkerData.filter(m => !m.captured)"
            :key="m.name"
            class="uncaptured-badge"
          >{{ m.name }}</span>
        </div>
      </template>
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
  InfoCircleOutlined, EyeOutlined, CopyOutlined,
} from '@ant-design/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import { useClientStore } from '@/stores/clientStore'
import { useScriptStore } from '@/stores/scriptStore'
import { api } from '@/services/api'
import type { Project, MarkerCapture, MarkerCaptureData } from '@/services/api'

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
const restoringWindow = ref(false)
const resizingWindow = ref(false)
// Copy captures between clients
const copySourceClientId = ref<string | null>(null)
const copyTargetClientIds = ref<string[]>([])
const copyMode = ref<'overwrite' | 'fill_missing'>('overwrite')
const copying = ref(false)
const copyResult = ref<{ ok: boolean; text: string } | null>(null)
const markerCaptureMap = ref<Record<string, boolean>>({})  // name → captured
const selectedMarkerNames = ref<Set<string>>(new Set())
const refreshingCaptures = ref(false)

// Marker preview
const previewOpen = ref(false)
const previewLoading = ref(false)
const previewFocusMarker = ref('')
const previewScreenshot = ref<string | null>(null)
const previewMarkerData = ref<MarkerCaptureData[]>([])
const previewImgNaturalWidth = ref(1)
const previewImgNaturalHeight = ref(1)
const previewImgRef = ref<HTMLImageElement | null>(null)

// Scripts tab
const addScriptId = ref<string | null>(null)

// Templates tab
const newTemplateName = ref('')
const uploadingTemplate = ref(false)
const renamingTemplateId = ref<string | null>(null)
const renameTemplateValue = ref('')
const updatingTemplateId = ref<string | null>(null)
const imageTimestamps = ref<Record<string, number>>({})

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
  const base = api.templateImageUrl(selectedId.value!, templateId)
  const ts = imageTimestamps.value[templateId]
  return ts ? `${base}?t=${ts}` : base
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

async function restoreWindow() {
  if (!capturePreviewClientId.value || !selectedId.value) return
  restoringWindow.value = true
  try {
    await api.restoreWindow(selectedId.value, capturePreviewClientId.value)
    message.success('已发送还原窗口指令')
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '还原失败')
  } finally {
    restoringWindow.value = false
  }
}

async function resizeWindowInteractive() {
  if (!capturePreviewClientId.value || !selectedId.value) return
  resizingWindow.value = true
  try {
    await api.resizeWindowInteractive(selectedId.value, capturePreviewClientId.value)
    message.info('已发送指令，请在客户端调整窗口大小后确认')
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '发送失败')
  } finally {
    resizingWindow.value = false
  }
}

const copyTargetOptions = computed(() =>
  projectClientIds.value
    .filter(cid => cid !== copySourceClientId.value)
    .map(cid => ({ label: clientName(cid), value: cid }))
)

async function copyCaptures() {
  if (!copySourceClientId.value || copyTargetClientIds.value.length === 0 || !selectedId.value) return
  copying.value = true
  copyResult.value = null
  try {
    const res = await api.copyCapturesBetweenClients(
      selectedId.value,
      copySourceClientId.value,
      copyTargetClientIds.value,
      copyMode.value,
    )
    copyResult.value = { ok: true, text: `已复制 ${res.copied} 条标注数据到 ${copyTargetClientIds.value.length} 个客户端` }
  } catch (e: any) {
    copyResult.value = { ok: false, text: e?.response?.data?.detail ?? '复制失败' }
  } finally {
    copying.value = false
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
  copyResult.value = null
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
  wait: '等待', script: '子脚本',
}

interface MarkerUsage { scriptName: string; nodeLabel: string; nodeType: string }

function getMarkerUsages(markerName: string): MarkerUsage[] {
  const usages: MarkerUsage[] = []
  const scripts = scriptStore.scripts.filter(s => s.project_id === selectedId.value)
  for (const script of scripts) {
    try {
      const flow = JSON.parse(script.flow_json || '{}')
      for (const node of (flow.cells ?? []).filter((c: any) => c.shape?.startsWith('node-'))) {
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

async function openMarkerPreview(markerName: string) {
  if (!capturePreviewClientId.value || !selectedId.value) {
    message.warning('请先选择预览客户端')
    return
  }
  previewFocusMarker.value = markerName
  previewScreenshot.value = null
  previewMarkerData.value = []
  previewImgNaturalWidth.value = 1
  previewImgNaturalHeight.value = 1
  previewOpen.value = true
  previewLoading.value = true
  try {
    const [screenshot, markerData] = await Promise.all([
      api.captureClientScreenshot(capturePreviewClientId.value),
      api.getMarkerCaptureData(selectedId.value, capturePreviewClientId.value),
    ])
    previewScreenshot.value = screenshot
    previewMarkerData.value = markerData
  } catch (e: any) {
    message.error(e?.response?.data?.detail ?? '获取预览失败')
    previewOpen.value = false
  } finally {
    previewLoading.value = false
  }
}

function onPreviewImgLoad() {
  if (previewImgRef.value) {
    previewImgNaturalWidth.value = previewImgRef.value.naturalWidth || 1
    previewImgNaturalHeight.value = previewImgRef.value.naturalHeight || 1
  }
}

function markerAbsX(m: MarkerCaptureData) {
  return (m.x ?? 0) + (m.window_x ?? 0)
}
function markerAbsY(m: MarkerCaptureData) {
  return (m.y ?? 0) + (m.window_y ?? 0)
}
function pointOverlayStyle(m: MarkerCaptureData) {
  return {
    left: `${markerAbsX(m) / previewImgNaturalWidth.value * 100}%`,
    top: `${markerAbsY(m) / previewImgNaturalHeight.value * 100}%`,
  }
}
function boxOverlayStyle(m: MarkerCaptureData) {
  return {
    left: `${markerAbsX(m) / previewImgNaturalWidth.value * 100}%`,
    top: `${markerAbsY(m) / previewImgNaturalHeight.value * 100}%`,
    width: `${(m.w ?? 0) / previewImgNaturalWidth.value * 100}%`,
    height: `${(m.h ?? 0) / previewImgNaturalHeight.value * 100}%`,
  }
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

async function handleTemplateImageUpdate(templateId: string, file: File) {
  if (!selectedId.value) return
  updatingTemplateId.value = templateId
  try {
    await projectStore.updateTemplateImage(selectedId.value, templateId, file)
    imageTimestamps.value[templateId] = Date.now()
    message.success('图片已更新')
  } catch {
    message.error('图片更新失败')
  } finally {
    updatingTemplateId.value = null
  }
}

function startTemplateRename(t: { id: string; name: string }) {
  renamingTemplateId.value = t.id
  renameTemplateValue.value = t.name
}

async function confirmTemplateRename(templateId: string) {
  if (!selectedId.value || !renameTemplateValue.value.trim()) return
  try {
    await projectStore.renameTemplate(selectedId.value, templateId, renameTemplateValue.value.trim())
    message.success('模板已重命名')
  } catch {
    message.error('重命名失败')
  } finally {
    renamingTemplateId.value = null
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
.template-thumb { width: 40px; height: 40px; object-fit: cover; border-radius: 3px; border: 1px solid #303030; flex-shrink: 0; display: block; }
.template-thumb-wrap { position: relative; width: 40px; height: 40px; flex-shrink: 0; cursor: pointer; }
.template-thumb-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.55); border-radius: 3px; display: flex; align-items: center; justify-content: center; }
.template-thumb-hover { position: absolute; inset: 0; background: rgba(0,0,0,0.55); border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 10px; color: #fff; opacity: 0; transition: opacity 0.15s; }
.template-thumb-wrap:hover .template-thumb-hover { opacity: 1; }

/* Marker list */
.marker-list-header { display: flex; align-items: center; justify-content: space-between; padding: 4px 2px 6px; }
.select-missing-btn { font-size: 11px; color: #888 !important; padding: 0 6px !important; height: 20px !important; }
.capture-badge { font-size: 10px; padding: 1px 6px; border-radius: 3px; flex-shrink: 0; }
.badge-ok { color: #52c41a; background: #162312; border: 1px solid #52c41a44; }
.badge-missing { color: #888; background: #222; border: 1px solid #333; }
.usage-info-btn { color: #444 !important; padding: 0 3px !important; height: 20px !important; flex-shrink: 0; }
.usage-info-btn:hover { color: #888 !important; }

/* Operation sections (markers tab) */
.ops-section {
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: #1e1e1e;
}
.ops-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 10px;
}
.ops-icon { font-size: 11px; }
.ops-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.ops-row:last-child { margin-bottom: 0; }
.ops-label { font-size: 11px; color: #555; flex-shrink: 0; width: 30px; }
.window-ctrl-btn { color: #888 !important; }
.resize-window-btn { color: #fa8c16 !important; border-color: transparent !important; }
.resize-window-btn:hover:not(:disabled) { color: #ffa940 !important; background: #2b1b07 !important; }
.send-client-row { padding: 4px 0; }
.send-result { margin-top: 8px; font-size: 12px; padding: 5px 10px; border-radius: 4px; }
.send-result.ok  { color: #52c41a; background: #162312; border: 1px solid #52c41a33; }
.send-result.err { color: #ff4d4f; background: #2a1215; border: 1px solid #ff4d4f33; }

/* Marker preview button */
.preview-marker-btn { color: #444 !important; padding: 0 3px !important; height: 20px !important; flex-shrink: 0; }
.preview-marker-btn:hover:not(:disabled) { color: #1890ff !important; }

/* Annotation preview modal */
.annotation-preview-wrapper { position: relative; display: block; width: 100%; line-height: 0; }
.annotation-preview-img { width: 100%; display: block; }

.overlay-point {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #1890ff;
  background: rgba(24, 144, 255, 0.25);
  transform: translate(-50%, -50%);
  pointer-events: none;
}
.overlay-point.focused {
  border-color: #faad14;
  background: rgba(250, 173, 20, 0.35);
  width: 16px;
  height: 16px;
  z-index: 10;
}
.overlay-box {
  position: absolute;
  border: 2px solid #52c41a;
  background: rgba(82, 196, 26, 0.08);
  pointer-events: none;
}
.overlay-box.focused {
  border-color: #faad14;
  background: rgba(250, 173, 20, 0.12);
  z-index: 10;
}
.overlay-label {
  position: absolute;
  top: -16px;
  left: 0;
  font-size: 10px;
  color: #fff;
  background: rgba(24, 144, 255, 0.85);
  padding: 0 4px;
  border-radius: 2px;
  white-space: nowrap;
  line-height: 14px;
}
.overlay-point.focused .overlay-label,
.overlay-box.focused .overlay-label { background: rgba(250, 173, 20, 0.95); color: #000; }
.overlay-box .overlay-label { top: -18px; }

.uncaptured-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 6px 8px;
  background: #1f1215;
  border: 1px solid #ff4d4f33;
  border-radius: 4px;
}
.uncaptured-legend-title { font-size: 11px; color: #ff4d4f; flex-shrink: 0; }
.uncaptured-badge {
  font-size: 10px;
  color: #ff4d4f;
  background: #2a1215;
  border: 1px solid #ff4d4f44;
  padding: 1px 6px;
  border-radius: 3px;
}
</style>

<style>
.marker-usage-popover .ant-popover-inner { background: #1e1e1e; border: 1px solid #2a2a2a; }
.marker-usage-popover .ant-popover-title { border-bottom: 1px solid #2a2a2a; padding: 6px 12px; }
.marker-usage-popover .ant-popover-inner-content { padding: 8px 12px; }
.marker-usage-popover .ant-popover-arrow::before { background: #1e1e1e; }
</style>
