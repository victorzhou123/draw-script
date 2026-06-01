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
  PrinterOutlined,
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
  PrinterOutlined,
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

// Loop: in=bottom, out=top, exit=right
const PORTS_LOOP = {
  groups: {
    in:   labeledGroup('bottom', { dy: 14,  textAnchor: 'middle' }),
    loop: labeledGroup('top',    { dy: -10, textAnchor: 'middle' }),
    exit: labeledGroup('right',  { dx: 10,  textAnchor: 'start',  dy: 4 }),
  },
  items: [
    { group: 'in',   id: 'in',   attrs: { labelText: { text: 'in' } } },
    { group: 'loop', id: 'loop', attrs: { labelText: { text: 'out' } } },
    { group: 'exit', id: 'exit', attrs: { labelText: { text: 'exit' } } },
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
  { shape: 'node-webhook',    icon: 'LinkOutlined',        label: 'Webhook',    w: 120, h: 60  },
  { shape: 'node-compute',    icon: 'CodeOutlined',        label: 'Compute',    w: 120, h: 60  },
  { shape: 'node-script',     icon: 'ApartmentOutlined',   label: 'Script',     w: 120, h: 60  },
  { shape: 'node-watch',      icon: 'PrinterOutlined',     label: 'Watch',      w: 120, h: 60  },
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
