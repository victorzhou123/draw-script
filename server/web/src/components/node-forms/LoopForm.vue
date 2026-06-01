<template>
  <a-form-item label="最大循环次数">
    <a-input-number v-model:value="d.params.count" :min="1" :max="1000" @change="update()" />
  </a-form-item>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
function update() { ctx.emitUpdate() }
</script>
