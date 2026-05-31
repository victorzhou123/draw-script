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

    <a-form-item label="检测范围">
      <a-select v-model:value="d.range_marker" :style="{ width: '100%' }" placeholder="选择方框标记作为识别区域" allow-clear @change="update()">
        <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
          <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '方框' }}</span>
          {{ m.name }}
        </a-select-option>
      </a-select>
      <div class="hint-text" style="margin-top:4px">
        留空默认范围为选择的窗口
      </div>
      <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:2px">
        当前项目暂无标记，请先在项目中添加方框类型标记
      </div>
    </a-form-item>

    <!-- Template match -->
    <template v-if="d.vision_type === 'template_match'">
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
      <a-form-item label="结果存入">
        <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear @change="update()" />
      </a-form-item>
      <a-form-item label="匹配成功时写入">
        <a-input v-model:value="d.found_value" placeholder="留空则写入坐标 x,y" @change="update()" />
      </a-form-item>
      <a-form-item label="未匹配时写入">
        <a-input v-model:value="d.not_found_value" placeholder="留空则写入 None" @change="update()" />
      </a-form-item>
    </template>

    <!-- OCR -->
    <template v-if="d.vision_type === 'ocr'">
      <a-form-item label="识别结果存入">
        <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名（存储全部识别文字）" allow-clear @change="update()" />
      </a-form-item>
    </template>

    <!-- AI Vision -->
    <template v-if="d.vision_type === 'ai_vision'">
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
        <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear @change="update()" />
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
      <a-form-item label="颜色 (Hex)">
        <a-input v-model:value="d.params.color" placeholder="#FF0000" @change="update()" />
      </a-form-item>
      <a-form-item label="容差">
        <a-input-number v-model:value="d.params.tolerance" :min="0" :max="128" @change="update()" />
      </a-form-item>
      <a-form-item label="结果存入">
        <a-auto-complete v-model:value="d.result_var" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))" placeholder="context 字段名" allow-clear @change="update()" />
      </a-form-item>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const templateSource = ref<'fixed' | 'context'>('fixed')

watch(d, (data) => {
  if (!data || data.type !== 'vision') return
  templateSource.value = String(data.params?.template_context_var || '') ? 'context' : 'fixed'
}, { immediate: true })

function update() { ctx.emitUpdate() }

function onTemplateSourceChange() {
  if (templateSource.value === 'fixed') { d.value.params.template_context_var = '' }
  else { d.value.params.template_id = '' }
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
</style>
