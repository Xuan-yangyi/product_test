<template>
  <div class="ai-chat">
    <div class="chat-messages" ref="msgContainer">
      <div v-if="messages.length === 0" class="chat-empty">
        <div class="empty-icon">🤖</div>
        <p>AI 老化测试分析助手</p>
        <p class="empty-hint">点击下方按钮分析日志，或直接输入分析需求</p>
      </div>
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['chat-msg', msg.role === 'user' ? 'msg-user' : 'msg-ai']"
      >
        <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="msg-bubble">
          <div class="msg-content" v-html="renderMarkdown(msg.content)"></div>
          <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
        </div>
      </div>
      <div v-if="loading" class="chat-msg msg-ai">
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble">
          <div class="msg-content typing">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-actions">
      <el-button size="small" @click="analyzeLogs" :loading="loading && analyzingMode === 'deepseek'" type="primary">
        📊 快速分析
      </el-button>
      <el-button size="small" @click="claudeAnalyze" :loading="loading && analyzingMode === 'claude'" type="success">
        🧠 深度分析 (Claude)
      </el-button>
      <el-button size="small" @click="analyzeErrors" :loading="loading && analyzingMode === 'errors'" type="warning">
        🔍 分析错误
      </el-button>
      <el-button size="small" @click="clearChat" :disabled="loading">清空对话</el-button>
    </div>

    <div class="chat-input">
      <el-input
        v-model="inputText"
        placeholder="输入分析需求，例如：分析温度是否正常..."
        @keyup.enter="sendMessage"
        :disabled="loading"
        type="textarea"
        :rows="2"
        resize="none"
      />
      <el-button
        type="primary"
        @click="sendMessage"
        :loading="loading"
        :disabled="!inputText.trim()"
        style="margin-top: 8px; width: 100%"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/api/http'

const props = defineProps<{
  testId: string
}>()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const analyzingMode = ref('')  // 'deepseek' | 'claude' | 'errors'
const msgContainer = ref<HTMLElement>()

function scrollToBottom() {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  })
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 代码块 ```...```
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="code-block"><code>${code.trim()}</code></pre>`
  })

  // 行内代码 `...`
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // 粗体 **...**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

  // 标题 ### ...
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')

  // 无序列表
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')

  // 有序列表
  html = html.replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>')

  // 换行
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')

  return `<p>${html}</p>`
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text, timestamp: Date.now() })
  inputText.value = ''
  scrollToBottom()

  loading.value = true
  try {
    const res: any = await http.post('/ai/chat', {
      messages: messages.value.map(m => ({ role: m.role, content: m.content })),
      test_id: props.testId,
    })
    messages.value.push({
      role: 'assistant',
      content: res.reply || '（无回复）',
      timestamp: Date.now(),
    })
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error('AI 请求失败: ' + (e?.detail || '未知错误'))
  }
  loading.value = false
  analyzingMode.value = ''
}

async function analyzeLogs() {
  if (loading.value) return
  loading.value = true
  analyzingMode.value = 'deepseek'
  try {
    const res: any = await http.post(`/ai/analyze/${props.testId}`)
    messages.value.push({
      role: 'assistant',
      content: res.analysis || '分析完成，无特殊发现。',
      timestamp: Date.now(),
    })
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error('日志分析失败: ' + (e?.detail || '未知错误'))
  }
  loading.value = false
  analyzingMode.value = ''
}

async function claudeAnalyze() {
  if (loading.value) return
  loading.value = true
  analyzingMode.value = 'claude'
  try {
    // Claude 深度分析需要较长时间（60-180秒），使用独立超时
    const res: any = await http.post(`/ai/claude-analyze/${props.testId}`, null, {
      timeout: 300000,  // 5 分钟超时
    } as any)
    messages.value.push({
      role: 'assistant',
      content: res.analysis || '分析完成，无特殊发现。',
      timestamp: Date.now(),
    })
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error('Claude 深度分析失败: ' + (e?.detail || '未知错误'))
  }
  loading.value = false
  analyzingMode.value = ''
}

async function analyzeErrors() {
  if (loading.value) return
  loading.value = true
  analyzingMode.value = 'errors'
  try {
    const res: any = await http.post(`/ai/analyze/${props.testId}/errors`)
    messages.value.push({
      role: 'assistant',
      content: res.analysis || '未发现错误。',
      timestamp: Date.now(),
    })
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error('错误分析失败: ' + (e?.detail || '未知错误'))
  }
  loading.value = false
  analyzingMode.value = ''
}

function clearChat() {
  messages.value = []
}

// 暴露方法供父组件调用
defineExpose({ analyzeLogs, analyzeErrors, clearChat })

onMounted(() => {
  // 自动发送欢迎消息
  messages.value.push({
    role: 'assistant',
    content: '你好！我是 AI 老化测试分析助手。我可以帮你：\n\n- **分析日志**：自动读取老化日志和系统日志进行分析\n- **分析错误**：专门检查日志中的错误和异常\n- **自由提问**：直接在下方输入你的分析需求\n\n请点击按钮或输入需求开始分析。',
    timestamp: Date.now(),
  })
})
</script>

<style scoped>
.ai-chat {
  display: flex;
  flex-direction: column;
  height: 500px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-empty {
  text-align: center;
  color: #909399;
  margin: auto;
  padding: 40px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-hint {
  font-size: 13px;
  color: #c0c4cc;
}

.chat-msg {
  display: flex;
  gap: 8px;
  max-width: 90%;
}

.msg-user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.msg-ai {
  align-self: flex-start;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.msg-user .msg-bubble {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-ai .msg-bubble {
  background: #fff;
  color: #303133;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.msg-content {
  word-break: break-word;
}

.msg-content :deep(p) {
  margin: 4px 0;
}

.msg-content :deep(pre.code-block) {
  background: #282c34;
  color: #abb2bf;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}

.msg-content :deep(code.inline-code) {
  background: rgba(0,0,0,0.06);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.msg-user .msg-content :deep(code.inline-code) {
  background: rgba(255,255,255,0.2);
}

.msg-content :deep(strong) {
  font-weight: 600;
}

.msg-content :deep(h2), .msg-content :deep(h3), .msg-content :deep(h4) {
  margin: 8px 0 4px;
  font-weight: 600;
}

.msg-content :deep(li) {
  margin: 2px 0;
}

.msg-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  text-align: right;
}

.msg-user .msg-time {
  color: rgba(255,255,255,0.7);
}

.typing .dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #909399;
  margin: 0 2px;
  animation: typing-bounce 1.4s infinite ease-in-out both;
}

.typing .dot:nth-child(1) { animation-delay: 0s; }
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-actions {
  padding: 8px 16px;
  display: flex;
  gap: 8px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

.chat-input {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}
</style>