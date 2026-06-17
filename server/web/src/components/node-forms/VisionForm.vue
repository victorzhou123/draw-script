<template>
  <div>
    <a-form-item label="识别类型">
      <a-radio-group v-model:value="d.vision_type" @change="update()">
        <a-radio value="template_match">模板匹配</a-radio>
        <a-radio value="ocr">OCR文字</a-radio>
        <a-radio value="ai_vision">AI视觉</a-radio>
        <a-radio value="color_detect">颜色检测</a-radio>
      </a-radio-group>
    </a-form-item>

    <!-- Template match -->
    <template v-if="d.vision_type === 'template_match'">
      <a-form-item label="检测范围">
        <a-select v-model:value="d.range_marker" :style="{ width: '100%' }" placeholder="选择方框标记作为识别区域" allow-clear @change="update()">
          <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
            <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '方框' }}</span>
            {{ m.name }}
          </a-select-option>
        </a-select>
        <div class="hint-text" style="margin-top:4px">留空默认范围为选择的窗口</div>
        <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:2px">当前项目暂无标记，请先在项目中添加方框类型标记</div>
      </a-form-item>
      <a-form-item label="模板来源">
        <a-radio-group v-model:value="templateSource" size="small" button-style="solid" @change="onTemplateSourceChange">
          <a-radio-button value="fixed">固定模板</a-radio-button>
          <a-radio-button value="context">Context 字段</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <a-form-item v-if="templateSource === 'fixed'" label="模板">
        <a-select v-model:value="d.params.template_id" :style="{ width: '100%' }" placeholder="选择项目模板" allow-clear @change="update()">
          <a-select-option v-for="t in ctx.availableTemplates.value" :key="t.id" :value="t.id">{{ t.name }}</a-select-option>
        </a-select>
        <div v-if="!ctx.availableTemplates.value.length" class="hint-text" style="margin-top:4px">当前项目暂无模板，请先在项目组中上传</div>
      </a-form-item>
      <a-form-item v-else label="Context 字段">
        <a-select v-model:value="d.params.template_context_var" :style="{ width: '100%' }" placeholder="选择包含 base64 图片数据的字段" allow-clear @change="update()">
          <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
            <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />{{ f.name }}
            <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
          </a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="相似度阈值">
        <a-slider v-model:value="d.params.threshold" :min="0.5" :max="1.0" :step="0.05" @change="update()" />
      </a-form-item>
      <a-form-item label="检测模式">
        <a-select v-model:value="d.params.mode" :style="{ width: '100%' }" @change="onModeChange">
          <a-select-option value="single">单个匹配</a-select-option>
          <a-select-option value="all_matches">所有匹配</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="存入类型">
        <a-select v-model:value="d.params.result_type" :style="{ width: '100%' }" @change="onResultTypeChange">
          <a-select-option value="coordinate">坐标</a-select-option>
          <a-select-option value="custom">自定义</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item v-if="d.params.result_type === 'custom'" label="匹配成功时写入">
        <div class="value-row">
          <a-input v-if="d.found_value_type !== 'bool'" v-model:value="d.found_value" placeholder="留空则不写入" class="value-input" @change="update()" />
          <a-select v-else v-model:value="d.found_value" class="value-input" allow-clear placeholder="选择 True / False" @change="update()">
            <a-select-option value="True">True</a-select-option>
            <a-select-option value="False">False</a-select-option>
          </a-select>
          <a-select v-model:value="d.found_value_type" class="value-type-select" @change="update()">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </a-form-item>
      <a-form-item label="结果存入">
        <div v-if="d.params.result_type !== 'custom'" class="value-row">
          <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear class="value-input" @change="update()" />
          <a-select v-model:value="d.found_value_type" class="value-type-select" @change="update()">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
        <a-auto-complete v-else v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear @change="update()" />
      </a-form-item>
      <a-form-item label="未匹配时写入">
        <div class="value-row">
          <a-input v-if="d.not_found_value_type === 'None'" value="None" disabled class="value-input" />
          <a-input v-else-if="d.not_found_value_type !== 'bool'" v-model:value="d.not_found_value" placeholder="留空则写入空值" class="value-input" @change="update()" />
          <a-select v-else v-model:value="d.not_found_value" class="value-input" allow-clear placeholder="选择 True / False" @change="update()">
            <a-select-option value="True">True</a-select-option>
            <a-select-option value="False">False</a-select-option>
          </a-select>
          <a-select v-model:value="d.not_found_value_type" class="value-type-select" @change="onNotFoundValueTypeChange">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </a-form-item>
      <a-form-item label="结果标记">
        <a-switch v-model:checked="d.params.show_overlay" @change="update()" />
        <span class="hint-text" style="margin-left:8px">识别成功后在客户端屏幕高亮匹配位置</span>
      </a-form-item>
      <template v-if="d.params.show_overlay">
        <a-form-item label="显示时长">
          <a-radio-group v-model:value="d.params.overlay_mode" size="small" button-style="solid" @change="update()">
            <a-radio-button value="fixed">固定秒数</a-radio-button>
            <a-radio-button value="until_next">下次执行刷新</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="d.params.overlay_mode !== 'until_next'" label="时长(秒)">
          <a-input-number
            v-model:value="d.params.overlay_duration"
            :min="0.5" :max="10" :step="0.5"
            :style="{ width: '120px' }"
            placeholder="2"
            @change="update()"
          />
        </a-form-item>
      </template>
    </template>

    <!-- OCR -->
    <template v-if="d.vision_type === 'ocr'">
      <a-form-item label="图片来源">
        <a-radio-group v-model:value="ocrImageSource" size="small" button-style="solid" @change="onOcrImageSourceChange">
          <a-radio-button value="screenshot">客户端截图</a-radio-button>
          <a-radio-button value="context">Context 字段</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <a-form-item v-if="ocrImageSource === 'context'" label="Context 字段">
        <a-select v-model:value="d.params.ocr_context_image_var" :style="{ width: '100%' }" placeholder="选择包含 base64 图片数据的字段" allow-clear @change="update()">
          <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
            <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />{{ f.name }}
            <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
          </a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item v-if="ocrImageSource === 'screenshot'" label="检测范围">
        <a-select v-model:value="d.range_marker" :style="{ width: '100%' }" placeholder="选择方框标记作为识别区域" allow-clear @change="update()">
          <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
            <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '方框' }}</span>
            {{ m.name }}
          </a-select-option>
        </a-select>
        <div class="hint-text" style="margin-top:4px">留空默认范围为选择的窗口</div>
        <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:2px">当前项目暂无标记，请先在项目中添加方框类型标记</div>
      </a-form-item>
      <a-form-item label="识别结果存入">
        <div class="value-row">
          <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名（存储全部识别文字）" allow-clear class="value-input" @change="update()" />
          <a-select v-model:value="d.value_type" class="value-type-select" @change="update()">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </a-form-item>
      <a-form-item label="未识别时写入">
        <div class="value-row">
          <a-input v-if="d.ocr_not_found_value_type === 'None'" value="None" disabled class="value-input" />
          <a-input v-else-if="d.ocr_not_found_value_type !== 'bool'" v-model:value="d.ocr_not_found_value" placeholder="留空则写入空字符串" class="value-input" @change="update()" />
          <a-select v-else v-model:value="d.ocr_not_found_value" class="value-input" allow-clear placeholder="选择 True / False" @change="update()">
            <a-select-option value="True">True</a-select-option>
            <a-select-option value="False">False</a-select-option>
          </a-select>
          <a-select v-model:value="d.ocr_not_found_value_type" class="value-type-select" @change="onOcrNotFoundValueTypeChange">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
        <div class="hint-text" style="margin-top:4px">OCR未识别到任何文字时写入此值</div>
      </a-form-item>
    </template>

    <!-- AI Vision -->
    <template v-if="d.vision_type === 'ai_vision'">
      <a-form-item label="图片来源">
        <a-radio-group v-model:value="aiImageSource" size="small" button-style="solid" @change="onAiImageSourceChange">
          <a-radio-button value="screenshot">客户端截图</a-radio-button>
          <a-radio-button value="context">Context 字段</a-radio-button>
        </a-radio-group>
      </a-form-item>
      <a-form-item v-if="aiImageSource === 'context'" label="Context 字段">
        <a-select v-model:value="d.params.context_image_var" :style="{ width: '100%' }" placeholder="选择包含 base64 图片数据的字段" allow-clear @change="update()">
          <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
            <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />{{ f.name }}
            <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
          </a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item v-if="aiImageSource === 'screenshot'" label="检测范围">
        <a-select v-model:value="d.range_marker" :style="{ width: '100%' }" placeholder="选择方框标记作为识别区域" allow-clear @change="update()">
          <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
            <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '方框' }}</span>
            {{ m.name }}
          </a-select-option>
        </a-select>
        <div class="hint-text" style="margin-top:4px">留空默认范围为选择的窗口</div>
        <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:2px">当前项目暂无标记，请先在项目中添加方框类型标记</div>
      </a-form-item>
      <a-form-item label="AI 模型">
        <a-select v-model:value="d.params.model_id" :style="{ width: '100%' }" placeholder="选择 AI 模型" allow-clear @change="update()">
          <a-select-option v-for="m in ctx.aiModels.value" :key="m.id" :value="m.id">
            {{ m.name }}<span class="model-provider-tag">{{ m.provider === 'qwen' ? 'Qwen' : 'GLM' }}</span>
          </a-select-option>
        </a-select>
        <div v-if="!ctx.aiModels.value.length" class="hint-text" style="margin-top:4px">暂无可用 AI 模型，请先在「AI 模型」管理中添加</div>
      </a-form-item>
      <a-form-item label="提示词">
        <a-textarea v-model:value="d.params.prompt" :rows="3" @change="update()" />
      </a-form-item>
      <a-form-item label="模式">
        <a-select v-model:value="d.params.mode" @change="update()">
          <a-select-option value="describe">描述内容</a-select-option>
          <a-select-option value="find">查找元素 (返回坐标)</a-select-option>
        </a-select>
      </a-form-item>
      <template v-if="d.params.mode === 'find'">
        <a-form-item label="查找目标">
          <a-input v-model:value="d.params.target" placeholder="例如：确定按钮" @change="update()" />
        </a-form-item>
      </template>
      <a-form-item label="结果存入">
        <div class="value-row">
          <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear class="value-input" @change="update()" />
          <a-select v-model:value="d.value_type" class="value-type-select" @change="update()">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </a-form-item>
      <a-form-item label="数据后处理">
        <a-select
          v-model:value="d.post_process"
          mode="multiple"
          :style="{ width: '100%' }"
          placeholder="可选，选择后处理步骤"
          allow-clear
          @change="update()"
        >
          <a-select-option value="parse_markdown_json">解析 Markdown JSON</a-select-option>
        </a-select>
      </a-form-item>
    </template>

    <!-- Color detect -->
    <template v-if="d.vision_type === 'color_detect'">
      <a-form-item label="检测范围">
        <a-select v-model:value="d.range_marker" :style="{ width: '100%' }" placeholder="选择方框标记作为识别区域" allow-clear @change="update()">
          <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
            <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '方框' }}</span>
            {{ m.name }}
          </a-select-option>
        </a-select>
        <div class="hint-text" style="margin-top:4px">留空默认范围为选择的窗口</div>
        <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:2px">当前项目暂无标记，请先在项目中添加方框类型标记</div>
      </a-form-item>
      <a-form-item label="检测模式">
        <a-select v-model:value="d.params.mode" :style="{ width: '100%' }" @change="onModeChange">
          <a-select-option value="largest_contour">最大色块</a-select-option>
          <a-select-option value="all_contours">所有目标</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="存入类型">
        <a-select v-model:value="d.params.result_type" :style="{ width: '100%' }" @change="onResultTypeChange">
          <a-select-option value="coordinate">坐标</a-select-option>
          <a-select-option value="custom">自定义</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item v-if="d.params.result_type === 'custom'" label="匹配成功时写入">
        <div class="value-row">
          <a-input v-if="d.found_value_type !== 'bool'" v-model:value="d.found_value" placeholder="留空则不写入" class="value-input" @change="update()" />
          <a-select v-else v-model:value="d.found_value" class="value-input" allow-clear placeholder="选择 True / False" @change="update()">
            <a-select-option value="True">True</a-select-option>
            <a-select-option value="False">False</a-select-option>
          </a-select>
          <a-select v-model:value="d.found_value_type" class="value-type-select" @change="update()">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </a-form-item>
      <a-form-item label="结果存入">
        <div v-if="d.params.result_type !== 'custom'" class="value-row">
          <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear class="value-input" @change="update()" />
          <a-select v-model:value="d.found_value_type" class="value-type-select" @change="update()">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
        <a-auto-complete v-else v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear @change="update()" />
      </a-form-item>
      <a-form-item label="未匹配时写入">
        <div class="value-row">
          <a-input v-if="d.not_found_value_type === 'None'" value="None" disabled class="value-input" />
          <a-input v-else-if="d.not_found_value_type !== 'bool'" v-model:value="d.not_found_value" placeholder="留空则写入空值" class="value-input" @change="update()" />
          <a-select v-else v-model:value="d.not_found_value" class="value-input" allow-clear placeholder="选择 True / False" @change="update()">
            <a-select-option value="True">True</a-select-option>
            <a-select-option value="False">False</a-select-option>
          </a-select>
          <a-select v-model:value="d.not_found_value_type" class="value-type-select" @change="onNotFoundValueTypeChange">
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </a-form-item>
      <a-form-item v-if="d.params.mode === 'all_contours'" label="最小面积">
        <a-input-number v-model:value="d.params.min_area" :min="0" :style="{ width: '100%' }" placeholder="过滤小于此面积的色块（像素²）" @change="update()" />
        <div class="hint-text" style="margin-top:4px">建议 100~500，过滤噪点用</div>
      </a-form-item>
      <a-form-item label="颜色 (Hex)">
        <a-input v-model:value="d.params.color" placeholder="#FF0000" @change="update()" />
      </a-form-item>
      <a-form-item label="容差">
        <a-input-number v-model:value="d.params.tolerance" :min="0" :max="128" @change="update()" />
      </a-form-item>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const VALUE_TYPES = ['str', 'int', 'float', 'bool', 'list', 'dict', 'None']

const templateSource = ref<'fixed' | 'context'>('fixed')
const aiImageSource = ref<'screenshot' | 'context'>('screenshot')
const ocrImageSource = ref<'screenshot' | 'context'>('screenshot')

function isArrayMode(data: any): boolean {
  return data.params.mode === 'all_matches' || data.params.mode === 'all_contours'
}

watch(d, (data) => {
  if (!data || data.type !== 'vision') return
  templateSource.value = String(data.params?.template_context_var || '') ? 'context' : 'fixed'
  aiImageSource.value = String(data.params?.context_image_var || '') ? 'context' : 'screenshot'
  ocrImageSource.value = String(data.params?.ocr_context_image_var || '') ? 'context' : 'screenshot'
  const validModes: Record<string, string[]> = {
    template_match: ['single', 'all_matches'],
    color_detect: ['largest_contour', 'all_contours'],
    ai_vision: ['describe', 'find'],
  }
  const modesForType = validModes[data.vision_type]
  if (modesForType && !modesForType.includes(data.params.mode)) {
    data.params.mode = modesForType[0]
    ctx.emitUpdate()
  }
  if (data.params.show_overlay && !data.params.overlay_mode) { data.params.overlay_mode = 'fixed'; ctx.emitUpdate() }

  if (['template_match', 'color_detect'].includes(data.vision_type)) {
    if (!data.params.result_type) {
      const hasCustomValues = (data.found_value || '') || (data.not_found_value || '')
      data.params.result_type = hasCustomValues ? 'custom' : 'coordinate'
      ctx.emitUpdate()
    }
    if (!data.found_value_type) {
      data.found_value_type = isArrayMode(data) ? 'list' : (data.params.result_type === 'coordinate' ? 'str' : (data.found_value ? 'str' : 'None'))
      ctx.emitUpdate()
    }
    if (!data.not_found_value_type) {
      data.not_found_value_type = data.not_found_value ? 'str' : 'None'
      ctx.emitUpdate()
    }
  }

  if (['ocr', 'ai_vision'].includes(data.vision_type) && !data.value_type) {
    data.value_type = 'str'
    ctx.emitUpdate()
  }

  if (data.vision_type === 'ocr' && !data.ocr_not_found_value_type) {
    data.ocr_not_found_value_type = 'str'
    ctx.emitUpdate()
  }
}, { immediate: true })

function update() { ctx.emitUpdate() }

function onResultTypeChange() {
  if (d.value.params.result_type === 'coordinate') {
    d.value.found_value = ''
    d.value.found_value_type = isArrayMode(d.value) ? 'list' : 'str'
  }
  update()
}

function onModeChange() {
  if (isArrayMode(d.value)) {
    d.value.found_value_type = 'list'
  } else if (d.value.params.result_type === 'coordinate') {
    d.value.found_value_type = 'str'
  }
  update()
}

function onTemplateSourceChange() {
  if (templateSource.value === 'fixed') { d.value.params.template_context_var = '' }
  else { d.value.params.template_id = '' }
  update()
}

function onAiImageSourceChange() {
  if (aiImageSource.value === 'screenshot') { d.value.params.context_image_var = '' }
  update()
}

function onOcrImageSourceChange() {
  if (ocrImageSource.value === 'screenshot') { d.value.params.ocr_context_image_var = '' }
  update()
}

function onNotFoundValueTypeChange() {
  if (d.value.not_found_value_type === 'None') {
    d.value.not_found_value = ''
  }
  update()
}

function onOcrNotFoundValueTypeChange() {
  if (d.value.ocr_not_found_value_type === 'None') {
    d.value.ocr_not_found_value = ''
  }
  update()
}
</script>

<style scoped>
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; flex-shrink: 0; }
.ctx-dot.certain { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
.ctx-warn { font-size: 10px; color: #faad14; margin-left: 6px; }
.marker-menu-type { display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-right: 6px; font-weight: 600; }
.type-point { background: #111d2c; color: #1890ff; }
.type-box { background: #2b2111; color: #faad14; }
.model-provider-tag { display: inline-block; font-size: 10px; padding: 0 5px; border-radius: 3px; margin-left: 6px; background: #1a0a2e; color: #9254de; font-weight: 600; }
.value-row { display: flex; align-items: center; gap: 6px; }
.value-input { flex: 1; min-width: 0; }
.value-type-select { width: 100px; flex-shrink: 0; }
</style>
