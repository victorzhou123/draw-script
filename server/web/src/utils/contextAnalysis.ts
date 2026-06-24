export interface ContextField {
  name: string
  certain: boolean  // false = 只在某些分支存在
}

export interface ContextStep {
  nodeId: string
  nodeType: string
  nodeLabel: string
  addedFields: ContextField[]
}

// ── 节点贡献的 context 字段 ────────────────────────────────────────────────

function nodeContributions(data: any): string[] {
  if (!data) return []
  if (data.type === 'start' && Array.isArray(data.fields))
    return data.fields.map((f: any) => f.name).filter(Boolean)
  if ((data.type === 'vision' || data.type === 'screenshot') && data.result_var?.trim())
    return [data.result_var.trim()]
  if (data.type === 'compute' && Array.isArray(data.output_fields))
    return data.output_fields.filter(Boolean)
  if (data.type === 'script' && Array.isArray(data.output_mappings) && data.output_mappings.length)
    return data.output_mappings.map((m: any) => m.to?.trim()).filter(Boolean)
  if (data.type === 'context-edit' && Array.isArray(data.params?.operations)) {
    return data.params.operations
      .filter((op: any) => op.op === 'set' || op.op === 'rename')
      .map((op: any) => op.op === 'set' ? op.key?.trim() : op.to?.trim())
      .filter(Boolean)
  }
  if ((data.type === 'crawl' || data.type === 'parse') && data.output_var?.trim())
    return [data.output_var.trim()]
  return []
}

// ── 辅助 ──────────────────────────────────────────────────────────────────

function setsEqual(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false
  for (const x of a) if (!b.has(x)) return false
  return true
}

// ── 图解析 ─────────────────────────────────────────────────────────────────

function buildGraph(cells: any[]) {
  const nodeMap = new Map<string, any>()
  const fwd = new Map<string, Set<string>>()  // node → successors
  const bwd = new Map<string, Set<string>>()  // node → predecessors

  for (const cell of cells) {
    const s = cell.source?.cell as string | undefined
    const t = cell.target?.cell as string | undefined
    if (s && t) {
      if (!fwd.has(s)) fwd.set(s, new Set())
      fwd.get(s)!.add(t)
      if (!bwd.has(t)) bwd.set(t, new Set())
      bwd.get(t)!.add(s)
    } else if (cell.id) {
      nodeMap.set(cell.id, cell)
    }
  }

  return { nodeMap, fwd, bwd }
}

// ── 拓扑排序（Kahn 算法，有环时返回可排序的部分） ─────────────────────────

function topoSort(
  nodeMap: Map<string, any>,
  fwd: Map<string, Set<string>>,
  bwd: Map<string, Set<string>>,
): string[] {
  const deg = new Map<string, number>()
  for (const id of nodeMap.keys()) deg.set(id, bwd.get(id)?.size ?? 0)

  const queue = [...nodeMap.keys()].filter(id => deg.get(id) === 0)
  const order: string[] = []

  while (queue.length) {
    const id = queue.shift()!
    order.push(id)
    for (const s of fwd.get(id) ?? []) {
      const d = (deg.get(s) ?? 1) - 1
      deg.set(s, d)
      if (d === 0) queue.push(s)
    }
  }

  return order
}

// ── 单节点数据流计算 ───────────────────────────────────────────────────────
// 只使用 availPreds（已计算的前驱）；返回值表示结果是否发生变化

function computeNodeFlow(
  id: string,
  availPreds: string[],
  contrib: string[],
  certOut: Map<string, Set<string>>,
  allOut: Map<string, Set<string>>,
): boolean {
  let cIn: Set<string>, aIn: Set<string>

  if (!availPreds.length) {
    cIn = new Set()
    aIn = new Set()
  } else {
    cIn = new Set(certOut.get(availPreds[0]) ?? [])
    for (const p of availPreds.slice(1)) {
      const cs = certOut.get(p) ?? new Set<string>()
      for (const f of [...cIn]) if (!cs.has(f)) cIn.delete(f)
    }
    aIn = new Set()
    for (const p of availPreds) for (const f of (allOut.get(p) ?? [])) aIn.add(f)
  }

  const newCert = new Set([...cIn, ...contrib])
  const newAll  = new Set([...aIn,  ...contrib])

  const prevCert = certOut.get(id)
  const prevAll  = allOut.get(id)
  const changed = !prevCert || !prevAll || !setsEqual(prevCert, newCert) || !setsEqual(prevAll, newAll)
  if (changed) {
    certOut.set(id, newCert)
    allOut.set(id,  newAll)
  }
  return changed
}

// ── 数据流分析（核心） ─────────────────────────────────────────────────────
// Pass 1：拓扑排序后的 DAG 部分，正常前向传播
// Pass 2：环中节点，用"已计算的前驱"迭代至不动点
//         - certOut 单调不增（交集只会缩小或不变）
//         - allOut  单调不减（并集只会扩大或不变）
//         → 必然在有限步内收敛

function runDataflow(cells: any[]) {
  const { nodeMap, fwd, bwd } = buildGraph(cells)
  const order = topoSort(nodeMap, fwd, bwd)
  const inOrder = new Set(order)

  const certOut = new Map<string, Set<string>>()
  const allOut  = new Map<string, Set<string>>()

  // Pass 1: DAG 部分
  for (const id of order) {
    const preds = [...(bwd.get(id) ?? [])]
    const contrib = nodeContributions(nodeMap.get(id)?.data)
    computeNodeFlow(id, preds, contrib, certOut, allOut)
  }

  // Pass 2: 环中节点不动点迭代
  const cycleNodes = [...nodeMap.keys()].filter(id => !inOrder.has(id))
  if (cycleNodes.length > 0) {
    for (let iter = 0; iter < 20; iter++) {
      let changed = false
      for (const id of cycleNodes) {
        const preds = [...(bwd.get(id) ?? [])]
        // 只使用已计算出结果的前驱，跳过尚未处理的环内回边
        const availPreds = preds.filter(p => certOut.has(p))
        if (!availPreds.length) continue
        const contrib = nodeContributions(nodeMap.get(id)?.data)
        if (computeNodeFlow(id, availPreds, contrib, certOut, allOut)) changed = true
      }
      if (!changed) break
    }
    // 完全孤立的环（无任何外部入口）：仅含自身贡献
    for (const id of cycleNodes) {
      if (!certOut.has(id)) {
        const contrib = nodeContributions(nodeMap.get(id)?.data)
        certOut.set(id, new Set(contrib))
        allOut.set(id,  new Set(contrib))
      }
    }
  }

  return { nodeMap, fwd, bwd, order: [...order, ...cycleNodes], certOut, allOut }
}

// ── 公共 API ───────────────────────────────────────────────────────────────

/**
 * 返回进入 targetId 节点时可用的 context 字段及其确定性。
 * certain=false 表示该字段只在某些分支存在（条件分支未合并）。
 */
export function analyzeContextAtNode(cells: any[], targetId: string): ContextField[] {
  const { nodeMap, bwd, certOut, allOut } = runDataflow(cells)
  if (!nodeMap.has(targetId)) return []

  const preds = [...(bwd.get(targetId) ?? [])]
  if (!preds.length) return []

  let cIn = new Set(certOut.get(preds[0]) ?? [])
  for (const p of preds.slice(1)) {
    const cs = certOut.get(p) ?? new Set<string>()
    for (const f of [...cIn]) if (!cs.has(f)) cIn.delete(f)
  }

  const aIn = new Set<string>()
  for (const p of preds) for (const f of (allOut.get(p) ?? [])) aIn.add(f)

  return [...aIn]
    .map(name => ({ name, certain: cIn.has(name) }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

/**
 * 返回到达 targetId 节点前的 context 演变时间线。
 * 只包含 targetId 的上游节点，字段确定性与 analyzeContextAtNode 完全一致。
 */
export function analyzeContextEvolution(cells: any[], targetId: string): ContextStep[] {
  const { nodeMap, bwd, certOut, allOut, order } = runDataflow(cells)

  if (!nodeMap.has(targetId)) return []

  // BFS 向上收集所有前驱节点（visit 检查防止环导致的无限循环）
  const upstream = new Set<string>()
  const queue = [...(bwd.get(targetId) ?? [])]
  while (queue.length) {
    const id = queue.shift()!
    if (upstream.has(id)) continue
    upstream.add(id)
    for (const p of (bwd.get(id) ?? [])) if (!upstream.has(p)) queue.push(p)
  }

  if (!upstream.size) return []

  // 与 analyzeContextAtNode 完全相同的入口分析（确保标记一致）
  const preds = [...(bwd.get(targetId) ?? [])]
  let cIn = new Set(certOut.get(preds[0]) ?? [])
  for (const p of preds.slice(1)) {
    const cs = certOut.get(p) ?? new Set<string>()
    for (const f of [...cIn]) if (!cs.has(f)) cIn.delete(f)
  }
  const aIn = new Set<string>()
  for (const p of preds) for (const f of (allOut.get(p) ?? [])) aIn.add(f)

  // 按拓扑顺序，只展示能到达 targetId 且有字段贡献的前驱节点
  const steps: ContextStep[] = []
  for (const id of order) {
    if (!upstream.has(id)) continue
    const contrib = nodeContributions(nodeMap.get(id)?.data).filter(f => aIn.has(f))
    if (!contrib.length) continue
    const node = nodeMap.get(id)
    steps.push({
      nodeId: id,
      nodeType: node?.data?.type ?? '',
      nodeLabel: node?.data?.label || node?.data?.type || '',
      addedFields: contrib.map(name => ({ name, certain: cIn.has(name) })),
    })
  }

  return steps
}
