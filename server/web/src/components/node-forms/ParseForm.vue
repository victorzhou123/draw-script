<template>
  <div>
    <!-- 输入变量 + 数据格式（同行） -->
    <a-form-item label="输入变量">
      <div class="var-row">
        <a-select
          v-model:value="d.input_var"
          placeholder="选择或输入变量名"
          allow-clear
          show-search
          class="var-select"
          @change="update()"
        >
          <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
            {{ f.name }}
          </a-select-option>
        </a-select>
        <!-- 如需支持更多格式（如 xml、json），在此添加选项并在后端 parse_node.py 中实现对应处理逻辑 -->
        <a-select v-model:value="d.input_format" size="small" class="format-select" @change="update()">
          <a-select-option value="html">HTML</a-select-option>
        </a-select>
      </div>
      <div class="field-hint">从 context 中读取该变量的值作为待解析内容，运行时校验格式是否符合声明</div>
    </a-form-item>

    <!-- 提取方式 -->
    <a-form-item label="提取方式">
      <a-radio-group v-model:value="d.params.selector_mode" size="small" @change="update()">
        <a-radio value="multi_field">多字段映射</a-radio>
        <a-radio value="single">单选择器</a-radio>
      </a-radio-group>
    </a-form-item>

    <!-- 多字段映射 -->
    <template v-if="d.params.selector_mode === 'multi_field'">
      <a-form-item label="字段映射">
        <div v-for="(f, idx) in parseFields" :key="idx" class="field-row">
          <a-input v-model:value="f.name" placeholder="字段名" class="field-name" @change="syncFields()" />
          <a-select v-model:value="f.selector_type" size="small" style="width:80px;flex-shrink:0" @change="syncFields()">
            <a-select-option value="css">CSS</a-select-option>
            <a-select-option value="xpath">XPath</a-select-option>
          </a-select>
          <a-input v-model:value="f.selector" placeholder="选择器" style="flex:2" @change="syncFields()" />
          <a-button type="text" size="small" danger @click="removeField(idx)">✕</a-button>
        </div>
        <a-button size="small" class="add-field-btn" @click="addField">+ 添加字段</a-button>
        <div class="field-hint">
          {{ d.params.output_format === 'str' ? '结果以纯文本写入 context' : '结果以 JSON 对象写入 context' }}
        </div>
      </a-form-item>
      <a-form-item label="输出格式">
        <a-select v-model:value="d.params.output_format" size="small" style="width:120px" @change="update()">
          <a-select-option value="json">JSON（对象）</a-select-option>
          <a-select-option value="str">str（纯文本）</a-select-option>
        </a-select>
      </a-form-item>
    </template>

    <!-- 单选择器 -->
    <template v-else>
      <a-form-item label="选择器类型">
        <a-radio-group v-model:value="d.params.selector_type" size="small" @change="update()">
          <a-radio value="css">CSS</a-radio>
          <a-radio value="xpath">XPath</a-radio>
        </a-radio-group>
      </a-form-item>
      <a-form-item label="选择器">
        <a-input v-model:value="d.params.selector" placeholder="h1.title 或 //h1[@class='title']" @change="update()" />
        <div class="field-hint">结果以 str 写入 context</div>
      </a-form-item>
    </template>

    <!-- 结果写入变量 -->
    <a-form-item label="结果写入变量">
      <a-input v-model:value="d.output_var" placeholder="parse_result" @change="update()" />
      <div class="field-hint">将提取结果写入 context 中指定的变量名</div>
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

interface ParseField {
  name: string
  selector_type: 'css' | 'xpath'
  selector: string
}

const parseFields = ref<ParseField[]>([])


watch(d, (data) => {
  if (!data || data.type !== 'parse') return
  if (!data.params) data.params = {}
  if (!data.params.selector_mode) data.params.selector_mode = 'multi_field'
  if (!data.params.selector_type) data.params.selector_type = 'css'
  if (!data.params.output_format) data.params.output_format = 'json'
  if (!data.input_format) data.input_format = 'html'
  parseFields.value = Array.isArray(data.params.fields) ? [...data.params.fields] : []
}, { immediate: true })

function update() { ctx.emitUpdate() }

function addField() {
  parseFields.value.push({ name: '', selector_type: 'css', selector: '' })
  syncFields()
}

function removeField(idx: number) {
  parseFields.value.splice(idx, 1)
  syncFields()
}

function syncFields() {
  d.value.params.fields = parseFields.value.map(f => ({ ...f }))
  update()
}
</script>

<style scoped>
.var-row { display: flex; gap: 6px; align-items: center; }
.var-select { flex: 1; min-width: 0; }
.format-select { width: 80px; flex-shrink: 0; }

.field-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.field-name { flex: 1.5; min-width: 0; }
.add-field-btn {
  width: 100%; margin-top: 4px; color: #555 !important;
  border-color: #303030 !important; background: transparent !important;
  font-size: 11px !important;
}
.add-field-btn:hover { color: #888 !important; border-color: #555 !important; }
.field-hint { font-size: 11px; color: #444; margin-top: 3px; }
</style>
