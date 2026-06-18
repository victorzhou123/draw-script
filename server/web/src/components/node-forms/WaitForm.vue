<template>
  <div>
    <a-form-item label="启用超时">
      <a-switch v-model:checked="d.params.timeout_enabled" @change="onToggle()" />
    </a-form-item>
    <template v-if="d.params.timeout_enabled">
      <a-form-item label="秒数">
        <a-input-number v-model:value="d.params.timeout_seconds" :min="0" :step="1" @change="update()" />
      </a-form-item>
      <a-form-item label="毫秒 (额外)">
        <a-input-number v-model:value="d.params.timeout_ms" :min="0" :step="100" @change="update()" />
      </a-form-item>
    </template>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

function onToggle() {
  if (d.value.params.timeout_enabled) {
    if (d.value.params.timeout_seconds === undefined) d.value.params.timeout_seconds = 10
    if (d.value.params.timeout_ms === undefined) d.value.params.timeout_ms = 0
  }
  ctx.emitUpdate()
}

function update() { ctx.emitUpdate() }
</script>
