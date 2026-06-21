<template>
  <div class="property-panel">
    <div class="panel-header">
      <span class="panel-title"><ApartmentOutlined /> 节点属性</span>
      <a-button type="text" size="small" class="close-btn" @click="emit('close')">
        <CloseOutlined />
      </a-button>
    </div>

    <div class="panel-body">
      <div class="node-type-badge" :class="`badge-${nodeType}`">{{ nodeLabel }}</div>

      <a-tabs v-model:activeKey="activeTab" size="small">
        <a-tab-pane key="props" tab="属性">
          <a-form layout="vertical" size="small" class="prop-form">
            <a-form-item label="节点标签">
              <a-input v-model:value="localData.label" @change="emitUpdate()" />
            </a-form-item>

            <component :is="formComponent" v-if="formComponent" />
          </a-form>

          <!-- Context 演变时间线 -->
          <template v-if="evolutionSteps.length > 0">
            <a-divider style="margin: 14px 0 10px; border-color: #2a2a2a;" />
            <div class="section-title" style="margin-top:0">
              Context 追踪
              <span class="ctx-legend">
                <span class="ctx-dot certain" />确定
                <span class="ctx-dot conditional" style="margin-left:8px" />条件分支
              </span>
            </div>
            <div class="evo-list">
              <div v-for="step in evolutionSteps" :key="step.nodeId" class="evo-step">
                <span class="evo-node-badge" :class="`badge-${step.nodeType}`">{{ step.nodeLabel }}</span>
                <div class="evo-fields">
                  <span v-for="f in step.addedFields" :key="f.name" class="evo-field-tag" :class="f.certain ? 'certain' : 'conditional'">
                    {{ f.name }}
                  </span>
                </div>
              </div>
            </div>
          </template>
        </a-tab-pane>

        <a-tab-pane key="debug" tab="调试">
          <div class="section-title" style="margin-top:0">调试</div>
          <div class="debug-actions">
            <a-button size="small" class="debug-btn" @click="emit('debugExecute', editingNodeId)">执行</a-button>
            <a-button size="small" class="debug-btn" @click="emit('debugRunTo', editingNodeId)">执行到此</a-button>
          </div>

          <a-divider style="margin: 14px 0 10px; border-color: #2a2a2a;" />

          <div class="section-title">Context</div>
          <template v-if="!ctxBefore && !ctxAfter">
            <div class="empty-hint">暂无记录（运行一次后显示）</div>
          </template>
          <template v-else>
            <!-- 执行前 -->
            <div class="ctx-phase-label">执行前</div>
            <template v-if="ctxBefore && Object.keys(ctxBefore).length > 0">
              <div class="ctx-kv-list">
                <div v-for="[k, v] in Object.entries(ctxBefore)" :key="k" class="ctx-kv-entry">
                  <div class="ctx-kv-row" :class="{'ctx-kv-row-top': !isComplex(v) && expandedPrimKeys.has('before:' + k)}">
                    <span class="ctx-kv-key" :title="k" @click="handleKeyClick('before', k)">{{ k }}</span>
                    <span v-if="!isComplex(v)"
                          class="ctx-kv-val ctx-prim-val"
                          :class="[valTypeClass(v), { 'ctx-prim-expanded': expandedPrimKeys.has('before:' + k) }]"
                          @click="handlePrimValClick('before', k, v)">{{ formatPrimitive(v) }}</span>
                    <span v-else class="ctx-kv-val ctx-obj-val" @click="toggleCtxKey('before', k)">
                      <span :class="valTypeClass(v)">{{ formatSummary(v) }}</span>
                      <span class="ctx-chevron">{{ expandedCtxKeys.has('before:' + k) ? '▼' : '▶' }}</span>
                    </span>
                  </div>
                  <pre v-if="isComplex(v) && expandedCtxKeys.has('before:' + k)" class="ctx-expanded-json">{{ JSON.stringify(v, null, 2) }}</pre>
                </div>
              </div>
            </template>
            <div v-else class="empty-hint" style="padding-left:4px">（空）</div>

            <!-- 执行后 -->
            <div class="ctx-phase-label" style="margin-top:10px">执行后</div>
            <template v-if="ctxAfter && Object.keys(ctxAfter).length > 0">
              <div class="ctx-kv-list">
                <div v-for="[k, v] in Object.entries(ctxAfter)" :key="k" class="ctx-kv-entry">
                  <div class="ctx-kv-row" :class="{'ctx-kv-row-top': !isComplex(v) && expandedPrimKeys.has('after:' + k)}">
                    <span class="ctx-kv-key" :title="k" @click="handleKeyClick('after', k)">{{ k }}</span>
                    <span v-if="!isComplex(v)"
                          class="ctx-kv-val ctx-prim-val"
                          :class="[valTypeClass(v), { 'ctx-prim-expanded': expandedPrimKeys.has('after:' + k) }]"
                          @click="handlePrimValClick('after', k, v)">{{ formatPrimitive(v) }}</span>
                    <span v-else class="ctx-kv-val ctx-obj-val" @click="toggleCtxKey('after', k)">
                      <span :class="valTypeClass(v)">{{ formatSummary(v) }}</span>
                      <span class="ctx-chevron">{{ expandedCtxKeys.has('after:' + k) ? '▼' : '▶' }}</span>
                    </span>
                  </div>
                  <pre v-if="isComplex(v) && expandedCtxKeys.has('after:' + k)" class="ctx-expanded-json">{{ JSON.stringify(v, null, 2) }}</pre>
                </div>
              </div>
            </template>
            <div v-else-if="!ctxAfter" class="empty-hint" style="padding-left:4px">（运行中…）</div>
            <div v-else class="empty-hint" style="padding-left:4px">（空）</div>
          </template>

          <a-divider style="margin: 14px 0 10px; border-color: #2a2a2a;" />

          <div class="section-title">节点动作</div>
          <div v-if="nodeActions.length === 0" class="empty-hint">暂无记录（运行一次脚本后会显示这个节点做了什么）</div>
          <div v-else class="log-list">
            <div v-for="(line, idx) in nodeActions" :key="idx" class="log-line action-line">{{ line }}</div>
          </div>

          <a-divider style="margin: 14px 0 10px; border-color: #2a2a2a;" />

          <div class="section-title">日志</div>
          <div v-if="nodeLogs.length === 0" class="empty-hint">暂无错误/日志</div>
          <div v-else class="log-list">
            <div v-for="(line, idx) in nodeLogs" :key="idx" class="log-line error-line">{{ line }}</div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, provide } from 'vue'
import { message } from 'ant-design-vue'
import { ApartmentOutlined, CloseOutlined } from '@ant-design/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import { useScriptStore } from '@/stores/scriptStore'
import { useModelStore } from '@/stores/modelStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useServiceKeyStore } from '@/stores/serviceKeyStore'
import { analyzeContextAtNode, analyzeContextEvolution } from '@/utils/contextAnalysis'
import { FORM_CTX } from './node-forms/useFormContext'
import ActionForm from './node-forms/ActionForm.vue'
import VisionForm from './node-forms/VisionForm.vue'
import ConditionForm from './node-forms/ConditionForm.vue'
import LoopForm from './node-forms/LoopForm.vue'
import DelayForm from './node-forms/DelayForm.vue'
import HttpForm from './node-forms/HttpForm.vue'
import StartForm from './node-forms/StartForm.vue'
import EndForm from './node-forms/EndForm.vue'
import ScriptForm from './node-forms/ScriptForm.vue'
import ComputeForm from './node-forms/ComputeForm.vue'
import ScreenshotForm from './node-forms/ScreenshotForm.vue'
import GlobalVarForm from './node-forms/GlobalVarForm.vue'
import ContextEditForm from './node-forms/ContextEditForm.vue'
import WaitForm from './node-forms/WaitForm.vue'
import CrawlForm from './node-forms/CrawlForm.vue'

const FORM_MAP: Record<string, any> = {
  action: ActionForm, vision: VisionForm, condition: ConditionForm,
  loop: LoopForm, delay: DelayForm, http: HttpForm,
  start: StartForm, end: EndForm, script: ScriptForm, compute: ComputeForm,
  screenshot: ScreenshotForm, 'global-var': GlobalVarForm,
  'context-edit': ContextEditForm, wait: WaitForm, crawl: CrawlForm,
}

const props = defineProps<{
  selectedNode: { id: string; data: any } | null
  graphCells: any[]
}>()

const emit = defineEmits<{
  (e: 'update', nodeId: string, data: any): void
  (e: 'close'): void
  (e: 'debugExecute', nodeId: string): void
  (e: 'debugRunTo', nodeId: string): void
}>()

const localData = ref<any>({})
const editingNodeId = ref<string>('')
const activeTab = ref<'props' | 'debug'>('props')

const projectStore = useProjectStore()
const scriptStore = useScriptStore()
const modelStore = useModelStore()
const executionStore = useExecutionStore()
const serviceKeyStore = useServiceKeyStore()

const nodeActions = computed(() => executionStore.nodeActionsFor(editingNodeId.value))
const nodeLogs = computed(() => executionStore.nodeLogsFor(editingNodeId.value))
const ctxBefore = computed(() => executionStore.nodeContextBeforeFor(editingNodeId.value))
const ctxAfter = computed(() => executionStore.nodeContextAfterFor(editingNodeId.value))

const expandedCtxKeys = ref(new Set<string>())
const expandedPrimKeys = ref(new Set<string>())

function toggleCtxKey(phase: string, key: string) {
  const k = `${phase}:${key}`
  const next = new Set(expandedCtxKeys.value)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  expandedCtxKeys.value = next
}

function copyText(text: string) {
  const succeed = () => message.success('已复制', 1.5)
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(succeed).catch(() => fallbackCopy(text))
  } else {
    fallbackCopy(text)
  }
}

function fallbackCopy(text: string) {
  const el = document.createElement('textarea')
  el.value = text
  el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
  document.body.appendChild(el)
  el.select()
  try { document.execCommand('copy'); message.success('已复制', 1.5) } catch { message.error('复制失败') }
  document.body.removeChild(el)
}

function handleKeyClick(phase: string, key: string) {
  copyText(key)
}

function handlePrimValClick(phase: string, key: string, v: any) {
  const k = `${phase}:${key}`
  if (expandedPrimKeys.value.has(k)) {
    copyText(v === null || v === undefined ? 'null' : String(v))
  } else {
    const next = new Set(expandedPrimKeys.value)
    next.add(k)
    expandedPrimKeys.value = next
  }
}

function isComplex(v: any): boolean {
  return v !== null && typeof v === 'object'
}

function formatPrimitive(v: any): string {
  if (v === null || v === undefined) return 'null'
  if (typeof v === 'string') return `"${v}"`
  return String(v)
}

function valTypeClass(v: any): string {
  if (v === null || v === undefined) return 'ctx-null'
  if (typeof v === 'string') return 'ctx-string'
  if (typeof v === 'number') return 'ctx-number'
  if (typeof v === 'boolean') return 'ctx-bool'
  return 'ctx-obj'
}

function formatSummary(v: any): string {
  if (Array.isArray(v)) return `[ ${v.length} 项 ]`
  if (typeof v === 'object' && v !== null) return `{ ${Object.keys(v).length} 个键 }`
  return String(v)
}

const contextFields = computed(() => {
  const id = props.selectedNode?.id
  if (!id) return []
  return analyzeContextAtNode(props.graphCells, id)
})

const evolutionSteps = computed(() => {
  const id = props.selectedNode?.id
  if (!id) return []
  return analyzeContextEvolution(props.graphCells, id)
})

const availableMarkers = computed(() => {
  const pid = scriptStore.currentScript?.project_id
  if (!pid) return []
  return projectStore.markers[pid] ?? []
})

const availableTemplates = computed(() => {
  const pid = scriptStore.currentScript?.project_id
  if (!pid) return []
  return projectStore.templates[pid] ?? []
})

const availableGlobalVars = computed(() => {
  const pid = scriptStore.currentScript?.project_id
  if (!pid) return []
  return (projectStore.globalVars[pid] ?? []).map(v => v.name)
})

const aiModels = computed(() => modelStore.enabledAIModels)
const otherScripts = computed(() => scriptStore.scripts.filter(s => s.id !== scriptStore.currentScript?.id))
const serviceKeys = computed(() => serviceKeyStore.keys)

const nodeType = computed(() => localData.value.type || '')
const nodeLabel = computed(() => {
  const map: Record<string, string> = {
    start: 'Start', end: 'End', action: 'Action', screenshot: 'Screenshot',
    vision: 'Vision', condition: 'Condition', delay: 'Delay', loop: 'Loop',
    http: 'HTTP', compute: 'Compute', script: 'Script',
    'global-var': 'Global Var',
    'context-edit': 'Context Edit',
    wait: 'Wait', crawl: 'Crawl',
  }
  return map[nodeType.value] || nodeType.value
})

const formComponent = computed(() => FORM_MAP[nodeType.value] ?? null)

provide(FORM_CTX, {
  localData,
  nodeId: editingNodeId,
  contextFields,
  availableMarkers,
  availableTemplates,
  aiModels,
  otherScripts,
  availableGlobalVars,
  serviceKeys,
  emitUpdate,
})

watch(() => scriptStore.currentScript?.project_id, (pid) => {
  if (pid) {
    projectStore.fetchMarkers(pid)
    projectStore.fetchTemplates(pid)
    projectStore.fetchGlobalVars(pid)
  }
}, { immediate: true })

watch(() => localData.value.vision_type, (vt) => {
  if (vt === 'ai_vision') modelStore.fetchModels()
}, { immediate: true })

watch(() => localData.value.type, (t) => {
  if (t === 'crawl') serviceKeyStore.fetchKeys()
}, { immediate: true })

watch(() => props.selectedNode, (node) => {
  if (!node) return
  editingNodeId.value = node.id
  activeTab.value = 'props'
  expandedCtxKeys.value = new Set()
  expandedPrimKeys.value = new Set()
  const d = JSON.parse(JSON.stringify({
    label: node.data.label || '',
    type: node.data.type || '',
    action_type: node.data.action_type || 'mouse_click',
    vision_type: node.data.vision_type || 'template_match',
    result_var: node.data.result_var || '',
    condition_type: node.data.condition_type || '',
    operator: node.data.operator || 'and',
    conditions: node.data.conditions || [],
    params: node.data.params || {},
    range_marker: node.data.range_marker || '',
    found_value: node.data.found_value ?? '',
    not_found_value: node.data.not_found_value ?? 'None',
    found_value_type: node.data.found_value_type || '',
    not_found_value_type: node.data.not_found_value_type || '',
    value_type: node.data.value_type || '',
    ocr_not_found_value: node.data.ocr_not_found_value ?? '',
    ocr_not_found_value_type: node.data.ocr_not_found_value_type || '',
    fields: node.data.fields || [],
    return_fields: node.data.return_fields || [],
    known_fields: node.data.known_fields || [],
    return_field_descriptions: node.data.return_field_descriptions || {},
    code: node.data.code || '',
    output_fields: node.data.output_fields || [],
    script_id: node.data.script_id || '',
    post_process: node.data.post_process || [],
    input_mappings: node.data.input_mappings || [],
    output_mappings: node.data.output_mappings || [],
    crawl_engine: node.data.crawl_engine || 'native',
    output_var: node.data.output_var || '',
  }))
  // Normalize condition node: migrate old single-condition to new multi-condition format
  if (d.type === 'condition') {
    if (!Array.isArray(d.conditions) || d.conditions.length === 0) {
      const oldType = d.condition_type
      if (oldType === 'variable_compare' || oldType === 'boolean_check') {
        d.conditions = [{ condition_type: oldType, params: d.params || {} }]
      } else {
        d.conditions = []
      }
    }
    d.operator = d.operator || 'and'
  }
  // Normalize legacy keyboard_press → keyboard_hotkey
  if (d.action_type === 'keyboard_press') {
    d.action_type = 'keyboard_hotkey'
    d.params.keys = d.params.key || ''
    delete d.params.key
  }
  // End node: auto-add newly seen context fields
  if (d.type === 'end') {
    const known = new Set<string>(d.known_fields)
    const added = contextFields.value.map(f => f.name).filter(n => !known.has(n))
    if (added.length > 0) { d.return_fields.push(...added); d.known_fields.push(...added) }
    localData.value = d
    if (added.length > 0) emitUpdate()
  } else {
    localData.value = d
  }
}, { immediate: true })

function emitUpdate() {
  emit('update', editingNodeId.value, JSON.parse(JSON.stringify(localData.value)))
}

defineExpose({ setActiveTab: (tab: 'props' | 'debug') => { activeTab.value = tab } })
</script>

<style scoped>
.property-panel { height: 100%; display: flex; flex-direction: column; background: #1a1a1a; }
.panel-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px 8px; border-bottom: 1px solid #252525; flex-shrink: 0; }
.panel-title { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 1px; }
.close-btn { color: #444 !important; padding: 0 4px !important; height: 22px !important; }
.close-btn:hover { color: #888 !important; }
.panel-body { flex: 1; overflow-y: auto; padding: 12px; }
.empty-hint { font-size: 11px; color: #444; padding: 4px 0; }
.log-list { display: flex; flex-direction: column; gap: 4px; }
.log-line {
  font-size: 11px; font-family: 'Consolas', monospace; line-height: 1.5;
  padding: 4px 8px; border-radius: 4px; word-break: break-all; white-space: pre-wrap;
}
.log-line.action-line { color: #888; background: #1f1f1f; }
.log-line.error-line  { color: #ff7875; background: #2a1215; }
.node-type-badge { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 4px; margin-bottom: 14px; border: 1px solid; }
.badge-start      { color: #52c41a; border-color: #52c41a; background: #162312; }
.badge-end        { color: #ff4d4f; border-color: #ff4d4f; background: #2a1215; }
.badge-action     { color: #1890ff; border-color: #1890ff; background: #111d2c; }
.badge-screenshot { color: #a0d911; border-color: #a0d911; background: #1d2c00; }
.badge-vision     { color: #9254de; border-color: #722ed1; background: #1a0a2e; }
.badge-condition  { color: #faad14; border-color: #faad14; background: #2b2111; }
.badge-delay      { color: #fa8c16; border-color: #fa8c16; background: #2b1d11; }
.badge-loop       { color: #597ef7; border-color: #2f54eb; background: #131629; }
.badge-http       { color: #13c2c2; border-color: #13c2c2; background: #112123; }
.badge-compute    { color: #36cfc9; border-color: #36cfc9; background: #112123; }
.badge-script     { color: #b37feb; border-color: #9254de; background: #1a0a2e; }
.badge-global-var  { color: #40a9ff; border-color: #1890ff; background: #0d2340; }
.badge-context-edit { color: #eb2f96; border-color: #eb2f96; background: #1a0a14; }
.badge-wait        { color: #2db7f5; border-color: #2db7f5; background: #0d1f2b; }
.badge-crawl       { color: #52c41a; border-color: #389e0d; background: #0d1a0a; }
.prop-form :deep(.ant-form-item) { margin-bottom: 12px; }
.prop-form :deep(.ant-form-item-label > label) { font-size: 11px; color: #666; }
.section-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.8px; margin: 14px 0 6px; display: flex; align-items: center; gap: 6px; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; flex-shrink: 0; }
.ctx-dot.certain { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
.ctx-legend { font-size: 10px; color: #555; font-weight: 400; margin-left: 8px; display: inline-flex; align-items: center; gap: 4px; text-transform: none; letter-spacing: 0; }
.evo-list { display: flex; flex-direction: column; gap: 8px; margin-top: 4px; }
.evo-step { display: flex; flex-direction: column; gap: 4px; }
.evo-node-badge { display: inline-block; font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: 3px; border: 1px solid; align-self: flex-start; }
.evo-fields { display: flex; flex-wrap: wrap; gap: 4px; padding-left: 6px; }
.evo-field-tag { font-size: 11px; font-family: 'Consolas', monospace; padding: 1px 7px; border-radius: 10px; }
.evo-field-tag.certain { background: #162312; color: #52c41a; border: 1px solid #274916; }
.evo-field-tag.conditional { background: #2b2111; color: #faad14; border: 1px solid #3f2e00; }
.debug-actions { display: flex; gap: 8px; margin-bottom: 4px; }
.debug-btn { background: #252525 !important; border-color: #3a3a3a !important; color: #aaa !important; font-size: 12px !important; }
.debug-btn:hover { border-color: #1890ff !important; color: #4dabf7 !important; }

/* Context section */
.ctx-phase-label {
  font-size: 10px; font-weight: 600; color: #3a3a3a;
  text-transform: uppercase; letter-spacing: 0.6px;
  margin: 6px 0 4px; padding-bottom: 3px;
  border-bottom: 1px solid #252525;
}
.ctx-kv-list { display: flex; flex-direction: column; gap: 1px; }
.ctx-kv-entry { display: flex; flex-direction: column; }
.ctx-kv-row {
  display: flex; align-items: baseline; gap: 8px;
  padding: 2px 0; min-height: 20px;
}
.ctx-kv-key {
  font-size: 11px; font-family: 'Consolas', monospace;
  color: #666; flex-shrink: 0;
  min-width: 50px; max-width: 110px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  cursor: pointer;
}
.ctx-kv-key:hover { color: #888; }
.ctx-kv-row-top { align-items: flex-start !important; }
.ctx-kv-val {
  font-size: 11px; font-family: 'Consolas', monospace;
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ctx-prim-val { cursor: pointer; }
.ctx-prim-val:hover { opacity: 0.8; }
.ctx-prim-expanded {
  white-space: pre-wrap !important;
  word-break: break-all;
  overflow: visible !important;
  text-overflow: unset !important;
  max-height: 115px;
  overflow-y: auto !important;
  display: block;
}
.ctx-obj-val { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.ctx-obj-val:hover { opacity: 0.8; }
.ctx-chevron { font-size: 9px; color: #555; flex-shrink: 0; }
.ctx-string  { color: #5cdbd3; }
.ctx-number  { color: #69c0ff; }
.ctx-bool    { color: #ffd666; }
.ctx-null    { color: #555; }
.ctx-obj     { color: #d3adf7; }
.ctx-expanded-json {
  font-size: 10px; font-family: 'Consolas', monospace;
  color: #888; background: #141414;
  border-radius: 4px; padding: 6px 8px;
  margin: 2px 0 4px 8px;
  max-height: 120px; overflow: auto;
  white-space: pre; border: 1px solid #252525;
  line-height: 1.5;
}
</style>
