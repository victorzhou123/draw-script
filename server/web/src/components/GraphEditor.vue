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
import { copyNodes, getClipboard } from '@/stores/clipboardStore'
import { message } from 'ant-design-vue'

registerNodes()

const emit = defineEmits<{
  (e: 'nodeSelected', node: any): void
  (e: 'edgeSelected', edge: any): void
  (e: 'selectionCleared'): void
  (e: 'graphChanged'): void
  (e: 'nodeContextMenu', payload: { id: string; data: any; clientX: number; clientY: number }): void
}>()

const containerEl = ref<HTMLElement>()
const graph = shallowRef<Graph>()
let contextMenuHandler: ((e: MouseEvent) => void) | null = null
const dnd = shallowRef<Dnd>()
const executionStore = useExecutionStore()
const isLoadingGraph = ref(false)

// Track last mouse position over the canvas for paste placement
const lastMousePos = { x: 0, y: 0 }
let mouseMoveHandler: ((e: MouseEvent) => void) | null = null

const hasPortLabel = (node: any, portId: string) =>
  node.getPort(portId)?.attrs?.labelText?.text !== undefined

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Space' || e.code === 'Space') {
    graph.value?.disableRubberband()
    return
  }

  const el = e.target as HTMLElement
  const inInput = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable

  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'z') {
    if (inInput) return
    e.preventDefault()
    graph.value?.undo()
    return
  }

  if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
    if (inInput) return
    e.preventDefault()
    graph.value?.redo()
    return
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
    if (inInput) return
    const nodes = (graph.value?.getSelectedCells() ?? []).filter(c => c.isNode())
    if (!nodes.length) return
    copyNodes(nodes.map(node => ({
      shape: (node as any).shape as string,
      position: (node as any).getPosition(),
      size: (node as any).getSize(),
      data: JSON.parse(JSON.stringify((node as any).getData() ?? {})),
    })))
    message.success(`已复制 ${nodes.length} 个节点`, 1.5)
    return
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
    if (inInput) return
    const clips = getClipboard()
    if (!clips.length || !graph.value) return
    e.preventDefault()

    const centroid = {
      x: clips.reduce((s, n) => s + n.position.x + n.size.width / 2, 0) / clips.length,
      y: clips.reduce((s, n) => s + n.position.y + n.size.height / 2, 0) / clips.length,
    }
    const target = graph.value.clientToLocal(lastMousePos)

    const newNodes = clips.map(n => {
      return graph.value!.addNode({
        shape: n.shape,
        x: target.x + (n.position.x - centroid.x),
        y: target.y + (n.position.y - centroid.y),
        width: n.size.width,
        height: n.size.height,
        data: JSON.parse(JSON.stringify(n.data)),
      })
    })

    graph.value.cleanSelection()
    graph.value.select(newNodes)
    emit('graphChanged')
    return
  }

  if (e.key !== 'Delete' && e.key !== 'Backspace') return
  if (inInput) return
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

  mouseMoveHandler = (e: MouseEvent) => {
    lastMousePos.x = e.clientX
    lastMousePos.y = e.clientY
  }
  containerEl.value.addEventListener('mousemove', mouseMoveHandler)

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

  g.use(new History({
    enabled: true,
    // Port visibility toggling (hover show/hide) is purely visual — exclude from undo stack
    beforeAddCommand: (_event: string, args: any) => args?.key !== 'ports',
  }))
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

  const segmentsTool = {
    name: 'segments',
    args: {
      snapRadius: 10,
      threshold: 20,
      attrs: { width: 16, height: 8, x: -8, y: -4, rx: 3, ry: 3, fill: '#555', stroke: '#999', 'stroke-width': 1 },
    },
  }

  function showSegmentsTool(edge: any) {
    edge.removeTools()
    edge.addTools([segmentsTool])
  }

  g.on('node:mouseenter', ({ node }) => showPorts(node))
  g.on('node:mouseleave', ({ node }) => { if (portNode?.id === node.id) hidePorts() })
  g.on('blank:mousemove', hidePorts)
  g.on('edge:mouseenter', ({ edge }) => { hidePorts(); showSegmentsTool(edge) })
  g.on('edge:mouseleave', ({ edge }) => { if (!(g as any).isSelected?.(edge)) edge.removeTools() })
  g.on('edge:selected',   ({ edge }) => showSegmentsTool(edge))
  g.on('edge:unselected', ({ edge }) => edge.removeTools())

  g.on('node:click', ({ node }) => {
    g.cleanSelection()
    g.select(node)
    emit('nodeSelected', { id: node.id, data: node.getData() })
  })
  contextMenuHandler = (e: MouseEvent) => {
    if (!containerEl.value?.contains(e.target as Node)) return
    e.preventDefault()
    const graphPt = g.clientToLocal({ x: e.clientX, y: e.clientY })
    const hitNode = g.getNodes().find((n: any) => n.getBBox().containsPoint(graphPt))
    if (hitNode) {
      emit('nodeContextMenu', { id: hitNode.id, data: (hitNode as any).getData(), clientX: e.clientX, clientY: e.clientY })
    }
  }
  document.addEventListener('contextmenu', contextMenuHandler)
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
  g.on('edge:change:vertices', ({ edge }) => {
    // Switch to orth so manual vertices are respected (manhattan ignores them)
    if ((edge.getRouter() as any)?.name !== 'orth' && edge.getRouter() !== 'orth') {
      edge.setRouter('orth')
    }
    onChanged()
  })
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
  if (contextMenuHandler) document.removeEventListener('contextmenu', contextMenuHandler)
  if (mouseMoveHandler && containerEl.value)
    containerEl.value.removeEventListener('mousemove', mouseMoveHandler)
})

watch(() => executionStore.activeNodeIds, (newIds, oldIds) => {
  // Nodes newly added to the active set → start glowing
  for (const id of newIds) {
    if (!oldIds?.has(id)) {
      graph.value?.getCellById(id)?.setAttrs({ body: { filter: 'drop-shadow(0 0 6px #52c41a)' } })
    }
  }
  // Nodes removed from the active set → stop glowing
  if (oldIds) {
    for (const id of oldIds) {
      if (!newIds.has(id)) {
        graph.value?.getCellById(id)?.setAttrs({ body: { filter: 'none' } })
      }
    }
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
    // Edges with manually-set vertices use orth; all others use manhattan.
    if (cell.source !== undefined && cell.target !== undefined) {
      const hasVertices = Array.isArray(cell.vertices) && cell.vertices.length > 0
      cell.router = hasVertices ? 'orth' : 'manhattan'
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
  if (!node) return
  graph.value?.startBatch('update-node-data')
  node.setData(data, { overwrite: true })
  graph.value?.stopBatch('update-node-data')
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
