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
  (e: 'graphChanged'): void
}>()

const containerEl = ref<HTMLElement>()
const graph = shallowRef<Graph>()
const dnd = shallowRef<Dnd>()
const executionStore = useExecutionStore()
const isLoadingGraph = ref(false)

const hasPortLabel = (node: any, portId: string) =>
  node.getPort(portId)?.attrs?.labelText?.text !== undefined

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Space' || e.code === 'Space') {
    graph.value?.disableRubberband()
    return
  }
  if (e.key !== 'Delete' && e.key !== 'Backspace') return
  const el = e.target as HTMLElement
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable) return
  const cells = graph.value?.getSelectedCells() ?? []
  if (cells.length) graph.value?.removeCells(cells)
}

function onKeyUp(e: KeyboardEvent) {
  if (e.key === 'Space' || e.code === 'Space') {
    graph.value?.enableRubberband()
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
  document.addEventListener('keyup', onKeyUp)
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
      validateConnection({ sourceCell, sourcePort, targetCell, targetPort }) {
        if (!sourceCell || !targetCell) return false
        return !g.getEdges().some(edge =>
          edge.getSourceCellId() === sourceCell.id &&
          edge.getSourcePortId() === sourcePort &&
          edge.getTargetCellId() === targetCell.id &&
          edge.getTargetPortId() === targetPort
        )
      },
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
  g.use(new Selection({ enabled: true, rubberband: true, showNodeSelectionBox: true, showEdgeSelectionBox: true }))

  // Track which node currently has visible ports.
  // node:mouseleave is unreliable after a click because X6's selection box
  // overlay intercepts mouse events, so we also hide via blank:mousemove
  // and edge:mouseenter, and clear other nodes' ports on node:mouseenter.
  let portNode: any = null

  function showPorts(node: any) {
    if (portNode && portNode.id !== node.id) {
      portNode.getPorts().forEach((p: any) => {
        portNode.portProp(p.id!, 'attrs/circle/visibility', 'hidden')
        if (hasPortLabel(portNode, p.id!))
          portNode.portProp(p.id!, 'attrs/labelText/visibility', 'hidden')
      })
    }
    node.getPorts().forEach((p: any) => {
      node.portProp(p.id!, 'attrs/circle/visibility', 'visible')
      if (hasPortLabel(node, p.id!))
        node.portProp(p.id!, 'attrs/labelText/visibility', 'visible')
    })
    portNode = node
  }

  function hidePorts() {
    if (!portNode) return
    portNode.getPorts().forEach((p: any) => {
      portNode.portProp(p.id!, 'attrs/circle/visibility', 'hidden')
      if (hasPortLabel(portNode, p.id!))
        portNode.portProp(p.id!, 'attrs/labelText/visibility', 'hidden')
    })
    portNode = null
  }

  g.on('node:mouseenter', ({ node }) => showPorts(node))
  g.on('node:mouseleave', ({ node }) => { if (portNode?.id === node.id) hidePorts() })
  g.on('blank:mousemove', hidePorts)
  g.on('edge:mouseenter', hidePorts)

  g.on('node:click', ({ node }) => {
    g.cleanSelection()
    g.select(node)
    emit('nodeSelected', { id: node.id, data: node.getData() })
  })
  g.on('edge:click', ({ edge }) => {
    g.cleanSelection()
    g.select(edge)
    emit('edgeSelected', { id: edge.id, data: edge.getData() })
  })
  g.on('blank:click', () => {
    g.cleanSelection()
    emit('selectionCleared')
  })
  g.on('cell:removed', () => emit('selectionCleared'))

  const onChanged = () => { if (!isLoadingGraph.value) emit('graphChanged') }
  g.on('cell:added', onChanged)
  g.on('cell:removed', onChanged)
  g.on('node:moved', onChanged)
  g.on('edge:connected', ({ edge }) => {
    const sourceNode = edge.getSourceNode()
    const sourcePort = edge.getSourcePortId()
    edge.setLabels([])
    if (sourceNode?.shape === 'node-condition' && (sourcePort === 'true' || sourcePort === 'false')) {
      const isTrue = sourcePort === 'true'
      edge.appendLabel({
        attrs: {
          text: { text: isTrue ? 'Yes' : 'No', fill: isTrue ? '#52c41a' : '#ff4d4f', fontSize: 11, fontWeight: 'bold' },
          rect: { fill: 'rgba(26,26,26,0.85)', stroke: 'none', rx: 3, ry: 3 },
        },
        position: { distance: 0.4 },
      })
    }
    onChanged()
  })

  graph.value = g
  dnd.value = new Dnd({ target: g, scaled: false })

})

onBeforeUnmount(() => {
  graph.value?.dispose()
  document.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('keyup', onKeyUp)
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

function sanitizePorts(cells: any[]) {
  for (const cell of cells) {
    // Strip port groups so registered shape positions are always used
    if (cell.ports?.groups) delete cell.ports.groups
    for (const port of cell.ports?.items ?? []) {
      if (port.attrs?.circle)    delete port.attrs.circle.visibility
      if (port.attrs?.labelText) delete port.attrs.labelText.visibility
    }
  }
}

function getJSON() {
  const json = graph.value?.toJSON() ?? { cells: [] }
  sanitizePorts((json as any).cells ?? [])
  return json
}

function loadJSON(json: object) {
  // Deep-clone to avoid mutating the caller's object, then strip stored port
  // groups so X6 falls back to the registered shape's position/markup.
  const cleaned = JSON.parse(JSON.stringify(json))
  sanitizePorts(cleaned.cells ?? [])

  isLoadingGraph.value = true
  graph.value?.fromJSON(cleaned)
  graph.value?.centerContent()
  // Reset port visibility after load.
  graph.value?.getNodes().forEach(node => {
    node.getPorts().forEach(port => {
      node.portProp(port.id!, 'attrs/circle/visibility', 'hidden')
      if (hasPortLabel(node, port.id!))
        node.portProp(port.id!, 'attrs/labelText/visibility', 'hidden')
    })
  })
  setTimeout(() => { isLoadingGraph.value = false }, 100)
}

function updateNodeData(nodeId: string, data: any) {
  const node = graph.value?.getCellById(nodeId)
  node?.setData(data, { overwrite: true })
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

defineExpose({ getJSON, loadJSON, undo, redo, startDragNode, updateNodeData })
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
