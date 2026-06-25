import { register } from '@antv/x6-vue-shape'
import { h } from 'vue'
import type { Component } from 'vue'
import BaseNode from './BaseNode.vue'
import {
  CaretRightOutlined,
  PoweroffOutlined,
  ThunderboltOutlined,
  CameraOutlined,
  EyeOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  GlobalOutlined,
  LinkOutlined,
  CodeOutlined,
  ApartmentOutlined,
  NodeCollapseOutlined,
  DatabaseOutlined,
  EditOutlined,
  CloudDownloadOutlined,
  FilterOutlined,
} from '@ant-design/icons-vue'

export const ICON_MAP: Record<string, Component> = {
  CaretRightOutlined,
  PoweroffOutlined,
  ThunderboltOutlined,
  CameraOutlined,
  EyeOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  GlobalOutlined,
  LinkOutlined,
  CodeOutlined,
  ApartmentOutlined,
  NodeCollapseOutlined,
  DatabaseOutlined,
  EditOutlined,
  CloudDownloadOutlined,
  FilterOutlined,
}

// Port appearance: hidden by default, revealed by graph hover events
const PORT_CIRCLE_ATTRS = {
  r: 5,
  magnet: true,
  stroke: '#1890ff',
  strokeWidth: 1.5,
  fill: '#141414',
  visibility: 'hidden',
}

const PORT_ATTRS = { circle: PORT_CIRCLE_ATTRS }

// Build a labeled port group: circle + text label positioned outside the node
function labeledGroup(position: string, labelStyle: Record<string, unknown>) {
  return {
    position,
    markup: [
      { tagName: 'circle', selector: 'circle' },
      { tagName: 'text',   selector: 'labelText' },
    ],
    attrs: {
      circle: PORT_CIRCLE_ATTRS,
      labelText: {
        fontSize: 9,
        fill: '#888',
        visibility: 'hidden',
        ...labelStyle,
      },
    },
  }
}

// Common in+out ports (top/bottom)
const PORTS_DEFAULT = {
  groups: {
    in:  { position: 'top',    attrs: PORT_ATTRS },
    out: { position: 'bottom', attrs: PORT_ATTRS },
  },
  items: [
    { group: 'in',  id: 'in'  },
    { group: 'out', id: 'out' },
  ],
}

// Start: output only (bottom)
const PORTS_START = {
  groups: { out: { position: 'bottom', attrs: PORT_ATTRS } },
  items: [{ group: 'out', id: 'out' }],
}

// End: input only (top)
const PORTS_END = {
  groups: { in: { position: 'top', attrs: PORT_ATTRS } },
  items: [{ group: 'in', id: 'in' }],
}

// Condition: input top, true=right, false=left
const PORTS_CONDITION = {
  groups: {
    in:    labeledGroup('top',   { dy: -10, textAnchor: 'middle' }),
    true:  labeledGroup('right', { dx: 10,  textAnchor: 'start',  dy: 4 }),
    false: labeledGroup('left',  { dx: -10, textAnchor: 'end',    dy: 4 }),
  },
  items: [
    { group: 'in',    id: 'in',    attrs: { labelText: { text: 'in' } } },
    { group: 'true',  id: 'true',  attrs: { labelText: { text: 'true' } } },
    { group: 'false', id: 'false', attrs: { labelText: { text: 'false' } } },
  ],
}

// Loop: 4 symmetric flex ports — any side accepts in or out edges.
// Branch (out vs exit) is stored on each outgoing edge via the popup in GraphEditor.
// Each port gets its own group so x6 can resolve the position correctly (position
// must live in the group definition, not in the item).
// Explicit markup (circle only) is required on each new group: when a registration
// mixes labeled groups (markup: circle+text) with plain groups (no markup), x6 falls
// back to the labeled markup for all ports, producing a stray text node at (0,0).
// Legacy groups (in/loop/exit) are retained so old saved scripts still render correctly.
const PORT_CIRCLE_MARKUP = [{ tagName: 'circle', selector: 'circle' }]
const PORTS_LOOP = {
  groups: {
    top:    { position: 'top',    markup: PORT_CIRCLE_MARKUP, attrs: { circle: PORT_CIRCLE_ATTRS } },
    bottom: { position: 'bottom', markup: PORT_CIRCLE_MARKUP, attrs: { circle: PORT_CIRCLE_ATTRS } },
    left:   { position: 'left',   markup: PORT_CIRCLE_MARKUP, attrs: { circle: PORT_CIRCLE_ATTRS } },
    right:  { position: 'right',  markup: PORT_CIRCLE_MARKUP, attrs: { circle: PORT_CIRCLE_ATTRS } },
    // Legacy groups — kept for backward compat with old saved JSON
    in:   labeledGroup('bottom', { dy: 14,  textAnchor: 'middle' }),
    loop: labeledGroup('top',    { dy: -10, textAnchor: 'middle' }),
    exit: labeledGroup('right',  { dx: 10,  textAnchor: 'start',  dy: 4 }),
  },
  items: [
    { group: 'top',    id: 'top'    },
    { group: 'bottom', id: 'bottom' },
    { group: 'left',   id: 'left'   },
    { group: 'right',  id: 'right'  },
  ],
}

function portsFor(shape: string) {
  if (shape === 'node-start')     return PORTS_START
  if (shape === 'node-end')       return PORTS_END
  if (shape === 'node-condition') return PORTS_CONDITION
  if (shape === 'node-loop')      return PORTS_LOOP
  return PORTS_DEFAULT
}

const NODE_DEFS = [
  { shape: 'node-start',      icon: 'CaretRightOutlined',  label: 'Start',      w: 80,  h: 80  },
  { shape: 'node-end',        icon: 'PoweroffOutlined',    label: 'End',        w: 80,  h: 80  },
  { shape: 'node-action',     icon: 'ThunderboltOutlined', label: 'Action',     w: 120, h: 60  },
  { shape: 'node-screenshot', icon: 'CameraOutlined',      label: 'Screenshot', w: 120, h: 60  },
  { shape: 'node-vision',     icon: 'EyeOutlined',         label: 'Vision',     w: 120, h: 60  },
  { shape: 'node-condition',  icon: 'BranchesOutlined',    label: 'Condition',  w: 67,  h: 67  },
  { shape: 'node-delay',      icon: 'ClockCircleOutlined', label: 'Delay',      w: 120, h: 60  },
  { shape: 'node-loop',       icon: 'SyncOutlined',        label: 'Loop',       w: 120, h: 60  },
  { shape: 'node-wait',       icon: 'NodeCollapseOutlined',label: 'Wait',       w: 120, h: 60  },
  { shape: 'node-http',       icon: 'GlobalOutlined',      label: 'HTTP',       w: 120, h: 60  },
  { shape: 'node-compute',    icon: 'CodeOutlined',        label: 'Compute',    w: 120, h: 60  },
  { shape: 'node-script',     icon: 'ApartmentOutlined',   label: 'Script',     w: 120, h: 60  },
  { shape: 'node-global-var',    icon: 'DatabaseOutlined',      label: 'Global Var',    w: 120, h: 60  },
  { shape: 'node-context-edit', icon: 'EditOutlined',           label: 'Context Edit',  w: 120, h: 60  },
  { shape: 'node-crawl',        icon: 'CloudDownloadOutlined',  label: 'Crawl',         w: 120, h: 60  },
  { shape: 'node-parse',        icon: 'FilterOutlined',         label: 'Parse',         w: 120, h: 60  },
]

export function registerNodes() {
  for (const def of NODE_DEFS) {
    register({
      shape: def.shape,
      width: def.w,
      height: def.h,
      ports: portsFor(def.shape),
      component: {
        render() {
          return h(BaseNode, {
            icon: def.icon,
            label: def.label,
            nodeType: def.shape.replace('node-', ''),
          })
        },
      },
    })
  }
}

export { NODE_DEFS }
