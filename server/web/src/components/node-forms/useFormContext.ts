import type { InjectionKey, Ref, ComputedRef } from 'vue'
import type { WindowBinding } from '@/services/api'

export interface ContextField {
  name: string
  certain: boolean
}

export interface FormContext {
  localData: Ref<any>
  nodeId: Ref<string>
  contextFields: ComputedRef<ContextField[]>
  availableMarkers: ComputedRef<any[]>
  availableTemplates: ComputedRef<any[]>
  aiModels: ComputedRef<any[]>
  otherScripts: ComputedRef<any[]>
  availableGlobalVars: ComputedRef<string[]>
  serviceKeys: ComputedRef<any[]>
  defaultClientWindowBinding: Ref<WindowBinding | null>
  emitUpdate: () => void
}

export const FORM_CTX: InjectionKey<FormContext> = Symbol('nodeFormContext')
