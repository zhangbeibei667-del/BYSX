import { ref } from 'vue'
import type { AnswerResponse } from '@/types'

/**
 * SSE流式请求工具
 */
export class StreamSSE {
  private eventSource: EventSource | null = null
  private message = ref('')
  private isComplete = ref(false)
  private buffer = ''

  constructor(private url: string, private options?: RequestInit) {}

  /**
   * 开始流式请求
   */
  start(onData?: (data: AnswerResponse) => void, onComplete?: () => void, onChunk?: (chunk: string) => void) {
    this.reset()
    
    this.eventSource = new EventSource(this.url)
    
    this.eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        this.isComplete.value = true
        this.eventSource?.close()
        onComplete?.()
        return
      }
      try {
        const data = JSON.parse(event.data)
        
        if (data.type === 'complete') {
          this.isComplete.value = true
          this.eventSource?.close()
          onComplete?.()
        } else if (data.type === 'chunk') {
          this.buffer += data.content
          this.message.value = this.buffer
          onChunk?.(data.content)
          
          // 如果是完整JSON响应，调用回调
          if (data.complete_response) {
            onData?.(data.complete_response)
          }
        } else if (data.type === 'result') {
          onData?.(data.result || data)
        } else if (data.type === 'error') {
          console.error('SSE error:', data.error)
          this.eventSource?.close()
        }
      } catch (error) {
        console.error('Failed to parse SSE data:', error)
      }
    }
    
    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
      this.eventSource?.close()
      this.isComplete.value = true
    }
  }

  /**
   * 停止流式请求
   */
  stop() {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
      this.isComplete.value = true
    }
  }

  /**
   * 重置状态
   */
  reset() {
    this.stop()
    this.message.value = ''
    this.buffer = ''
    this.isComplete.value = false
  }

  /**
   * 获取当前消息
   */
  getMessage() {
    return this.message
  }

  /**
   * 获取完成状态
   */
  getIsComplete() {
    return this.isComplete
  }
}

/**
 * 模拟流式响应（开发环境使用）
 */
export function simulateStreamResponse(
  response: AnswerResponse,
  onChunk: (chunk: string) => void,
  onComplete?: () => void,
  chunkDelay = 50
): Promise<void> {
  return new Promise((resolve) => {
    const chunks = response.answer.split('')
    let index = 0
    
    const sendChunk = () => {
      if (index < chunks.length) {
        onChunk(chunks[index])
        index++
        setTimeout(sendChunk, chunkDelay)
      } else {
        onComplete?.()
        resolve()
      }
    }
    
    sendChunk()
  })
}

/**
 * 解析SSE数据
 */
export function parseSSEData(data: string): any[] {
  const lines = data.split('\n')
  const results: any[] = []
  
  let buffer = ''
  let eventType = ''
  
  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.replace('event:', '').trim()
    } else if (line.startsWith('data:')) {
      const dataLine = line.replace('data:', '').trim()
      buffer += dataLine
      
      if (dataLine.endsWith('}')) {
        try {
          const parsed = JSON.parse(buffer)
          results.push({ type: eventType, data: parsed })
          buffer = ''
          eventType = ''
        } catch (error) {
          // 继续累积数据
        }
      }
    } else if (line === '') {
      // 空行表示消息结束
      if (buffer) {
        try {
          const parsed = JSON.parse(buffer)
          results.push({ type: eventType, data: parsed })
        } catch (error) {
          console.error('Failed to parse buffer:', buffer, error)
        }
        buffer = ''
        eventType = ''
      }
    }
  }
  
  return results
}
