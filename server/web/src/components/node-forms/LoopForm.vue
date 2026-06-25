<template>
  <div>
    <a-form-item label="循环模式">
      <a-radio-group v-model:value="loopMode" size="small" button-style="solid" @change="onModeChange">
        <a-radio-button value="count">次数</a-radio-button>
        <a-radio-button value="iterate">迭代</a-radio-button>
      </a-radio-group>
    </a-form-item>

    <!-- ── 次数模式 ── -->
    <template v-if="loopMode === 'count'">
      <a-form-item label="次数来源">
        <a-radio-group v-model:value="countSource" size="small" button-style="solid" @change="onCountSourceChange">
          <a-radio-button value="fixed">固定次数</a-radio-button>
          <a-radio-button value="context">Context</a-radio-button>
        </a-radio-group>
      </a-form-item>

      <template v-if="countSource === 'fixed'">
        <a-form-item label="最大循环次数">
          <a-input-number v-model:value="d.params.count" :min="1" :max="1000" @change="update()" />
          <div class="hint-text" style="margin-top:4px">填入的数字表示主干部分执行的次数</div>
        </a-form-item>
      </template>
      <template v-else>
        <a-form-item label="Context 变量">
          <a-select v-model:value="countContextVar" :style="{ width: '100%' }" placeholder="选择变量" allow-clear @change="onCountContextVarSelect">
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

    <!-- ── 迭代模式 ── -->
    <template v-else>
      <a-form-item label="迭代变量">
        <a-select
          v-model:value="d.params.iter_var"
          :style="{ width: '100%' }"
          placeholder="选择可迭代的 context 变量"
          allow-clear
          @change="update()"
        >
          <a-select-option v-for="f in ctx.contextFields.value" :key="f.name" :value="f.name">
            <span class="ctx-dot" :class="f.certain ? 'certain' : 'conditional'" />
            {{ f.name }}
            <span v-if="!f.certain" class="ctx-warn">⚠ 条件分支</span>
          </a-select-option>
        </a-select>
        <div class="hint-text" style="margin-top:4px">支持 list 和 dict；dict 每次取出 {key, value} 小对象</div>
      </a-form-item>

      <a-form-item label="元素写入变量">
        <a-input v-model:value="d.params.item_var" placeholder="item" @change="update()" />
        <div class="hint-text" style="margin-top:4px">每轮迭代取出的元素写入 context 中此变量名</div>
      </a-form-item>

      <a-form-item label="元素类型">
        <a-select v-model:value="d.params.item_type" :style="{ width: '100%' }" @change="update()">
          <a-select-option v-for="t in ITEM_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
        </a-select>
        <div class="hint-text" style="margin-top:4px">运行时对取出的元素做强制类型转换</div>
      </a-form-item>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ITEM_TYPES = ['str', 'int', 'float', 'bool', 'list', 'dict']

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const loopMode = ref<'count' | 'iterate'>('count')
const countSource = ref<'fixed' | 'context'>('fixed')
const countContextVar = ref<string | undefined>(undefined)

watch(d, (data) => {
  if (!data || data.type !== 'loop') return
  if (!data.params) data.params = {}

  if (data.params.mode === 'iterate') {
    loopMode.value = 'iterate'
    if (!data.params.item_type) data.params.item_type = 'str'
    if (!('item_var' in data.params)) data.params.item_var = ''
  } else {
    loopMode.value = 'count'
    const countVal = data.params?.count !== undefined && data.params?.count !== null
      ? String(data.params.count)
      : ''
    const tplM = countVal.match(/^\{\{([^}]+)\}\}$/)
    if (countVal.startsWith('$') || tplM) {
      countSource.value = 'context'
      countContextVar.value = tplM ? tplM[1].trim() : countVal.slice(1)
    } else {
      countSource.value = 'fixed'
      countContextVar.value = undefined
    }
  }
}, { immediate: true })

function update() { ctx.emitUpdate() }

function onModeChange() {
  if (loopMode.value === 'count') {
    d.value.params = { count: 1 }
  } else {
    d.value.params = { mode: 'iterate', iter_var: undefined, item_var: '', item_type: 'str' }
  }
  countSource.value = 'fixed'
  countContextVar.value = undefined
  update()
}

function onCountSourceChange() {
  countContextVar.value = undefined
  d.value.params.count = undefined
  update()
}

function onCountContextVarSelect(varName: string | undefined) {
  countContextVar.value = varName
  d.value.params.count = varName ? `{{${varName}}}` : undefined
  update()
}
</script>

<style scoped>
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; flex-shrink: 0; }
.ctx-dot.certain { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
.ctx-warn { font-size: 10px; color: #faad14; margin-left: 6px; vertical-align: middle; }
</style>
