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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, provide } from 'vue'
import { ApartmentOutlined, CloseOutlined } from '@ant-design/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import { useScriptStore } from '@/stores/scriptStore'
import { useModelStore } from '@/stores/modelStore'
import { analyzeContextAtNode, analyzeContextEvolution } from '@/utils/contextAnalysis'
import { FORM_CTX } from './node-forms/useFormContext'
import ActionForm from './node-forms/ActionForm.vue'
import VisionForm from './node-forms/VisionForm.vue'
import ConditionForm from './node-forms/ConditionForm.vue'
import LoopForm from './node-forms/LoopForm.vue'
import DelayForm from './node-forms/DelayForm.vue'
import HttpForm from './node-forms/HttpForm.vue'
import WebhookForm from './node-forms/WebhookForm.vue'
import StartForm from './node-forms/StartForm.vue'
import EndForm from './node-forms/EndForm.vue'
import ScriptForm from './node-forms/ScriptForm.vue'
import ComputeForm from './node-forms/ComputeForm.vue'

const FORM_MAP: Record<string, any> = {
  action: ActionForm, vision: VisionForm, condition: ConditionForm,
  loop: LoopForm, delay: DelayForm, http: HttpForm, webhook: WebhookForm,
  start: StartForm, end: EndForm, script: ScriptForm, compute: ComputeForm,
}

const props = defineProps<{
  selectedNode: { id: string; data: any } | null
  graphCells: any[]
}>()

const emit = defineEmits<{
  (e: 'update', nodeId: string, data: any): void
  (e: 'close'): void
}>()

const localData = ref<any>({})
const editingNodeId = ref<string>('')

const projectStore = useProjectStore()
const scriptStore = useScriptStore()
const modelStore = useModelStore()

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

const aiModels = computed(() => modelStore.enabledAIModels)
const otherScripts = computed(() => scriptStore.scripts.filter(s => s.id !== scriptStore.currentScript?.id))

const nodeType = computed(() => localData.value.type || '')
const nodeLabel = computed(() => {
  const map: Record<string, string> = {
    start: 'Start', end: 'End', action: 'Action', screenshot: 'Screenshot',
    vision: 'Vision', condition: 'Condition', delay: 'Delay', loop: 'Loop',
    http: 'HTTP', webhook: 'Webhook', compute: 'Compute', script: 'Script',
  }
  return map[nodeType.value] || nodeType.value
})

const formComponent = computed(() => FORM_MAP[nodeType.value] ?? null)

provide(FORM_CTX, {
  localData,
  contextFields,
  availableMarkers,
  availableTemplates,
  aiModels,
  otherScripts,
  emitUpdate,
})

watch(() => scriptStore.currentScript?.project_id, (pid) => {
  if (pid) { projectStore.fetchMarkers(pid); projectStore.fetchTemplates(pid) }
}, { immediate: true })

watch(() => localData.value.vision_type, (vt) => {
  if (vt === 'ai_vision') modelStore.fetchModels()
}, { immediate: true })

watch(() => props.selectedNode, (node) => {
  if (!node) return
  editingNodeId.value = node.id
  const d = JSON.parse(JSON.stringify({
    label: node.data.label || '',
    type: node.data.type || '',
    action_type: node.data.action_type || 'mouse_click',
    vision_type: node.data.vision_type || 'template_match',
    result_var: node.data.result_var || '',
    condition_type: node.data.condition_type || 'vision_found',
    params: node.data.params || {},
    range_marker: node.data.range_marker || '',
    found_value: node.data.found_value ?? '',
    not_found_value: node.data.not_found_value ?? 'None',
    fields: node.data.fields || [],
    return_fields: node.data.return_fields || [],
    known_fields: node.data.known_fields || [],
    code: node.data.code || '',
    output_fields: node.data.output_fields || [],
    script_id: node.data.script_id || '',
    post_process: node.data.post_process || [],
  }))
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
</script>

<style scoped>
.property-panel { height: 100%; display: flex; flex-direction: column; background: #1a1a1a; }
.panel-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px 8px; border-bottom: 1px solid #252525; flex-shrink: 0; }
.panel-title { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 1px; }
.close-btn { color: #444 !important; padding: 0 4px !important; height: 22px !important; }
.close-btn:hover { color: #888 !important; }
.panel-body { flex: 1; overflow-y: auto; padding: 12px; }
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
.badge-webhook    { color: #eb2f96; border-color: #eb2f96; background: #291321; }
.badge-compute    { color: #36cfc9; border-color: #36cfc9; background: #112123; }
.badge-script     { color: #b37feb; border-color: #9254de; background: #1a0a2e; }
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
</style>
