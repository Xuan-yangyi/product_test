<template>
  <div class="ai-report-content">
    <div class="head-row">
      <h1 class="report-title">{{ report?.title || 'AI 汇总分析报告' }}</h1>
      <div class="actions">
        <el-button size="small" @click="printReport">打印</el-button>
        <el-button size="small" @click="exportHtml">导出 HTML</el-button>
        <el-button v-if="showClose" size="small" type="primary" plain @click="$emit('close')">关闭</el-button>
      </div>
    </div>

    <div class="meta">
      <el-tag size="small" type="info">{{ report?.kind_label || report?.kind }}</el-tag>
      <el-tag size="small" :type="providerTagType">{{ providerLabel }}</el-tag>
      <span>生成时间：{{ createdAt }}</span>
    </div>

    <div class="stats" v-if="stats.total !== undefined">
      <div class="stat"><b>{{ stats.total }}</b><span>总数</span></div>
      <div class="stat ok"><b>{{ stats.passed }}</b><span>通过</span></div>
      <div class="stat bad"><b>{{ stats.failed }}</b><span>失败</span></div>
      <div class="stat"><b>{{ stats.pass_rate }}%</b><span>通过率</span></div>
      <div class="stat muted" v-if="stats.abnormal"><b>{{ stats.abnormal }}</b><span>异常状态</span></div>
      <div class="stat muted" v-if="stats.analyzed"><b>{{ stats.analyzed }}</b><span>分析样本</span></div>
    </div>

    <table class="groups" v-if="groups.length">
      <thead>
        <tr><th>产品线</th><th>总数</th><th>通过</th><th>失败</th><th>通过率</th></tr>
      </thead>
      <tbody>
        <tr v-for="g in groups" :key="g.model">
          <td>{{ g.model }}</td>
          <td>{{ g.total }}</td>
          <td class="ok">{{ g.passed }}</td>
          <td class="bad">{{ g.failed }}</td>
          <td>{{ g.pass_rate }}%</td>
        </tr>
      </tbody>
    </table>

    <article class="md" v-html="html"></article>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = withDefaults(defineProps<{ report: any; showClose?: boolean }>(), {
  showClose: true,
})
defineEmits<{ (e: 'close'): void }>()

const html = computed(() => renderMarkdown(props.report?.content || ''))
const stats = computed(() => props.report?.stats || {})
const groups = computed(() => props.report?.groups || [])
const providerLabel = computed(() => {
  const p = props.report?.provider
  if (p === 'claude') return 'Claude CLI'
  if (p === 'api') return 'API Key'
  return '不可用'
})
const providerTagType = computed(() => {
  const p = props.report?.provider
  return p === 'claude' ? 'success' : p === 'api' ? 'primary' : 'info'
})
const createdAt = computed(() => {
  const ts = props.report?.created_at
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN') : '-'
})

function buildHtmlDoc(): string {
  const css = `
    body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;max-width:1000px;margin:24px auto;padding:0 20px;color:#222;line-height:1.7}
    h1{font-size:24px;border-bottom:2px solid #409eff;padding-bottom:8px}
    h2{font-size:19px;margin:18px 0 8px}h3{font-size:16px}h4{font-size:14px}
    table{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px}
    th,td{border:1px solid #ccc;padding:5px 8px;text-align:left;vertical-align:top}
    th{background:#f2f6fc}
    pre{background:#f5f5f5;padding:10px;border-radius:4px;overflow:auto}
    code{background:#f0f0f0;padding:1px 4px;border-radius:3px}
    .meta{color:#666;font-size:13px;margin-bottom:12px}
    .stats{display:flex;gap:18px;margin:12px 0}
    .stats b{font-size:20px}.stats span{display:block;font-size:12px;color:#666}
    .ok{color:#67c23a}.bad{color:#f56c6c}.muted{color:#909399}
  `
  const s = stats.value
  return `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>${props.report?.title || 'AI 汇总分析报告'}</title>
<style>${css}</style></head>
<body>
<h1>${props.report?.title || 'AI 汇总分析报告'}</h1>
<div class="meta">${props.report?.kind_label || props.report?.kind || ''} · 引擎：${providerLabel.value} · 生成时间：${createdAt.value}</div>
<div class="stats">
  <div><b>${s.total ?? '-'}</b><span>总数</span></div>
  <div class="ok"><b>${s.passed ?? '-'}</b><span>通过</span></div>
  <div class="bad"><b>${s.failed ?? '-'}</b><span>失败</span></div>
  <div><b>${s.pass_rate ?? '-'}%</b><span>通过率</span></div>
</div>
${html.value}
</body></html>`
}

function exportHtml() {
  const doc = buildHtmlDoc()
  const blob = new Blob([doc], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AI分析报告_${props.report?.report_id || 'report'}.html`
  a.click()
  URL.revokeObjectURL(url)
}

/** 用隐藏 iframe 打印，避免把页面其他区域一起打印 */
function printReport() {
  const doc = buildHtmlDoc()
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  iframe.srcdoc = doc
  iframe.onload = () => {
    try {
      iframe.contentWindow?.focus()
      iframe.contentWindow?.print()
    } finally {
      setTimeout(() => iframe.remove(), 1500)
    }
  }
  document.body.appendChild(iframe)
}
</script>

<style scoped>
.ai-report-content { color: var(--text-primary); }
.head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}
.report-title {
  font-size: 20px;
  margin: 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--accent);
  flex: 1;
}
.actions { display: flex; gap: 8px; flex-shrink: 0; }
.meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.stats { display: flex; gap: 24px; margin: 12px 0 16px; flex-wrap: wrap; }
.stat b { display: block; font-size: 22px; color: var(--text-primary); }
.stat span { font-size: 12px; color: var(--text-secondary); }
.stat.ok b { color: #67c23a; }
.stat.bad b { color: #f56c6c; }
.stat.muted b { color: #909399; }
.groups { border-collapse: collapse; font-size: 13px; margin-bottom: 8px; }
.groups th, .groups td {
  border: 1px solid var(--border-color);
  padding: 4px 12px;
  text-align: left;
}
.groups th { background: rgba(255, 255, 255, 0.06); }
.groups .ok { color: #67c23a; }
.groups .bad { color: #f56c6c; }

.md { font-size: 14px; line-height: 1.8; }
.md :deep(p) { margin: 6px 0; }
.md :deep(h2), .md :deep(h3), .md :deep(h4) { margin: 18px 0 8px; color: var(--text-primary); }
.md :deep(h2) { font-size: 19px; }
.md :deep(h3) { font-size: 16px; }
.md :deep(h4) { font-size: 15px; }
.md :deep(ul), .md :deep(ol) { margin: 6px 0 6px 22px; }
.md :deep(li) { margin: 3px 0; }
.md :deep(pre.code-block) {
  background: #282c34; color: #abb2bf; padding: 12px; border-radius: 6px; overflow-x: auto;
}
.md :deep(code.inline-code) {
  background: rgba(255, 255, 255, 0.1); padding: 1px 5px; border-radius: 3px;
}
.md :deep(.md-hr) { border: none; border-top: 1px solid var(--border-color); margin: 14px 0; }
.md :deep(table.md-table) { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
.md :deep(table.md-table th), .md :deep(table.md-table td) {
  border: 1px solid var(--border-color); padding: 5px 8px; text-align: left; vertical-align: top;
}
.md :deep(table.md-table th) { background: rgba(255, 255, 255, 0.08); }
.md :deep(a) { color: #79bbff; }
</style>