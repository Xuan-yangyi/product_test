/**
 * 轻量 Markdown 渲染（先转义 HTML，再按行解析：标题/列表/表格/代码/粗体）
 * 适用于 AI 分析报告展示，避免引入额外依赖。
 */
function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inline(s: string): string {
  let h = esc(s)
  h = h.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  return h
}

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const out: string[] = []
  let i = 0
  let listType: 'ul' | 'ol' | null = null

  const closeList = () => {
    if (listType) {
      out.push(listType === 'ul' ? '</ul>' : '</ol>')
      listType = null
    }
  }

  const openList = (t: 'ul' | 'ol') => {
    if (listType !== t) {
      closeList()
      out.push(t === 'ul' ? '<ul>' : '<ol>')
      listType = t
    }
  }

  while (i < lines.length) {
    const line = lines[i]

    // 代码块
    if (/^```/.test(line.trim())) {
      closeList()
      const buf: string[] = []
      i++
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        buf.push(lines[i])
        i++
      }
      i++ // skip closing ```
      out.push(`<pre class="code-block"><code>${esc(buf.join('\n'))}</code></pre>`)
      continue
    }

    // 标题
    let m = /^(#{1,4})\s+(.*)$/.exec(line)
    if (m) {
      closeList()
      const level = m[1].length
      out.push(`<h${level + 1} class="md-h${level + 1}">${inline(m[2])}</h${level + 1}>`)
      i++
      continue
    }

    // 分隔线
    if (/^\s*---+\s*$/.test(line)) {
      closeList()
      out.push('<hr class="md-hr" />')
      i++
      continue
    }

    // 表格：当前行以 | 开头，下一行是分隔行
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      closeList()
      const parseRow = (r: string) =>
        r.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => inline(c.trim()))
      const header = parseRow(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        rows.push(parseRow(lines[i]))
        i++
      }
      let table = '<table class="md-table"><thead><tr>'
      table += header.map(h => `<th>${h}</th>`).join('')
      table += '</tr></thead><tbody>'
      for (const r of rows) {
        table += '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>'
      }
      table += '</tbody></table>'
      out.push(table)
      continue
    }

    // 无序列表
    m = /^\s*[-*]\s+(.*)$/.exec(line)
    if (m) {
      openList('ul')
      out.push(`<li>${inline(m[1])}</li>`)
      i++
      continue
    }

    // 有序列表
    m = /^\s*\d+\.\s+(.*)$/.exec(line)
    if (m) {
      openList('ol')
      out.push(`<li>${inline(m[1])}</li>`)
      i++
      continue
    }

    // 空行
    if (!line.trim()) {
      closeList()
      i++
      continue
    }

    // 普通段落
    closeList()
    out.push(`<p>${inline(line)}</p>`)
    i++
  }
  closeList()
  return out.join('\n')
}