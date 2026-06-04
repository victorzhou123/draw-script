interface ClipboardNode {
  shape: string
  position: { x: number; y: number }
  size: { width: number; height: number }
  data: Record<string, any>
}

// Module-level so clipboard survives GraphEditor unmount (cross-script paste)
const clipboard: { nodes: ClipboardNode[] } = { nodes: [] }

export function copyNodes(nodes: ClipboardNode[]) {
  clipboard.nodes = nodes
}

export function getClipboard(): ClipboardNode[] {
  return clipboard.nodes
}
