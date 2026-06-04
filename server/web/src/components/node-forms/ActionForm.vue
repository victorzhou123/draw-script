<template>
  <div>
    <a-form-item label="操作类型">
      <a-select v-model:value="d.action_type" @change="onActionTypeChange">
        <a-select-option value="mouse_click">鼠标点击</a-select-option>
        <a-select-option value="mouse_double_click">鼠标双击</a-select-option>
        <a-select-option value="mouse_move">鼠标移动</a-select-option>
        <a-select-option value="mouse_drag">鼠标拖拽</a-select-option>
        <a-select-option value="keyboard_type">键盘输入</a-select-option>
        <a-select-option value="keyboard_hotkey">按键 / 快捷键</a-select-option>
        <a-select-option value="mouse_scroll">滚轮</a-select-option>
      </a-select>
    </a-form-item>

    <template v-if="d.action_type === 'mouse_scroll'">
      <a-form-item label="滚动方向">
        <a-radio-group v-model:value="d.params.direction" button-style="solid" size="small" @change="update()">
          <a-radio-button value="up">向上</a-radio-button>
          <a-radio-button value="down">向下</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <a-form-item label="滚动步数">
        <a-input-number v-model:value="d.params.amount" :min="1" :max="100" :style="{ width: '100%' }" placeholder="3" @change="update()" />
      </a-form-item>
      <a-form-item label="滚动位置">
        <a-radio-group v-model:value="scrollPositionMode" size="small" button-style="solid" @change="onScrollPositionModeChange">
          <a-radio-button value="current">当前鼠标位置</a-radio-button>
          <a-radio-button value="fixed">指定坐标</a-radio-button>
          <a-radio-button value="marker">标记</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <template v-if="scrollPositionMode === 'fixed'">
        <a-form-item label="X">
          <a-input-number v-model:value="d.params.x" :style="{ width: '100%' }" placeholder="0" @change="update()" />
        </a-form-item>
        <a-form-item label="Y">
          <a-input-number v-model:value="d.params.y" :style="{ width: '100%' }" placeholder="0" @change="update()" />
        </a-form-item>
      </template>
      <template v-else-if="scrollPositionMode === 'marker'">
        <a-form-item label="选择标记">
          <a-select v-model:value="scrollMarkerName" :style="{ width: '100%' }" placeholder="选择标记点" allow-clear @change="onScrollMarkerSelect">
            <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
              <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '框' }}</span>
              {{ m.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:-6px">
          当前项目暂无标记，请先在项目中添加标记
        </div>
      </template>
    </template>

    <template v-if="['mouse_click','mouse_double_click','mouse_move'].includes(d.action_type)">
      <a-form-item label="坐标来源">
        <a-radio-group v-model:value="coordSource" size="small" button-style="solid" @change="onCoordSourceChange">
          <a-radio-button value="fixed">固定坐标</a-radio-button>
          <a-radio-button value="marker">标记</a-radio-button>
          <a-radio-button value="context">Context</a-radio-button>
        </a-radio-group>
      </a-form-item>

      <template v-if="coordSource === 'fixed'">
        <a-form-item label="X">
          <a-input-number v-model:value="d.params.x" :style="{ width: '100%' }" placeholder="0" @change="update()" />
        </a-form-item>
        <a-form-item label="Y">
          <a-input-number v-model:value="d.params.y" :style="{ width: '100%' }" placeholder="0" @change="update()" />
        </a-form-item>
      </template>

      <template v-else-if="coordSource === 'marker'">
        <a-form-item label="选择标记">
          <a-select v-model:value="currentMarkerName" :style="{ flex: 1 }" placeholder="选择标记点" allow-clear @change="onMarkerSelect">
            <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
              <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '框' }}</span>
              {{ m.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:-6px">
          当前项目暂无标记，请先在项目中添加标记
        </div>
      </template>

      <template v-else-if="coordSource === 'context'">
        <a-form-item label="Context 变量">
          <a-select v-model:value="contextVarSelected" :style="{ width: '100%' }" placeholder="选择变量" allow-clear @change="onContextVarSelect">
            <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
              <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
              {{ f.name }}
              <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <div v-if="!ctx.contextFields.value.length" class="hint-text" style="margin-top:-6px">当前节点上游暂无 context 变量</div>
      </template>

      <a-form-item v-if="d.action_type === 'mouse_double_click'" label="点击间隔 (ms)">
        <a-input-number
          v-model:value="d.params.interval_ms"
          :min="0" :max="2000" :step="10"
          :style="{ width: '100%' }"
          placeholder="100"
          @change="update()"
        />
      </a-form-item>

      <a-form-item v-if="['mouse_click','mouse_double_click'].includes(d.action_type)" label="按键">
        <a-select v-model:value="d.params.button" @change="update()">
          <a-select-option value="left">左键</a-select-option>
          <a-select-option value="right">右键</a-select-option>
          <a-select-option value="middle">中键</a-select-option>
        </a-select>
      </a-form-item>
    </template>

    <template v-if="d.action_type === 'keyboard_type'">
      <a-form-item label="文字来源">
        <a-radio-group v-model:value="textSource" size="small" button-style="solid" @change="onTextSourceChange">
          <a-radio-button value="manual">手动输入</a-radio-button>
          <a-radio-button value="context">Context</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <template v-if="textSource === 'manual'">
        <a-form-item label="文字内容">
          <a-textarea v-model:value="d.params.text" :rows="3" @change="update()" />
        </a-form-item>
      </template>
      <template v-else>
        <a-form-item label="Context 变量">
          <a-select v-model:value="textContextVar" :style="{ width: '100%' }" placeholder="选择变量" allow-clear @change="onTextContextVarSelect">
            <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
              <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
              {{ f.name }}
              <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <div v-if="!ctx.contextFields.value.length" class="hint-text" style="margin-top:-6px">当前节点上游暂无 context 变量</div>
      </template>
    </template>

    <template v-if="d.action_type === 'keyboard_hotkey'">
      <a-form-item label="按键来源">
        <a-radio-group v-model:value="keySource" size="small" button-style="solid" @change="onKeySourceChange">
          <a-radio-button value="fixed">固定按键</a-radio-button>
          <a-radio-button value="context">Context</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <template v-if="keySource === 'fixed'">
        <a-form-item label="按键 / 快捷键">
          <div class="key-capture" :class="{ recording: isRecordingKey }" tabindex="0"
            @focus="isRecordingKey = true; pendingModifierOnly = false" @blur="isRecordingKey = false; pendingModifierOnly = false"
            @keydown.prevent="onCaptureKeyDown" @keyup.prevent="onCaptureKeyUp">
            <span v-if="isRecordingKey" class="key-hint">请按下按键…</span>
            <span v-else-if="d.params.keys" class="key-value">{{ d.params.keys }}</span>
            <span v-else class="key-placeholder">点击后按下按键</span>
            <CloseCircleOutlined v-if="d.params.keys && !isRecordingKey" class="key-clear" @mousedown.prevent="clearKey" />
          </div>
        </a-form-item>
      </template>
      <template v-else>
        <a-form-item label="Context 变量">
          <a-select v-model:value="keyContextVar" :style="{ width: '100%' }" placeholder="选择变量" allow-clear @change="onKeyContextVarSelect">
            <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
              <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
              {{ f.name }}
              <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <div v-if="!ctx.contextFields.value.length" class="hint-text" style="margin-top:-6px">当前节点上游暂无 context 变量</div>
      </template>
      <a-form-item label="按键时长来源">
        <a-radio-group v-model:value="holdMsSource" size="small" button-style="solid" @change="onHoldMsSourceChange">
          <a-radio-button value="fixed">固定时长</a-radio-button>
          <a-radio-button value="context">Context</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <template v-if="holdMsSource === 'fixed'">
        <a-form-item label="长按时长 (ms)">
          <a-input-number v-model:value="d.params.hold_ms" :min="0" :style="{ width: '100%' }" placeholder="0 = 普通按键，>0 = 长按" @change="update()" />
        </a-form-item>
      </template>
      <template v-else>
        <a-form-item label="Context 变量">
          <a-select v-model:value="holdMsContextVar" :style="{ width: '100%' }" placeholder="选择变量" allow-clear @change="onHoldMsContextVarSelect">
            <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
              <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
              {{ f.name }}
              <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
            </a-select-option>
          </a-select>
        </a-form-item>
        <div v-if="!ctx.contextFields.value.length" class="hint-text" style="margin-top:-6px">当前节点上游暂无 context 变量</div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { CloseCircleOutlined } from '@ant-design/icons-vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const coordSource = ref<'fixed' | 'marker' | 'context'>('fixed')
const contextVarSelected = ref<string | undefined>(undefined)
const currentMarkerName = ref<string | null>(null)
const textSource = ref<'manual' | 'context'>('manual')
const textContextVar = ref<string | undefined>(undefined)
const keySource = ref<'fixed' | 'context'>('fixed')
const keyContextVar = ref<string | undefined>(undefined)
const holdMsSource = ref<'fixed' | 'context'>('fixed')
const holdMsContextVar = ref<string | undefined>(undefined)
const isRecordingKey = ref(false)
const pendingModifierOnly = ref(false)
const scrollPositionMode = ref<'current' | 'fixed' | 'marker'>('current')
const scrollMarkerName = ref<string | null>(null)

const KEY_MAP: Record<string, string> = {
  ' ': 'space', Enter: 'enter', Backspace: 'backspace', Delete: 'delete',
  Escape: 'esc', Tab: 'tab',
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
  Home: 'home', End: 'end', PageUp: 'pageup', PageDown: 'pagedown',
  Insert: 'insert', Control: 'ctrl', Alt: 'alt', Shift: 'shift', Meta: 'win',
}

watch(d, (data) => {
  if (!data || data.type !== 'action') return
  currentMarkerName.value = null
  const params = data.params || {}
  const coordsStr = String(params.coords || '')
  const xStr = String(params.x || '')
  const tplCoordsM = coordsStr.match(/^\{\{([^}]+)\}\}$/)
  const tplMarkerM = xStr.match(/^\{\{markers\.([^.}]+)/)
  if (coordsStr.startsWith('$') || tplCoordsM) {
    coordSource.value = 'context'
    contextVarSelected.value = tplCoordsM ? tplCoordsM[1].trim() : coordsStr.slice(1)
  } else if (xStr.startsWith('$markers.') || tplMarkerM) {
    coordSource.value = 'marker'
    const m = tplMarkerM ?? xStr.match(/^\$markers\.([^.]+)/)
    currentMarkerName.value = m ? m[1] : null
    contextVarSelected.value = undefined
  } else {
    coordSource.value = 'fixed'
    contextVarSelected.value = undefined
  }
  const textVal = String(params.text || '')
  const tplTextM = textVal.match(/^\{\{([^}]+)\}\}$/)
  if (textVal.startsWith('$') || tplTextM) {
    textSource.value = 'context'
    textContextVar.value = tplTextM ? tplTextM[1].trim() : textVal.slice(1)
  } else {
    textSource.value = 'manual'
    textContextVar.value = undefined
  }
  const keysVal = String(params.keys || '')
  const tplKeysM = keysVal.match(/^\{\{([^}]+)\}\}$/)
  if (keysVal.startsWith('$') || tplKeysM) {
    keySource.value = 'context'
    keyContextVar.value = tplKeysM ? tplKeysM[1].trim() : keysVal.slice(1)
  } else {
    keySource.value = 'fixed'
    keyContextVar.value = undefined
  }
  const holdMsVal = params.hold_ms !== undefined && params.hold_ms !== null ? String(params.hold_ms) : ''
  const tplHoldMsM = holdMsVal.match(/^\{\{([^}]+)\}\}$/)
  if (holdMsVal.startsWith('$') || tplHoldMsM) {
    holdMsSource.value = 'context'
    holdMsContextVar.value = tplHoldMsM ? tplHoldMsM[1].trim() : holdMsVal.slice(1)
  } else {
    holdMsSource.value = 'fixed'
    holdMsContextVar.value = undefined
  }
  isRecordingKey.value = false
  if (data.action_type === 'mouse_scroll') {
    const xStr = String(params.x || '')
    const tplM = xStr.match(/^\{\{markers\.([^.}]+)/)
    if (xStr.startsWith('$markers.') || tplM) {
      scrollPositionMode.value = 'marker'
      const m = tplM ?? xStr.match(/^\$markers\.([^.]+)/)
      scrollMarkerName.value = m ? m[1] : null
    } else if (params.x != null && params.x !== '') {
      scrollPositionMode.value = 'fixed'
      scrollMarkerName.value = null
    } else {
      scrollPositionMode.value = 'current'
      scrollMarkerName.value = null
    }
    if (!data.params.direction) data.params.direction = 'down'
    if (data.params.amount == null) data.params.amount = 3
  }
}, { immediate: true })

function update() { ctx.emitUpdate() }

function onActionTypeChange() {
  if (d.value.action_type === 'mouse_scroll') {
    if (!d.value.params.direction) d.value.params.direction = 'down'
    if (d.value.params.amount == null) d.value.params.amount = 3
    scrollPositionMode.value = 'current'
    scrollMarkerName.value = null
    d.value.params.x = undefined
    d.value.params.y = undefined
  }
  update()
}

function onScrollPositionModeChange() {
  d.value.params.x = undefined
  d.value.params.y = undefined
  scrollMarkerName.value = null
  update()
}

function onScrollMarkerSelect(name: string | undefined) {
  if (!name) { scrollMarkerName.value = null; d.value.params.x = undefined; d.value.params.y = undefined; update(); return }
  const marker = ctx.availableMarkers.value.find((m: any) => m.name === name)
  if (!marker) return
  scrollMarkerName.value = marker.name
  if (marker.type === 'point') {
    d.value.params.x = `{{markers.${marker.name}.x}}`
    d.value.params.y = `{{markers.${marker.name}.y}}`
  } else {
    d.value.params.x = `{{markers.${marker.name}.cx}}`
    d.value.params.y = `{{markers.${marker.name}.cy}}`
  }
  update()
}

function onCoordSourceChange() {
  if (coordSource.value === 'fixed') {
    d.value.params.coords = ''; d.value.params.x = ''; d.value.params.y = ''
    currentMarkerName.value = null; contextVarSelected.value = undefined
  } else if (coordSource.value === 'marker') {
    d.value.params.coords = ''; d.value.params.x = ''; d.value.params.y = ''
    contextVarSelected.value = undefined
  } else {
    d.value.params.x = ''; d.value.params.y = ''; d.value.params.coords = ''
    currentMarkerName.value = null
  }
  update()
}

function onMarkerSelect(name: string | undefined) {
  if (!name) { currentMarkerName.value = null; d.value.params.x = ''; d.value.params.y = ''; update(); return }
  const marker = ctx.availableMarkers.value.find((m: any) => m.name === name)
  if (!marker) return
  currentMarkerName.value = marker.name
  if (marker.type === 'point') {
    d.value.params.x = `{{markers.${marker.name}.x}}`
    d.value.params.y = `{{markers.${marker.name}.y}}`
  } else {
    d.value.params.x = `{{markers.${marker.name}.cx}}`
    d.value.params.y = `{{markers.${marker.name}.cy}}`
  }
  update()
}

function onContextVarSelect(varName: string | undefined) {
  contextVarSelected.value = varName
  d.value.params.coords = varName ? `{{${varName}}}` : ''
  update()
}

function onTextSourceChange() {
  textContextVar.value = undefined; d.value.params.text = ''; update()
}

function onTextContextVarSelect(varName: string | undefined) {
  textContextVar.value = varName
  d.value.params.text = varName ? `{{${varName}}}` : ''
  update()
}

function onCaptureKeyDown(e: KeyboardEvent) {
  const mods: string[] = []
  if (e.ctrlKey) mods.push('ctrl')
  if (e.altKey) mods.push('alt')
  if (e.shiftKey) mods.push('shift')
  if (e.metaKey) mods.push('win')
  const mainKey = KEY_MAP[e.key] ?? (e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase())
  if (['ctrl', 'alt', 'shift', 'win'].includes(mainKey)) {
    pendingModifierOnly.value = true
    return
  }
  pendingModifierOnly.value = false
  d.value.params.keys = [...mods, mainKey].join('+')
  update()
  isRecordingKey.value = false
}

function onCaptureKeyUp(e: KeyboardEvent) {
  if (!isRecordingKey.value || !pendingModifierOnly.value) return
  const mainKey = KEY_MAP[e.key] ?? e.key.toLowerCase()
  if (['ctrl', 'alt', 'shift', 'win'].includes(mainKey)) {
    d.value.params.keys = mainKey
    update()
    isRecordingKey.value = false
    pendingModifierOnly.value = false
  }
}

function clearKey() { d.value.params.keys = ''; update() }

function onKeySourceChange() {
  keyContextVar.value = undefined; d.value.params.keys = ''; update()
}

function onKeyContextVarSelect(varName: string | undefined) {
  keyContextVar.value = varName
  d.value.params.keys = varName ? `{{${varName}}}` : ''
  update()
}

function onHoldMsSourceChange() {
  holdMsContextVar.value = undefined
  d.value.params.hold_ms = undefined
  update()
}

function onHoldMsContextVarSelect(varName: string | undefined) {
  holdMsContextVar.value = varName
  d.value.params.hold_ms = varName ? `{{${varName}}}` : undefined
  update()
}
</script>

<style scoped>
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; flex-shrink: 0; }
.ctx-dot.certain { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
.ctx-warn { font-size: 10px; color: #faad14; margin-left: 6px; vertical-align: middle; }
.marker-menu-type { display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-right: 6px; font-weight: 600; }
.type-point { background: #111d2c; color: #1890ff; }
.type-box { background: #2b2111; color: #faad14; }
.key-capture { display: flex; align-items: center; min-height: 28px; padding: 3px 8px; background: #141414; border: 1px solid #434343; border-radius: 4px; cursor: pointer; outline: none; position: relative; transition: border-color 0.2s; }
.key-capture:focus, .key-capture.recording { border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.2); }
.key-hint { font-size: 11px; color: #1890ff; flex: 1; }
.key-value { font-size: 12px; color: #d9d9d9; flex: 1; font-family: monospace; letter-spacing: 0.5px; }
.key-placeholder { font-size: 11px; color: #444; flex: 1; }
.key-clear { color: #555; font-size: 12px; cursor: pointer; flex-shrink: 0; }
.key-clear:hover { color: #ff4d4f; }
</style>
