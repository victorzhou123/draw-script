from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowEdge:
    id: str
    source_id: str
    target_id: str
    branch: str | None = None


@dataclass
class FlowNode:
    id: str
    node_type: str
    data: dict[str, Any] = field(default_factory=dict)
    position: dict[str, float] = field(default_factory=dict)


class FlowGraph:
    def __init__(self, nodes: dict[str, FlowNode], edges: list[FlowEdge]):
        self.nodes = nodes
        self.edges = edges
        self._out_edges: dict[str, list[FlowEdge]] = {}
        for edge in edges:
            self._out_edges.setdefault(edge.source_id, []).append(edge)

    @classmethod
    def from_x6_json(cls, flow_json: dict) -> "FlowGraph":
        cells = flow_json.get("cells", [])
        nodes: dict[str, FlowNode] = {}
        raw_edge_cells: list[dict] = []

        # First pass: collect all nodes so we can look up node types during edge parsing
        for cell in cells:
            shape = cell.get("shape", "")
            if shape == "edge" or (cell.get("source") and cell.get("target") and "label" not in cell.get("data", {})):
                raw_edge_cells.append(cell)
            else:
                cell_data = cell.get("data", {})
                node_type = cell_data.get("type") or cell_data.get("node_type") or shape
                if node_type and cell.get("id"):
                    nodes[cell["id"]] = FlowNode(
                        id=cell["id"],
                        node_type=node_type,
                        data=cell_data,
                        position=cell.get("position", {}),
                    )

        # Second pass: parse edges, using node types for backward-compat branch mapping
        edges: list[FlowEdge] = []
        for cell in raw_edge_cells:
            source = cell.get("source", {})
            target = cell.get("target", {})
            source_id = source.get("cell") if isinstance(source, dict) else str(source)
            target_id = target.get("cell") if isinstance(target, dict) else str(target)
            if source_id and target_id:
                branch = cell.get("data", {}).get("branch")
                if not branch:
                    src_port = source.get("port") if isinstance(source, dict) else None
                    if src_port and src_port not in ("in", "out"):
                        branch = src_port
                    elif src_port == "out":
                        # Backward compat: loop nodes saved with an "out" port
                        # (before the port was renamed to "loop") should still route
                        # to the loop body.
                        src_node = nodes.get(source_id)
                        if src_node and src_node.node_type == "loop":
                            branch = "loop"
                edges.append(FlowEdge(
                    id=cell.get("id", ""),
                    source_id=source_id,
                    target_id=target_id,
                    branch=branch,
                ))

        return cls(nodes, edges)

    def get_start_node(self) -> FlowNode | None:
        for node in self.nodes.values():
            if node.node_type in ("start",):
                return node
        return next(iter(self.nodes.values()), None)

    def get_next_nodes(self, node_id: str, branch: str | None = None) -> list[FlowNode]:
        out = self._out_edges.get(node_id, [])
        matched = []
        if branch is None:
            # No branching: follow unlabeled edges only
            for edge in out:
                if edge.branch is None:
                    node = self.nodes.get(edge.target_id)
                    if node:
                        matched.append(node)
        else:
            # Branch returned: follow only edges with matching label
            for edge in out:
                if edge.branch == branch:
                    node = self.nodes.get(edge.target_id)
                    if node:
                        matched.append(node)
        return matched
