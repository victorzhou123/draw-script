<template>
  <div>
    <!--
      [FIRECRAWL_DISABLED] 爬虫引擎选择器暂时屏蔽，当前仅支持原生 HTTP 爬取。
      重新启用时取消注释下方 a-form-item，并同步开放后端 crawl_node.py 中的 Firecrawl 路径。

      <a-form-item label="爬虫引擎">
        <a-radio-group v-model:value="d.crawl_engine" button-style="solid" size="small" @change="update()">
          <a-radio-button value="native">原生（HTTP）</a-radio-button>
          <a-radio-button value="firecrawl">Firecrawl</a-radio-button>
        </a-radio-group>
      </a-form-item>
    -->

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

    <!-- 结果写入变量 -->
    <a-form-item label="结果写入变量">
      <a-input v-model:value="d.output_var" placeholder="crawl_result" @change="update()" />
      <div class="field-hint">将原始 HTML 写入 context 中指定的变量名，可作为 Parse 节点的输入</div>
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

watch(d, (data) => {
  if (!data || data.type !== 'crawl') return
  if (!data.params) data.params = {}
}, { immediate: true })

function update() { ctx.emitUpdate() }

function insertUrl(varName: string) {
  d.value.params.url = (d.value.params.url ?? '') + `{{${varName}}}`
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
.field-hint { font-size: 11px; color: #444; margin-top: 3px; }
</style>
