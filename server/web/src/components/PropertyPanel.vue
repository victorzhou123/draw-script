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
          <a-input v-model:value="localData.label" @change="emit('update', localData)" />
        </a-form-item>

        <!-- Action -->
        <template v-if="nodeType === 'action'">
          <a-form-item label="操作类型">
            <a-select v-model:value="localData.action_type" @change="emit('update', localData)">
              <a-select-option value="mouse_click">鼠标点击</a-select-option>
              <a-select-option value="mouse_move">鼠标移动</a-select-option>
              <a-select-option value="mouse_drag">鼠标拖拽</a-select-option>
              <a-select-option value="keyboard_type">键盘输入</a-select-option>
              <a-select-option value="keyboard_hotkey">快捷键</a-select-option>
              <a-select-option value="keyboard_press">按键</a-select-option>
              <a-select-option value="mouse_scroll">滚轮</a-select-option>
            </a-select>
          </a-form-item>
          <template v-if="['mouse_click','mouse_move'].includes(localData.action_type)">
            <!-- Marker quick-fill -->
            <div v-if="availableMarkers.length > 0" class="marker-picker-row">
              <AimOutlined class="marker-picker-icon" />
              <span class="marker-picker-label">从标记选取坐标</span>
              <a-dropdown :trigger="['click']">
                <a-button size="small" class="marker-picker-btn">
                  {{ currentMarkerName || '选择标记' }} <DownOutlined />
                </a-button>
                <template #overlay>
                  <a-menu @click="onMarkerPick">
                    <a-menu-item v-for="m in availableMarkers" :key="m.name">
                      <span class="marker-menu-type" :class="`type-${m.type}`">
                        {{ m.type === 'point' ? '点' : '框' }}
                      </span>
                      {{ m.name }}
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
              <a-button
                v-if="currentMarkerName"
                type="text" size="small" class="marker-clear-btn"
                @click="clearMarker"
              ><CloseOutlined /></a-button>
            </div>

            <a-form-item label="X 坐标">
              <a-input v-model:value="localData.params.x" placeholder="数字或 $last_vision_result.location.x" @change="emit('update', localData)" />
            </a-form-item>
            <a-form-item label="Y 坐标">
              <a-input v-model:value="localData.params.y" placeholder="数字或 $last_vision_result.location.y" @change="emit('update', localData)" />
            </a-form-item>
            <a-form-item v-if="localData.action_type === 'mouse_click'" label="按键">
              <a-select v-model:value="localData.params.button" @change="emit('update', localData)">
                <a-select-option value="left">左键</a-select-option>
                <a-select-option value="right">右键</a-select-option>
                <a-select-option value="middle">中键</a-select-option>
              </a-select>
            </a-form-item>
          </template>
          <template v-if="localData.action_type === 'keyboard_type'">
            <a-form-item label="文字内容">
              <a-textarea v-model:value="localData.params.text" :rows="3" @change="emit('update', localData)" />
            </a-form-item>
          </template>
          <template v-if="localData.action_type === 'keyboard_hotkey'">
            <a-form-item label="按键组合 (用+分隔)">
              <a-input v-model:value="localData.params.keys" placeholder="ctrl+c" @change="emit('update', localData)" />
            </a-form-item>
          </template>
          <template v-if="localData.action_type === 'keyboard_press'">
            <a-form-item label="按键名称">
              <a-input v-model:value="localData.params.key" placeholder="enter / tab / f5" @change="emit('update', localData)" />
            </a-form-item>
          </template>
        </template>

        <!-- Vision -->
        <template v-if="nodeType === 'vision'">
          <a-form-item label="识别类型">
            <a-radio-group v-model:value="localData.vision_type" @change="emit('update', localData)">
              <a-radio value="template_match">模板匹配</a-radio>
              <a-radio value="ocr">OCR文字</a-radio>
              <a-radio value="ai_vision">AI视觉</a-radio>
              <a-radio value="color_detect">颜色检测</a-radio>
            </a-radio-group>
          </a-form-item>
          <template v-if="localData.vision_type === 'template_match'">
            <a-form-item label="相似度阈值">
              <a-slider v-model:value="localData.params.threshold" :min="0.5" :max="1.0" :step="0.05" @change="emit('update', localData)" />
            </a-form-item>
          </template>
          <template v-if="localData.vision_type === 'ocr'">
            <a-form-item label="查找文字 (留空返回全部)">
              <a-input v-model:value="localData.params.find_text" @change="emit('update', localData)" />
            </a-form-item>
          </template>
          <template v-if="localData.vision_type === 'ai_vision'">
            <a-form-item label="提示词">
              <a-textarea v-model:value="localData.params.prompt" :rows="3" @change="emit('update', localData)" />
            </a-form-item>
            <a-form-item label="模式">
              <a-select v-model:value="localData.params.mode" @change="emit('update', localData)">
                <a-select-option value="describe">描述内容</a-select-option>
                <a-select-option value="find">查找元素 (返回坐标)</a-select-option>
              </a-select>
            </a-form-item>
            <template v-if="localData.params.mode === 'find'">
              <a-form-item label="查找目标">
                <a-input v-model:value="localData.params.target" placeholder="例如：确定按钮" @change="emit('update', localData)" />
              </a-form-item>
            </template>
          </template>
          <template v-if="localData.vision_type === 'color_detect'">
            <a-form-item label="颜色 (Hex)">
              <a-input v-model:value="localData.params.color" placeholder="#FF0000" @change="emit('update', localData)" />
            </a-form-item>
            <a-form-item label="容差">
              <a-input-number v-model:value="localData.params.tolerance" :min="0" :max="128" @change="emit('update', localData)" />
            </a-form-item>
          </template>
        </template>

        <!-- Condition -->
        <template v-if="nodeType === 'condition'">
          <a-form-item label="条件类型">
            <a-select v-model:value="localData.condition_type" @change="emit('update', localData)">
              <a-select-option value="vision_found">识别是否找到</a-select-option>
              <a-select-option value="vision_text_contains">识别文字包含</a-select-option>
              <a-select-option value="variable_compare">变量比较</a-select-option>
              <a-select-option value="http_status">HTTP状态码</a-select-option>
            </a-select>
          </a-form-item>
          <template v-if="localData.condition_type === 'vision_text_contains'">
            <a-form-item label="包含文字">
              <a-input v-model:value="localData.params.value" @change="emit('update', localData)" />
            </a-form-item>
          </template>
          <template v-if="localData.condition_type === 'variable_compare'">
            <a-form-item label="变量路径">
              <a-input v-model:value="localData.params.variable" placeholder="last_http_response.status_code" @change="emit('update', localData)" />
            </a-form-item>
            <a-form-item label="运算符">
              <a-select v-model:value="localData.params.operator" @change="emit('update', localData)">
                <a-select-option value="==">等于 (==)</a-select-option>
                <a-select-option value="!=">不等于 (!=)</a-select-option>
                <a-select-option value=">">大于 (&gt;)</a-select-option>
                <a-select-option value="<">小于 (&lt;)</a-select-option>
                <a-select-option value="contains">包含</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="期望值">
              <a-input v-model:value="localData.params.value" @change="emit('update', localData)" />
            </a-form-item>
          </template>
        </template>

        <!-- Delay -->
        <template v-if="nodeType === 'delay'">
          <a-form-item label="秒数">
            <a-input-number v-model:value="localData.params.seconds" :min="0" :step="0.1" @change="emit('update', localData)" />
          </a-form-item>
          <a-form-item label="毫秒 (额外)">
            <a-input-number v-model:value="localData.params.ms" :min="0" :step="100" @change="emit('update', localData)" />
          </a-form-item>
        </template>

        <!-- Loop -->
        <template v-if="nodeType === 'loop'">
          <a-form-item label="循环次数">
            <a-input-number v-model:value="localData.params.count" :min="1" :max="1000" @change="emit('update', localData)" />
          </a-form-item>
        </template>

        <!-- HTTP -->
        <template v-if="nodeType === 'http'">
          <a-form-item label="请求方法">
            <a-select v-model:value="localData.params.method" @change="emit('update', localData)">
              <a-select-option value="GET">GET</a-select-option>
              <a-select-option value="POST">POST</a-select-option>
              <a-select-option value="PUT">PUT</a-select-option>
              <a-select-option value="DELETE">DELETE</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="URL">
            <a-input v-model:value="localData.params.url" placeholder="https://..." @change="emit('update', localData)" />
          </a-form-item>
          <a-form-item label="请求体 (JSON)">
            <a-textarea v-model:value="localData.params.bodyText" :rows="4" placeholder='{"key": "value"}' @change="emit('update', localData)" />
          </a-form-item>
        </template>

        <!-- Webhook -->
        <template v-if="nodeType === 'webhook'">
          <a-form-item label="Webhook 名称">
            <a-input v-model:value="localData.params.name" @change="emit('update', localData)" />
          </a-form-item>
        </template>
      </a-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ApartmentOutlined, CloseOutlined, AimOutlined, DownOutlined } from '@ant-design/icons-vue'
import { useProjectStore } from '@/stores/projectStore'
import { useScriptStore } from '@/stores/scriptStore'

const props = defineProps<{
  selectedNode: { id: string; data: any } | null
}>()

const emit = defineEmits<{
  (e: 'update', data: any): void
  (e: 'close'): void
}>()

const localData = ref<any>({})

const projectStore = useProjectStore()
const scriptStore = useScriptStore()

// Markers available from the current script's project
const availableMarkers = computed(() => {
  const pid = scriptStore.currentScript?.project_id
  if (!pid) return []
  return projectStore.markers[pid] ?? []
})

// Track which marker name is currently filling the coords
const currentMarkerName = ref<string | null>(null)

function onMarkerPick({ key }: { key: string }) {
  const marker = availableMarkers.value.find(m => m.name === key)
  if (!marker) return
  currentMarkerName.value = marker.name
  if (marker.type === 'point') {
    localData.value.params.x = `$markers.${marker.name}.x`
    localData.value.params.y = `$markers.${marker.name}.y`
  } else {
    // box: center coordinates
    localData.value.params.x = `$markers.${marker.name}.cx`
    localData.value.params.y = `$markers.${marker.name}.cy`
  }
  emit('update', localData.value)
}

function clearMarker() {
  currentMarkerName.value = null
  localData.value.params.x = ''
  localData.value.params.y = ''
  emit('update', localData.value)
}

// Reset marker selection when node changes
watch(() => props.selectedNode?.id, () => { currentMarkerName.value = null })

const nodeType = computed(() => localData.value.type || '')
const nodeLabel = computed(() => {
  const map: Record<string, string> = {
    start: 'Start', end: 'End', action: 'Action', screenshot: 'Screenshot',
    vision: 'Vision', condition: 'Condition', delay: 'Delay', loop: 'Loop',
    http: 'HTTP', webhook: 'Webhook',
  }
  return map[nodeType.value] || nodeType.value
})

watch(() => props.selectedNode, (node) => {
  if (!node) return
  localData.value = JSON.parse(JSON.stringify({
    label: node.data.label || '',
    type: node.data.type || '',
    action_type: node.data.action_type || 'mouse_click',
    vision_type: node.data.vision_type || 'template_match',
    condition_type: node.data.condition_type || 'vision_found',
    params: node.data.params || {},
  }))
}, { immediate: true })
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

.prop-form :deep(.ant-form-item) { margin-bottom: 12px; }
.prop-form :deep(.ant-form-item-label > label) { font-size: 11px; color: #666; }

.marker-picker-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding: 6px 8px;
  background: #111d2c;
  border: 1px solid #1890ff33;
  border-radius: 5px;
}
.marker-picker-icon { color: #1890ff; font-size: 12px; }
.marker-picker-label { font-size: 11px; color: #555; flex: 1; }
.marker-picker-btn {
  font-size: 11px !important;
  color: #1890ff !important;
  border-color: #1890ff44 !important;
  background: #0d1926 !important;
  padding: 0 8px !important;
  height: 22px !important;
}
.marker-clear-btn { color: #444 !important; padding: 0 4px !important; height: 22px !important; }
.marker-clear-btn:hover { color: #ff4d4f !important; }
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
