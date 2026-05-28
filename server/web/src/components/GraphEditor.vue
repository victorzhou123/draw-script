<template>
  <div class="graph-editor-wrap">
    <div ref="containerEl" class="graph-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, onMounted, onBeforeUnmount, watch } from 'vue'
import { Graph } from '@antv/x6'
import { Dnd } from '@antv/x6-plugin-dnd'
import { History } from '@antv/x6-plugin-history'
import { Snapline } from '@antv/x6-plugin-snapline'
import { Selection } from '@antv/x6-plugin-selection'
import { registerNodes } from './nodes/index'
import { useExecutionStore } from '@/stores/executionStore'

registerNodes()

const emit = defineEmits<{
  (e: 'nodeSelected', node: any): void
  (e: 'edgeSelected', edge: any): void
  (e: 'selectionCleared'): void
}>()

const containerEl = ref<HTMLElement>()
const graph = shallowRef<Graph>()
const dnd = shallowRef<Dnd>()
const executionStore = useExecutionStore()

onMounted(() => {
  if (!containerEl.value) return

  const g = new Graph({
    container: containerEl.value,
    autoResize: true,
    panning: { enabled: true, modifiers: 'space' },
    mousewheel: { enabled: true, modifiers: 'ctrl' },
    grid: { visible: true, size: 10, type: 'dot', args: { color: '#333333', thickness: 1 } },
    background: { color: '#1a1a1a' },
    connecting: {
      allowBlank: false,
      allowLoop: false,
      snap: { radius: 20 },
      createEdge() {
        return g.createEdge({
          attrs: {
            line: {
              stroke: '#8f8f8f',
              strokeWidth: 2,
              targetMarker: { name: 'block', width: 12, height: 8 },
            },
          },
          router: 'manhattan',
          connector: { name: 'rounded' },
        })
      },
    },
    highlighting: {
      magnetAdsorbed: {
        name: 'stroke',
        args: { attrs: { fill: '#5F95FF', stroke: '#5F95FF' } },
      },
    },
  })

  g.use(new History({ enabled: true }))
  g.use(new Snapline({ enabled: true }))
  g.use(new Selection({ enabled: true, rubberband: true, showNodeSelectionBox: true }))

  // Show/hide ports on node hover
  g.on('node:mouseenter', ({ node }) => {
    node.getPorts().forEach(port => {
      node.portProp(port.id!, 'attrs/circle/visibility', 'visible')
    })
  })
  g.on('node:mouseleave', ({ node }) => {
    node.getPorts().forEach(port => {
      node.portProp(port.id!, 'attrs/circle/visibility', 'hidden')
    })
  })

  g.on('node:click', ({ node }) => emit('nodeSelected', { id: node.id, data: node.getData() }))
  g.on('edge:click', ({ edge }) => emit('edgeSelected', { id: edge.id, data: edge.getData() }))
  g.on('blank:click', () => emit('selectionCleared'))
  g.on('cell:removed', () => emit('selectionCleared'))

  graph.value = g
  dnd.value = new Dnd({ target: g, scaled: false })
})

onBeforeUnmount(() => {
  graph.value?.dispose()
})

watch(() => executionStore.activeNodeId, (nodeId, prevNodeId) => {
  if (prevNodeId) {
    const prev = graph.value?.getCellById(prevNodeId)
    prev?.setAttrs({ body: { filter: 'none' } })
  }
  if (nodeId) {
    const cell = graph.value?.getCellById(nodeId)
    cell?.setAttrs({ body: { filter: 'drop-shadow(0 0 6px #52c41a)' } })
  }
})

function getJSON() {
  return graph.value?.toJSON() ?? { cells: [] }
}

function loadJSON(json: object) {
  graph.value?.fromJSON(json)
  graph.value?.centerContent()
}

function undo() { graph.value?.undo() }
function redo() { graph.value?.redo() }

function startDragNode(shape: string, data: object, event: MouseEvent) {
  if (!dnd.value || !graph.value) return
  const node = graph.value.createNode({
    shape,
    data: { type: shape.replace('node-', ''), ...data },
  })
  dnd.value.start(node, event)
}

defineExpose({ getJSON, loadJSON, undo, redo, startDragNode })
</script>

<style scoped>
.graph-editor-wrap {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #1a1a1a;
}
.graph-container {
  width: 100%;
  height: 100%;
}
</style>
