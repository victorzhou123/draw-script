<template>
  <div>
    <!-- 爬虫引擎选择 -->
    <a-form-item label="爬虫引擎">
      <a-radio-group v-model:value="d.crawl_engine" button-style="solid" size="small" @change="update()">
        <a-radio-button value="native">原生（CSS/XPath）</a-radio-button>
        <a-radio-button value="firecrawl">Firecrawl</a-radio-button>
      </a-radio-group>
    </a-form-item>

    <!-- URL -->
    <a-form-item label="URL">
      <a-input v-model:value="d.params.url" placeholder="https://example.com" @change="update()" />
      <div class="tpl-hint">
        使用 <code v-pre>{{变量名}}</code> 引用 context 字段
        <span v-if="ctx.contextFields.value.length" class="tpl-vars">
          —
          <span v-for="f in ctx.contextFields.value" :key="f.name" class="tpl-var-chip" @click="insertUrl(f.name)">{{ f.name }}</span>
        </span>
      </div>
    </a-form-item>

    <!-- ── 原生模式 ────────────────────────────────────── -->
    <template v-if="d.crawl_engine === 'native'">
      <a-form-item label="提取方式">
        <a-radio-group v-model:value="d.params.selector_mode" size="small" @change="update()">
          <a-radio value="multi_field">多字段映射</a-radio>
          <a-radio value="single">单选择器</a-radio>
        </a-radio-group>
      </a-form-item>

      <!-- 多字段映射 -->
      <template v-if="d.params.selector_mode === 'multi_field'">
        <a-form-item label="字段映射">
          <div v-for="(f, idx) in nativeFields" :key="idx" class="field-row">
            <a-input v-model:value="f.name" placeholder="字段名" class="field-name" @change="syncFields()" />
            <a-select v-model:value="f.selector_type" size="small" style="width:80px;flex-shrink:0" @change="syncFields()">
              <a-select-option value="css">CSS</a-select-option>
              <a-select-option value="xpath">XPath</a-select-option>
            </a-select>
            <a-input v-model:value="f.selector" placeholder="选择器" style="flex:2" @change="syncFields()" />
            <a-button type="text" size="small" danger @click="removeField(idx)">✕</a-button>
          </div>
          <a-button size="small" class="add-field-btn" @click="addField">+ 添加字段</a-button>
          <div class="field-hint">结果以 JSON 对象写入 context</div>
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
        </a-form-item>
        <a-form-item label="输出格式">
          <a-select v-model:value="d.params.output_format" size="small" style="width:120px" @change="update()">
            <a-select-option value="json">JSON（数组）</a-select-option>
            <a-select-option value="text">纯文本</a-select-option>
          </a-select>
        </a-form-item>
      </template>
    </template>

    <!-- ── Firecrawl 模式 ──────────────────────────────── -->
    <template v-else>
      <a-form-item label="API Key 配置">
        <a-select
          v-model:value="d.params.service_key_id"
          placeholder="选择已配置的 Firecrawl Key"
          allow-clear
          style="width:100%"
          @change="update()"
        >
          <a-select-option v-for="k in ctx.serviceKeys.value" :key="k.id" :value="k.id">
            {{ k.service_name }}
          </a-select-option>
        </a-select>
        <div v-if="!ctx.serviceKeys.value.length" class="field-hint warn-hint">
          暂无 API Key，请先在「配置中心 → API & Key」中添加 Firecrawl 服务
        </div>
      </a-form-item>

      <a-form-item label="爬取范围">
        <a-radio-group v-model:value="d.params.crawl_type" size="small" @change="update()">
          <a-radio value="single">单页</a-radio>
          <a-radio value="recursive">递归爬取</a-radio>
        </a-radio-group>
      </a-form-item>

      <!-- 递归参数 -->
      <template v-if="d.params.crawl_type === 'recursive'">
        <a-form-item label="最大深度">
          <a-input-number v-model:value="d.params.max_depth" :min="1" :max="10" style="width:80px" @change="update()" />
        </a-form-item>
        <a-form-item label="最大页数">
          <a-input-number v-model:value="d.params.limit" :min="1" :max="500" style="width:80px" @change="update()" />
        </a-form-item>
        <a-form-item label="URL 过滤">
          <a-input v-model:value="d.params.url_filter" placeholder="例如：/blog/*（留空不过滤）" @change="update()" />
          <div class="field-hint">仅爬取匹配此路径模式的页面</div>
        </a-form-item>
      </template>

      <a-form-item label="输出格式">
        <a-select v-model:value="d.params.output_format" size="small" style="width:130px" @change="update()">
          <a-select-option value="markdown">Markdown</a-select-option>
          <a-select-option value="html">HTML</a-select-option>
          <a-select-option value="rawHtml">原始 HTML</a-select-option>
          <a-select-option value="links">链接列表</a-select-option>
        </a-select>
      </a-form-item>
    </template>

    <!-- 输出 context 变量 -->
    <a-form-item label="结果写入变量">
      <a-input v-model:value="d.output_var" placeholder="crawl_result" @change="update()" />
      <div class="field-hint">将爬取结果写入 context 中指定的变量名</div>
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

interface NativeField {
  name: string
  selector_type: 'css' | 'xpath'
  selector: string
}

const nativeFields = ref<NativeField[]>([])

watch(d, (data) => {
  if (!data || data.type !== 'crawl') return
  // Initialize defaults
  if (!data.params) data.params = {}
  if (!data.params.selector_mode) data.params.selector_mode = 'multi_field'
  if (!data.params.selector_type) data.params.selector_type = 'css'
  if (!data.params.crawl_type) data.params.crawl_type = 'single'
  if (!data.params.output_format) data.params.output_format = data.crawl_engine === 'firecrawl' ? 'markdown' : 'json'
  if (data.params.max_depth === undefined) data.params.max_depth = 2
  if (data.params.limit === undefined) data.params.limit = 10
  nativeFields.value = Array.isArray(data.params.fields) ? [...data.params.fields] : []
}, { immediate: true })

function update() { ctx.emitUpdate() }

function insertUrl(varName: string) {
  d.value.params.url = (d.value.params.url ?? '') + `{{${varName}}}`
  update()
}

function addField() {
  nativeFields.value.push({ name: '', selector_type: 'css', selector: '' })
  syncFields()
}

function removeField(idx: number) {
  nativeFields.value.splice(idx, 1)
  syncFields()
}

function syncFields() {
  d.value.params.fields = nativeFields.value.map(f => ({ ...f }))
  update()
}
</script>

<style scoped>
.tpl-hint { font-size: 11px; color: #444; margin-top: 4px; line-height: 1.6; }
.tpl-hint code { background: #1e1e1e; padding: 1px 4px; border-radius: 3px; color: #7ec8e3; font-size: 11px; }
.tpl-vars { color: #444; }
.tpl-var-chip {
  display: inline-block; background: #111d2c; color: #4096ff;
  border: 1px solid #1d3c6b; border-radius: 3px; font-size: 10px;
  padding: 0 5px; margin: 0 2px; cursor: pointer;
  font-family: 'Consolas', monospace; transition: background 0.15s;
}
.tpl-var-chip:hover { background: #1d3c6b; }

.field-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.field-name { flex: 1.5; min-width: 0; }
.add-field-btn {
  width: 100%; margin-top: 4px; color: #555 !important;
  border-color: #303030 !important; background: transparent !important;
  font-size: 11px !important;
}
.add-field-btn:hover { color: #888 !important; border-color: #555 !important; }

.field-hint { font-size: 11px; color: #444; margin-top: 3px; }
.warn-hint { color: #d48806; }
</style>
