<template>
  <div class="property-panel">
    <div class="panel-header">
      <span class="panel-title">
        <ApartmentOutlined /> 节点属性
      </span>
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

        <!-- Action -->
        <template v-if="nodeType === 'action'">
          <a-form-item label="操作类型">
            <a-select v-model:value="localData.action_type" @change="emitUpdate()">
              <a-select-option value="mouse_click">鼠标点击</a-select-option>
              <a-select-option value="mouse_move">鼠标移动</a-select-option>
              <a-select-option value="mouse_drag">鼠标拖拽</a-select-option>
              <a-select-option value="keyboard_type">键盘输入</a-select-option>
              <a-select-option value="keyboard_hotkey">按键 / 快捷键</a-select-option>
              <a-select-option value="mouse_scroll">滚轮</a-select-option>
            </a-select>
          </a-form-item>
          <template v-if="['mouse_click','mouse_move'].includes(localData.action_type)">
            <!-- Coord source selector -->
            <a-form-item label="坐标来源">
              <a-radio-group
                v-model:value="coordSource"
                size="small"
                button-style="solid"
                @change="onCoordSourceChange"
              >
                <a-radio-button value="fixed">固定坐标</a-radio-button>
                <a-radio-button value="marker">标记</a-radio-button>
                <a-radio-button value="context">Context</a-radio-button>
              </a-radio-group>
            </a-form-item>

            <!-- Fixed coords -->
            <template v-if="coordSource === 'fixed'">
              <a-form-item label="X">
                <a-input-number
                  v-model:value="localData.params.x"
                  :style="{ width: '100%' }"
                  placeholder="0"
                  @change="emitUpdate()"
                />
              </a-form-item>
              <a-form-item label="Y">
                <a-input-number
                  v-model:value="localData.params.y"
                  :style="{ width: '100%' }"
                  placeholder="0"
                  @change="emitUpdate()"
                />
              </a-form-item>
            </template>

            <!-- Marker picker -->
            <template v-else-if="coordSource === 'marker'">
              <a-form-item label="选择标记">
                <div class="marker-select-row">
                  <a-select
                    v-model:value="currentMarkerName"
                    :style="{ flex: 1 }"
                    placeholder="选择标记点"
                    allow-clear
                    @change="onMarkerSelect"
                  >
                    <a-select-option v-for="m in availableMarkers" :key="m.name" :value="m.name">
                      <span class="marker-menu-type" :class="`type-${m.type}`">
                        {{ m.type === 'point' ? '点' : '框' }}
                      </span>
                      {{ m.name }}
                    </a-select-option>
                  </a-select>
                </div>
              </a-form-item>
              <div v-if="!availableMarkers.length" class="hint-text" style="margin-top:-6px">
                当前项目暂无标记，请先在项目中添加标记
              </div>
            </template>

            <!-- Context variable picker -->
            <template v-else-if="coordSource === 'context'">
              <a-form-item label="Context 变量">
                <a-select
                  v-model:value="contextVarSelected"
                  :style="{ width: '100%' }"
                  placeholder="选择变量"
                  allow-clear
                  @change="onContextVarSelect"
                >
                  <a-select-option v-for="f in contextFields" :key="f.name" :value="f.name">
                    <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
                    {{ f.name }}
                    <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
                  </a-select-option>
                </a-select>
              </a-form-item>
              <div v-if="!contextFields.length" class="hint-text" style="margin-top:-6px">
                当前节点上游暂无 context 变量
              </div>
            </template>
            <a-form-item v-if="localData.action_type === 'mouse_click'" label="按键">
              <a-select v-model:value="localData.params.button" @change="emitUpdate()">
                <a-select-option value="left">左键</a-select-option>
                <a-select-option value="right">右键</a-select-option>
                <a-select-option value="middle">中键</a-select-option>
              </a-select>
            </a-form-item>
          </template>
          <template v-if="localData.action_type === 'keyboard_type'">
            <a-form-item label="文字来源">
              <a-radio-group
                v-model:value="textSource"
                size="small"
                button-style="solid"
                @change="onTextSourceChange"
              >
                <a-radio-button value="manual">手动输入</a-radio-button>
                <a-radio-button value="context">Context</a-radio-button>
              </a-radio-group>
            </a-form-item>
            <template v-if="textSource === 'manual'">
              <a-form-item label="文字内容">
                <a-textarea v-model:value="localData.params.text" :rows="3" @change="emitUpdate()" />
              </a-form-item>
            </template>
            <template v-else-if="textSource === 'context'">
              <a-form-item label="Context 变量">
                <a-select
                  v-model:value="textContextVar"
                  :style="{ width: '100%' }"
                  placeholder="选择变量"
                  allow-clear
                  @change="onTextContextVarSelect"
                >
                  <a-select-option v-for="f in contextFields" :key="f.name" :value="f.name">
                    <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
                    {{ f.name }}
                    <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
                  </a-select-option>
                </a-select>
              </a-form-item>
              <div v-if="!contextFields.length" class="hint-text" style="margin-top:-6px">
                当前节点上游暂无 context 变量
              </div>
            </template>
          </template>
          <template v-if="localData.action_type === 'keyboard_hotkey'">
            <a-form-item label="按键 / 快捷键">
              <div
                class="key-capture"
                :class="{ recording: isRecordingKey }"
                tabindex="0"
                @focus="isRecordingKey = true"
                @blur="isRecordingKey = false"
                @keydown.prevent="onCaptureKeyDown"
              >
                <span v-if="isRecordingKey" class="key-hint">请按下按键…</span>
                <span v-else-if="localData.params.keys" class="key-value">{{ localData.params.keys }}</span>
                <span v-else class="key-placeholder">点击后按下按键</span>
                <CloseCircleOutlined
                  v-if="localData.params.keys && !isRecordingKey"
                  class="key-clear"
                  @mousedown.prevent="clearKey"
                />
              </div>
            </a-form-item>
          </template>
        </template>

        <!-- Vision -->
        <template v-if="nodeType === 'vision'">
          <a-form-item label="识别类型">
            <a-radio-group v-model:value="localData.vision_type" @change="emitUpdate()">
              <a-radio value="template_match">模板匹配</a-radio>
              <a-radio value="ocr">OCR文字</a-radio>
              <a-radio value="ai_vision">AI视觉</a-radio>
              <a-radio value="color_detect">颜色检测</a-radio>
            </a-radio-group>
          </a-form-item>

          <!-- Detection range (all types) -->
          <a-form-item label="检测范围">
            <a-select
              v-model:value="localData.range_marker"
              :style="{ width: '100%' }"
              placeholder="选择方框标记作为识别区域"
              allow-clear
              @change="emitUpdate()"
            >
              <a-select-option v-for="m in availableMarkers" :key="m.name" :value="m.name">
                <span class="marker-menu-type" :class="`type-${m.type}`">
                  {{ m.type === 'point' ? '点' : '方框' }}
                </span>
                {{ m.name }}
              </a-select-option>
            </a-select>
            <div v-if="!availableMarkers.length" class="hint-text" style="margin-top:4px">
              当前项目暂无标记，请先在项目中添加方框类型标记
            </div>
          </a-form-item>

          <!-- Template match -->
          <template v-if="localData.vision_type === 'template_match'">
            <a-form-item label="模板">
              <a-select
                v-model:value="localData.params.template_id"
                :style="{ width: '100%' }"
                placeholder="选择项目模板"
                allow-clear
                @change="emitUpdate()"
              >
                <a-select-option v-for="t in availableTemplates" :key="t.id" :value="t.id">
                  {{ t.name }}
                </a-select-option>
              </a-select>
              <div v-if="!availableTemplates.length" class="hint-text" style="margin-top:4px">
                当前项目暂无模板，请先在项目组中上传
              </div>
            </a-form-item>
            <a-form-item label="相似度阈值">
              <a-slider v-model:value="localData.params.threshold" :min="0.5" :max="1.0" :step="0.05" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="结果存入">
              <a-input v-model:value="localData.result_var" placeholder="context 字段名" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="匹配成功时写入">
              <a-input v-model:value="localData.found_value" placeholder="留空则写入坐标 x,y" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="未匹配时写入">
              <a-input v-model:value="localData.not_found_value" placeholder="留空则写入 null" @change="emitUpdate()" />
            </a-form-item>
          </template>

          <!-- OCR -->
          <template v-if="localData.vision_type === 'ocr'">
            <a-form-item label="识别结果存入">
              <a-input v-model:value="localData.result_var" placeholder="context 字段名（存储全部识别文字）" @change="emitUpdate()" />
            </a-form-item>
          </template>

          <!-- AI Vision -->
          <template v-if="localData.vision_type === 'ai_vision'">
            <a-form-item label="提示词">
              <a-textarea v-model:value="localData.params.prompt" :rows="3" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="模式">
              <a-select v-model:value="localData.params.mode" @change="emitUpdate()">
                <a-select-option value="describe">描述内容</a-select-option>
                <a-select-option value="find">查找元素 (返回坐标)</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="localData.params.mode === 'find'">
              <a-form-item label="查找目标">
                <a-input v-model:value="localData.params.target" placeholder="例如：确定按钮" @change="emitUpdate()" />
              </a-form-item>
            </template>
            <a-form-item label="结果存入">
              <a-input v-model:value="localData.result_var" placeholder="context 字段名" @change="emitUpdate()" />
            </a-form-item>
          </template>

          <!-- Color detect -->
          <template v-if="localData.vision_type === 'color_detect'">
            <a-form-item label="颜色 (Hex)">
              <a-input v-model:value="localData.params.color" placeholder="#FF0000" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="容差">
              <a-input-number v-model:value="localData.params.tolerance" :min="0" :max="128" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="结果存入">
              <a-input v-model:value="localData.result_var" placeholder="context 字段名" @change="emitUpdate()" />
            </a-form-item>
          </template>
        </template>

        <!-- Condition -->
        <template v-if="nodeType === 'condition'">
          <a-form-item label="条件类型">
            <a-select v-model:value="localData.condition_type" @change="emitUpdate()">
              <a-select-option value="vision_found">识别是否找到</a-select-option>
              <a-select-option value="vision_text_contains">识别文字包含</a-select-option>
              <a-select-option value="variable_compare">变量比较</a-select-option>
              <a-select-option value="http_status">HTTP状态码</a-select-option>
            </a-select>
          </a-form-item>
          <template v-if="localData.condition_type === 'vision_text_contains'">
            <a-form-item label="包含文字">
              <a-input v-model:value="localData.params.value" @change="emitUpdate()" />
            </a-form-item>
          </template>
          <template v-if="localData.condition_type === 'variable_compare'">
            <a-form-item label="变量路径">
              <a-input v-model:value="localData.params.variable" placeholder="last_http_response.status_code" @change="emitUpdate()" />
            </a-form-item>
            <a-form-item label="运算符">
              <a-select v-model:value="localData.params.operator" @change="emitUpdate()">
                <a-select-option value="==">等于 (==)</a-select-option>
                <a-select-option value="!=">不等于 (!=)</a-select-option>
                <a-select-option value=">">大于 (&gt;)</a-select-option>
                <a-select-option value="<">小于 (&lt;)</a-select-option>
                <a-select-option value="contains">包含</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="期望值">
              <a-input v-model:value="localData.params.value" @change="emitUpdate()" />
            </a-form-item>
          </template>
        </template>

        <!-- Delay -->
        <template v-if="nodeType === 'delay'">
          <a-form-item label="秒数">
            <a-input-number v-model:value="localData.params.seconds" :min="0" :step="0.1" @change="emitUpdate()" />
          </a-form-item>
          <a-form-item label="毫秒 (额外)">
            <a-input-number v-model:value="localData.params.ms" :min="0" :step="100" @change="emitUpdate()" />
          </a-form-item>
        </template>

        <!-- Loop -->
        <template v-if="nodeType === 'loop'">
          <a-form-item label="循环次数">
            <a-input-number v-model:value="localData.params.count" :min="1" :max="1000" @change="emitUpdate()" />
          </a-form-item>
        </template>

        <!-- HTTP -->
        <template v-if="nodeType === 'http'">
          <a-form-item label="请求方法">
            <a-select v-model:value="localData.params.method" @change="emitUpdate()">
              <a-select-option value="GET">GET</a-select-option>
              <a-select-option value="POST">POST</a-select-option>
              <a-select-option value="PUT">PUT</a-select-option>
              <a-select-option value="DELETE">DELETE</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="URL">
            <a-input v-model:value="localData.params.url" placeholder="https://..." @change="emitUpdate()" />
          </a-form-item>
          <a-form-item label="请求体 (JSON)">
            <a-textarea v-model:value="localData.params.bodyText" :rows="4" placeholder='{"key": "value"}' @change="emitUpdate()" />
          </a-form-item>
        </template>

        <!-- Webhook -->
        <template v-if="nodeType === 'webhook'">
          <a-form-item label="Webhook 名称">
            <a-input v-model:value="localData.params.name" @change="emitUpdate()" />
          </a-form-item>
        </template>

        <!-- Start -->
        <template v-if="nodeType === 'start'">
          <div class="section-title">Context 字段定义</div>
          <div class="hint-text">API 调用时同名参数自动注入；否则使用默认值。</div>
          <div v-for="(field, idx) in localData.fields" :key="idx" class="field-row">
            <a-input v-model:value="field.name" placeholder="字段名" class="field-name"
              @change="emitUpdate()" />
            <a-select v-model:value="field.type" class="field-type" @change="emitUpdate()">
              <a-select-option value="any">any</a-select-option>
              <a-select-option value="str">str</a-select-option>
              <a-select-option value="int">int</a-select-option>
              <a-select-option value="float">float</a-select-option>
              <a-select-option value="bool">bool</a-select-option>
            </a-select>
            <a-input v-model:value="field.default" placeholder="默认值" class="field-default"
              @change="emitUpdate()" />
            <a-button type="text" size="small" danger @click="removeField(idx)">✕</a-button>
          </div>
          <a-button size="small" class="add-field-btn" @click="addField">+ 添加字段</a-button>
        </template>

        <!-- End -->
        <template v-if="nodeType === 'end'">
          <div class="section-title">返回字段</div>
          <div class="hint-text">新增的 context 字段会自动加入，手动删除的不会再自动添加。</div>
          <template v-if="localData.return_fields?.length">
            <div v-for="(f, idx) in localData.return_fields" :key="idx" class="return-field-row">
              <span class="ctx-dot certain" />
              <span style="flex:1; font-size:13px;">{{ f }}</span>
              <a-button type="text" size="small" danger @click="removeReturnField(idx)">✕</a-button>
            </div>
          </template>
          <div v-else class="hint-text">上游暂无 context 变量</div>
          <div class="return-field-row" style="margin-top:6px">
            <a-input
              v-model:value="newReturnField"
              placeholder="手动输入字段名"
              size="small"
              style="flex:1"
              @pressEnter="addReturnFieldManual"
            />
            <a-button size="small" @click="addReturnFieldManual">+</a-button>
          </div>
        </template>

        <!-- Script -->
        <template v-if="nodeType === 'script'">
          <a-form-item label="引用脚本">
            <a-select
              v-model:value="localData.script_id"
              :style="{ width: '100%' }"
              placeholder="选择要调用的脚本"
              allow-clear
              show-search
              option-filter-prop="label"
              @change="emitUpdate()"
            >
              <a-select-option
                v-for="s in otherScripts"
                :key="s.id"
                :value="s.id"
                :label="s.name"
              >
                {{ s.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <div class="hint-text">
            父脚本的 context 变量传入子脚本；子脚本 End 节点返回的字段合并回父脚本。
          </div>
        </template>

        <!-- Compute -->
        <template v-if="nodeType === 'compute'">
          <div class="section-title">Python 代码</div>
          <div class="hint-text">通过 <code>context</code> 字典读写 context 变量。</div>
          <a-form-item>
            <a-textarea
              v-model:value="localData.code"
              :rows="10"
              :style="{ fontFamily: 'Consolas, Monaco, monospace', fontSize: '12px' }"
              placeholder="# 例如：&#10;result = context['x'] * 2&#10;context['result'] = result"
              @change="onCodeChange"
            />
          </a-form-item>
          <div class="section-title">输出字段
            <a-button size="small" type="link" class="auto-detect-btn" @click="autoDetect">自动检测</a-button>
          </div>
          <div class="hint-text">标注此节点会写入 context 的字段名。</div>
          <div v-for="(f, idx) in localData.output_fields" :key="idx" class="return-field-row">
            <a-input v-model:value="localData.output_fields[idx]" placeholder="字段名"
              @change="emitUpdate()" />
            <a-button type="text" size="small" danger @click="removeOutputField(idx)">✕</a-button>
          </div>
          <a-button size="small" class="add-field-btn" @click="addOutputField">+ 添加字段</a-button>
        </template>
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
              <span
                v-for="f in step.addedFields"
                :key="f.name"
                class="evo-field-tag"
                :class="f.certain ? 'certain' : 'conditional'"
              >
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
import { ref, watch, computed } from 'vue'
import { ApartmentOutlined, CloseOutlined, CloseCircleOutlined } from '@ant-design/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import { useScriptStore } from '@/stores/scriptStore'
import { analyzeContextAtNode, analyzeContextEvolution } from '@/utils/contextAnalysis'

const props = defineProps<{
  selectedNode: { id: string; data: any } | null
  graphCells: any[]
}>()

const emit = defineEmits<{
  (e: 'update', nodeId: string, data: any): void
  (e: 'close'): void
}>()

const localData = ref<any>({})
const isRecordingKey = ref(false)
const coordSource = ref<'fixed' | 'marker' | 'context'>('fixed')
const contextVarSelected = ref<string | undefined>(undefined)
const textSource = ref<'manual' | 'context'>('manual')
const textContextVar = ref<string | undefined>(undefined)
const editingNodeId = ref<string>('')

const KEY_MAP: Record<string, string> = {
  ' ': 'space', Enter: 'enter', Backspace: 'backspace', Delete: 'delete',
  Escape: 'esc', Tab: 'tab',
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
  Home: 'home', End: 'end', PageUp: 'pageup', PageDown: 'pagedown',
  Insert: 'insert', Control: 'ctrl', Alt: 'alt', Shift: 'shift', Meta: 'win',
}

function onCaptureKeyDown(e: KeyboardEvent) {
  const mods: string[] = []
  if (e.ctrlKey)  mods.push('ctrl')
  if (e.altKey)   mods.push('alt')
  if (e.shiftKey) mods.push('shift')
  if (e.metaKey)  mods.push('win')
  const mainKey = KEY_MAP[e.key] ?? (e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase())
  if (['ctrl', 'alt', 'shift', 'win'].includes(mainKey)) return
  localData.value.params.keys = [...mods, mainKey].join('+')
  emitUpdate()
  isRecordingKey.value = false
}

function clearKey() {
  localData.value.params.keys = ''
  emitUpdate()
}

const projectStore = useProjectStore()
const scriptStore = useScriptStore()

// Context fields available at the current node (dataflow analysis)
const contextFields = computed(() => {
  const id = props.selectedNode?.id
  if (!id) return []
  return analyzeContextAtNode(props.graphCells, id)
})

// Context evolution: only upstream of the selected node
const evolutionSteps = computed(() => {
  const id = props.selectedNode?.id
  if (!id) return []
  return analyzeContextEvolution(props.graphCells, id)
})

// Scripts available for reference (exclude the current script to prevent self-reference)
const otherScripts = computed(() =>
  scriptStore.scripts.filter(s => s.id !== scriptStore.currentScript?.id)
)

// Markers available from the current script's project
const availableMarkers = computed(() => {
  const pid = scriptStore.currentScript?.project_id
  if (!pid) return []
  return projectStore.markers[pid] ?? []
})

// Auto-fetch markers whenever the project changes (no stale-cache guard)
watch(
  () => scriptStore.currentScript?.project_id,
  (pid) => {
    if (pid) {
      projectStore.fetchMarkers(pid)
      projectStore.fetchTemplates(pid)
    }
  },
  { immediate: true }
)

const availableTemplates = computed(() => {
  const pid = scriptStore.currentScript?.project_id
  if (!pid) return []
  return projectStore.templates[pid] ?? []
})

// Track which marker name is currently filling the coords
const currentMarkerName = ref<string | null>(null)

function onCoordSourceChange() {
  if (coordSource.value === 'fixed') {
    localData.value.params.coords = ''
    localData.value.params.x = ''
    localData.value.params.y = ''
    currentMarkerName.value = null
    contextVarSelected.value = undefined
  } else if (coordSource.value === 'marker') {
    localData.value.params.coords = ''
    localData.value.params.x = ''
    localData.value.params.y = ''
    contextVarSelected.value = undefined
  } else {
    localData.value.params.x = ''
    localData.value.params.y = ''
    localData.value.params.coords = ''
    currentMarkerName.value = null
  }
  emitUpdate()
}

function onTextSourceChange() {
  textContextVar.value = undefined
  localData.value.params.text = ''
  emitUpdate()
}

function onTextContextVarSelect(varName: string | undefined) {
  textContextVar.value = varName
  localData.value.params.text = varName ? `$${varName}` : ''
  emitUpdate()
}

function onMarkerSelect(name: string | undefined) {
  if (!name) {
    currentMarkerName.value = null
    localData.value.params.x = ''
    localData.value.params.y = ''
    emitUpdate()
    return
  }
  const marker = availableMarkers.value.find(m => m.name === name)
  if (!marker) return
  currentMarkerName.value = marker.name
  if (marker.type === 'point') {
    localData.value.params.x = `$markers.${marker.name}.x`
    localData.value.params.y = `$markers.${marker.name}.y`
  } else {
    localData.value.params.x = `$markers.${marker.name}.cx`
    localData.value.params.y = `$markers.${marker.name}.cy`
  }
  emitUpdate()
}

function onContextVarSelect(varName: string | undefined) {
  contextVarSelected.value = varName
  localData.value.params.coords = varName ? `$${varName}` : ''
  emitUpdate()
}

const nodeType = computed(() => localData.value.type || '')
const nodeLabel = computed(() => {
  const map: Record<string, string> = {
    start: 'Start', end: 'End', action: 'Action', screenshot: 'Screenshot',
    vision: 'Vision', condition: 'Condition', delay: 'Delay', loop: 'Loop',
    http: 'HTTP', webhook: 'Webhook', compute: 'Compute', script: 'Script',
  }
  return map[nodeType.value] || nodeType.value
})

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
    // vision
    range_marker: node.data.range_marker || '',
    found_value: node.data.found_value || '',
    not_found_value: node.data.not_found_value || '',
    // start
    fields: node.data.fields || [],
    // end
    return_fields: node.data.return_fields || [],
    known_fields: node.data.known_fields || [],
    // compute
    code: node.data.code || '',
    output_fields: node.data.output_fields || [],
    // script
    script_id: node.data.script_id || '',
  }))
  if (d.action_type === 'keyboard_press') {
    d.action_type = 'keyboard_hotkey'
    d.params.keys = d.params.key || ''
    delete d.params.key
  }
  if (d.type === 'end') {
    const known = new Set<string>(d.known_fields)
    const added = contextFields.value.map(f => f.name).filter(n => !known.has(n))
    if (added.length > 0) {
      d.return_fields.push(...added)
      d.known_fields.push(...added)
    }
    localData.value = d
    if (added.length > 0) emitUpdate()
  } else {
    localData.value = d
  }
  isRecordingKey.value = false

  // Derive coordSource from the new node's params right here, after localData is set,
  // so we always use the correct incoming data (not stale localData from the previous node).
  currentMarkerName.value = null
  const params = d.params || {}
  if (params.coords && String(params.coords).startsWith('$')) {
    coordSource.value = 'context'
    contextVarSelected.value = String(params.coords).slice(1)
  } else if (String(params.x || '').startsWith('$markers.')) {
    coordSource.value = 'marker'
    const m = String(params.x).match(/^\$markers\.([^.]+)/)
    currentMarkerName.value = m ? m[1] : null
    contextVarSelected.value = undefined
  } else {
    coordSource.value = 'fixed'
    contextVarSelected.value = undefined
  }

  // Derive textSource
  const textVal = String(params.text || '')
  if (textVal.startsWith('$')) {
    textSource.value = 'context'
    textContextVar.value = textVal.slice(1)
  } else {
    textSource.value = 'manual'
    textContextVar.value = undefined
  }
}, { immediate: true })

// Auto-add only genuinely new context fields to end node
watch(contextFields, (fields) => {
  if (nodeType.value !== 'end') return
  const known = new Set<string>(localData.value.known_fields ?? [])
  const added = fields.map(f => f.name).filter(n => !known.has(n))
  if (added.length === 0) return
  localData.value.return_fields = [...(localData.value.return_fields ?? []), ...added]
  localData.value.known_fields = [...(localData.value.known_fields ?? []), ...added]
  emitUpdate()
})

// start node helpers
function addField() {
  localData.value.fields.push({ name: '', type: 'any', default: '' })
  emitUpdate()
}
function removeField(idx: number) {
  localData.value.fields.splice(idx, 1)
  emitUpdate()
}

// end node helpers
const newReturnField = ref('')
function addReturnFieldManual() {
  const name = newReturnField.value.trim()
  if (!name) return
  if (!localData.value.return_fields.includes(name)) {
    localData.value.return_fields.push(name)
  }
  if (!localData.value.known_fields) localData.value.known_fields = []
  if (!localData.value.known_fields.includes(name)) {
    localData.value.known_fields.push(name)
  }
  newReturnField.value = ''
  emitUpdate()
}
function removeReturnField(idx: number) {
  // Only remove from return_fields; keep in known_fields so it won't be auto-added back
  localData.value.return_fields.splice(idx, 1)
  emitUpdate()
}

// compute node helpers
function addOutputField() {
  localData.value.output_fields.push('')
  emitUpdate()
}
function removeOutputField(idx: number) {
  localData.value.output_fields.splice(idx, 1)
  emitUpdate()
}
function autoDetect() {
  const code: string = localData.value.code || ''
  const matches = [...code.matchAll(/context\s*\[\s*['"](\w+)['"]\s*\]\s*=/g)]
  const detected = [...new Set(matches.map(m => m[1]))]
  localData.value.output_fields = detected
  emitUpdate()
}

function emitUpdate() {
  emit('update', editingNodeId.value, localData.value)
}

function onCodeChange() {
  const code: string = localData.value.code || ''
  const matches = [...code.matchAll(/context\s*\[\s*['"](\w+)['"]\s*\]\s*=/g)]
  const detected = [...new Set(matches.map(m => m[1]))]
  const existing: string[] = localData.value.output_fields ?? []
  const toAdd = detected.filter(f => !existing.includes(f))
  if (toAdd.length > 0) {
    localData.value.output_fields = [...existing, ...toAdd]
  }
  emitUpdate()
}
</script>

<style scoped>
.property-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px;
  border-bottom: 1px solid #252525;
  flex-shrink: 0;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.close-btn {
  color: #444 !important;
  padding: 0 4px !important;
  height: 22px !important;
}
.close-btn:hover { color: #888 !important; }
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.node-type-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 4px;
  margin-bottom: 14px;
  border: 1px solid;
}
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

.marker-select-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Context dropdown certainty indicators */
.ctx-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
  flex-shrink: 0;
}
.ctx-dot.certain    { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
.ctx-warn {
  font-size: 10px;
  color: #faad14;
  margin-left: 6px;
  vertical-align: middle;
}
.ctx-legend {
  font-size: 10px;
  color: #555;
  font-weight: 400;
  margin-left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  text-transform: none;
  letter-spacing: 0;
}

/* Context evolution timeline */
.evo-list { display: flex; flex-direction: column; gap: 8px; margin-top: 4px; }
.evo-step { display: flex; flex-direction: column; gap: 4px; }
.evo-node-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 3px;
  border: 1px solid;
  align-self: flex-start;
}
.evo-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 6px;
}
.evo-field-tag {
  font-size: 11px;
  font-family: 'Consolas', monospace;
  padding: 1px 7px;
  border-radius: 10px;
}
.evo-field-tag.certain    { background: #162312; color: #52c41a; border: 1px solid #274916; }
.evo-field-tag.conditional { background: #2b2111; color: #faad14; border: 1px solid #3f2e00; }
.key-capture {
  display: flex; align-items: center;
  min-height: 28px; padding: 3px 8px;
  background: #141414; border: 1px solid #434343; border-radius: 4px;
  cursor: pointer; outline: none; position: relative;
  transition: border-color 0.2s;
}
.key-capture:focus, .key-capture.recording {
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24,144,255,0.2);
}
.key-hint     { font-size: 11px; color: #1890ff; flex: 1; }
.key-value    { font-size: 12px; color: #d9d9d9; flex: 1; font-family: monospace; letter-spacing: 0.5px; }
.key-placeholder { font-size: 11px; color: #444; flex: 1; }
.key-clear    { color: #555; font-size: 12px; cursor: pointer; flex-shrink: 0; }
.key-clear:hover { color: #ff4d4f; }

.section-title {
  font-size: 11px; font-weight: 700; color: #555;
  text-transform: uppercase; letter-spacing: 0.8px;
  margin: 14px 0 6px;
  display: flex; align-items: center; gap: 6px;
}
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.hint-text code { background: #1e1e1e; padding: 1px 4px; border-radius: 3px; color: #7ec8e3; }
.field-row {
  display: flex; align-items: center; gap: 4px; margin-bottom: 6px;
}
.field-name    { flex: 2; min-width: 0; }
.field-type    { flex: 1.2; min-width: 0; }
.field-default { flex: 1.5; min-width: 0; }
.return-field-row {
  display: flex; align-items: center; gap: 4px; margin-bottom: 6px;
}
.return-field-row .ant-input { flex: 1; }
.add-field-btn {
  width: 100%; margin-top: 4px;
  color: #555 !important; border-color: #303030 !important;
  background: transparent !important;
  font-size: 11px !important;
}
.add-field-btn:hover { color: #888 !important; border-color: #555 !important; }
.auto-detect-btn { font-size: 11px !important; padding: 0 4px !important; height: auto !important; }

.marker-menu-type {
  display: inline-block;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  margin-right: 6px;
  font-weight: 600;
}
.type-point { background: #111d2c; color: #1890ff; }
.type-box   { background: #2b2111; color: #faad14; }
</style>
