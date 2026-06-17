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
import { registerNodes, NODE_DEFS } from './nodes/index'
import { useExecutionStore } from '@/stores/executionStore'
import { message } from 'ant-design-vue'

const KNOWN_SHAPES = new Set(NODE_DEFS.map(d => d.shape))

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

async function onKeyDown(e: KeyboardEvent) {
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
    const selectedCells = graph.value?.getSelectedCells() ?? []
    const selectedNodes = selectedCells.filter(c => c.isNode())
    if (!selectedNodes.length) return

    const selectedNodeIds = new Set(selectedNodes.map(n => n.id))
    const internalEdges = (graph.value?.getEdges() ?? []).filter(edge => {
      const srcId = edge.getSourceCellId()
      const tgtId = edge.getTargetCellId()
      return srcId && tgtId && selectedNodeIds.has(srcId) && selectedNodeIds.has(tgtId)
    })

    const clips = [
      ...selectedNodes.map(node => ({
        kind: 'node' as const,
        id: node.id,
        shape: (node as any).shape as string,
        position: (node as any).getPosition(),
        size: (node as any).getSize(),
        data: JSON.parse(JSON.stringify((node as any).getData() ?? {})),
      })),
      ...internalEdges.map(edge => ({
        kind: 'edge' as const,
        source: { cell: edge.getSourceCellId()!, port: edge.getSourcePortId()! },
        target: { cell: edge.getTargetCellId()!, port: edge.getTargetPortId()! },
      })),
    ]

    const json = JSON.stringify(clips)
    // navigator.clipboard requires HTTPS/localhost; fall back to execCommand for LAN access
    const writeOk = navigator.clipboard && window.isSecureContext
      ? await navigator.clipboard.writeText(json).then(() => true).catch(() => false)
      : (() => {
          const el = document.createElement('textarea')
          el.value = json
          el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
          document.body.appendChild(el)
          el.focus(); el.select()
          const ok = document.execCommand('copy')
          document.body.removeChild(el)
          return ok
        })()
    if (writeOk) message.success(`已复制 ${selectedNodes.length} 个节点`, 1.5)
    else message.error('复制失败', 2)
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

function pasteFromText(text: string) {
  let clips: any[]
  try { clips = JSON.parse(text) } catch {
    message.error('剪贴板内容不是有效的 JSON 格式', 2)
    return
  }
  if (!Array.isArray(clips)) { message.error('剪贴板数据格式不符合节点结构', 2); return }

  const nodeItems = clips.filter(item => item?.kind === 'node')
  const edgeItems = clips.filter(item => item?.kind === 'edge')
  if (nodeItems.length === 0) { message.error('剪贴板数据中没有有效节点', 2); return }
  for (const n of nodeItems) {
    if (!n.id || !KNOWN_SHAPES.has(n.shape) || !n.position || !n.size || typeof n.data !== 'object') {
      message.error('剪贴板数据格式不符合节点结构', 2); return
    }
  }
  for (const edge of edgeItems) {
    if (!edge.source?.cell || !edge.source?.port || !edge.target?.cell || !edge.target?.port) {
      message.error('剪贴板数据格式不符合节点结构', 2); return
    }
  }
  if (!graph.value) return

  const centroid = {
    x: nodeItems.reduce((s: number, n: any) => s + n.position.x + n.size.width / 2, 0) / nodeItems.length,
    y: nodeItems.reduce((s: number, n: any) => s + n.position.y + n.size.height / 2, 0) / nodeItems.length,
  }
  const target = graph.value.clientToLocal(lastMousePos)
  const idMap = new Map<string, any>()
  const newNodes = nodeItems.map((n: any) => {
    const node = graph.value!.addNode({
      shape: n.shape,
      x: target.x + (n.position.x - centroid.x),
      y: target.y + (n.position.y - centroid.y),
      width: n.size.width,
      height: n.size.height,
      data: JSON.parse(JSON.stringify(n.data)),
    })
    idMap.set(n.id, node)
    return node
  })
  const newEdges = edgeItems
    .filter((e: any) => idMap.has(e.source.cell) && idMap.has(e.target.cell))
    .map((e: any) => {
      const srcNode = idMap.get(e.source.cell)
      const edge = graph.value!.addEdge({
        source: { cell: srcNode.id, port: e.source.port },
        target: { cell: idMap.get(e.target.cell).id, port: e.target.port },
        attrs: { line: { stroke: '#8f8f8f', strokeWidth: 2, targetMarker: { name: 'block', width: 12, height: 8 } } },
        router: 'manhattan',
        connector: { name: 'rounded' },
      })
      if (srcNode.shape === 'node-condition' && (e.source.port === 'true' || e.source.port === 'false')) {
        const isTrue = e.source.port === 'true'
        edge.appendLabel({
          attrs: {
            text: { text: isTrue ? 'Yes' : 'No', fill: isTrue ? '#52c41a' : '#ff4d4f', fontSize: 11, fontWeight: 'bold' },
            rect: { fill: 'rgba(26,26,26,0.85)', stroke: 'none', rx: 3, ry: 3 },
          },
          position: { distance: 0.4 },
        })
      }
      return edge
    })
  graph.value.cleanSelection()
  graph.value.select([...newNodes, ...newEdges])
  emit('graphChanged')
}

function onPaste(e: ClipboardEvent) {
  const el = e.target as HTMLElement
  const inInput = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable
  if (inInput) return
  const text = e.clipboardData?.getData('text') ?? ''
  if (!text) return
  e.preventDefault()
  pasteFromText(text)
}

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
  document.addEventListener('keyup', onKeyUp)
  document.addEventListener('paste', onPaste)
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
          router: { name: 'manhattan', args: { padding: 4 } },
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
  document.removeEventListener('paste', onPaste)
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
      cell.router = hasVertices ? 'orth' : { name: 'manhattan', args: { padding: 4 } }
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

  // Drop cells with unregistered node shapes so one stale node doesn't crash the whole graph
  const allCells: any[] = cleaned.cells ?? []
  const validNodeIds = new Set<string>()
  for (const cell of allCells) {
    if (cell.source === undefined && KNOWN_SHAPES.has(cell.shape)) validNodeIds.add(cell.id)
  }
  cleaned.cells = allCells.filter(cell => {
    if (cell.source !== undefined) {
      // Edge: keep only if both endpoints survived
      return validNodeIds.has(cell.source?.cell) && validNodeIds.has(cell.target?.cell)
    }
    return KNOWN_SHAPES.has(cell.shape)
  })

  sanitizePorts(cleaned.cells)

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
