import type { Component } from 'vue'
import {
  Platform, Setting, Monitor, VideoCamera,
  Sunny, Aim, Printer, Cpu, MagicStick,
  Brush, Search, Histogram, Link, Refresh,
} from '@element-plus/icons-vue'

export const DEVICE_TYPE_ICON_MAP: Record<string, Component> = {
  'reflow-oven': Platform,
  'injection-molder': Setting,
  'pick-and-place': VideoCamera,
  'wave-solder': Sunny,
  'cnc-drill': Aim,
  '3d-printer': Printer,
  'testing-station': Monitor,
  'laser-cutter': MagicStick,
  'coating-machine': Brush,
  'xray-inspection': Search,
  'oven-curing': Histogram,
  'wire-bonder': Link,
  'ultrasonic-cleaner': Refresh,
}

export const DEVICE_TYPE_LABELS: Record<string, string> = {
  'reflow-oven': '回流焊',
  'injection-molder': '注塑机',
  'pick-and-place': '贴片机',
  'wave-solder': '波峰焊',
  'cnc-drill': 'CNC钻孔',
  '3d-printer': '3D打印机',
  'testing-station': '测试站',
  'laser-cutter': '激光切割',
  'coating-machine': '涂覆机',
  'xray-inspection': 'X光检测',
  'oven-curing': '固化炉',
  'wire-bonder': '引线键合',
  'ultrasonic-cleaner': '超声清洗',
}

export function deviceIcon(type: string): Component {
  return DEVICE_TYPE_ICON_MAP[type] || Cpu
}

export function deviceLabel(type: string): string {
  return DEVICE_TYPE_LABELS[type] || type
}
