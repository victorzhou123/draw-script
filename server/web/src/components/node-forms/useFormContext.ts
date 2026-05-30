import type { InjectionKey, Ref, ComputedRef } from 'vue'

export interface ContextField {
  name: string
  certain: boolean
}

export interface FormContext {
  localData: Ref<any>
  contextFields: ComputedRef<ContextField[]>
  availableMarkers: ComputedRef<any[]>
  availableTemplates: ComputedRef<any[]>
  aiModels: ComputedRef<any[]>
  otherScripts: ComputedRef<any[]>
  emitUpdate: () => void
}

export const FORM_CTX: InjectionKey<FormContext> = Symbol('nodeFormContext')
