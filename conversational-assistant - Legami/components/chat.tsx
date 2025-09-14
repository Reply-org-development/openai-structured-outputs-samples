'use client'

import { Item } from '@/lib/assistant'
import React, { useEffect, useRef, useState } from 'react'
import ToolCall from './tool-call'
import Message from './message'
import useConversationStore from '@/stores/useConversationStore'
import { ArrowDown, Bot } from 'lucide-react'
import './message.css'

interface ChatProps {
  items: Item[]
  onSendMessage: (message: string) => void
}

const Chat: React.FC<ChatProps> = ({ items, onSendMessage }) => {
  const itemsEndRef = useRef<HTMLDivElement>(null)
  const [inputMessageText, setinputMessageText] = useState<string>('')
  const { isAssistantTyping } = useConversationStore()
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [showScrollDown, setShowScrollDown] = useState(false)
  const suggestions = [
    'Mostra prodotti',
    'Idee regalo',
    'Stato ordine',
    'Resi e spedizioni',
    'Contatta supporto'
  ]

  const scrollToBottom = () => {
    itemsEndRef.current?.scrollIntoView({ behavior: 'instant' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [items])

  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight
      setShowScrollDown(distance > 120)
    }
    el.addEventListener('scroll', onScroll)
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="flex h-full w-full min-h-0">
      <div className="flex flex-col h-full w-full max-w-6xl mx-auto gap-2 px-4 md:px-8 min-h-0">
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto elegant-scroll motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300">
          <div className="space-y-1 pt-6 pb-24">
            {items.map((item, index) => (
              <React.Fragment key={index}>
                {item.type === 'function_call' ? (
                  <ToolCall
                    functionCall={item}
                    previousItem={items[index - 1]}
                  />
                ) : (
                  <Message message={item} />
                )}
              </React.Fragment>
            ))}
            {isAssistantTyping ? (
              <div className="flex items-start gap-3">
                <div className="shrink-0 size-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
                  <Bot size={16} />
                </div>
                <div className="max-w-[70%] rounded-[18px] px-3 py-2 font-light bg-accent text-zinc-500 border border-border">
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              </div>
            ) : null}
            <div ref={itemsEndRef} />
          </div>
        </div>
        {showScrollDown ? (
          <button
            className="fixed bottom-24 right-6 md:right-[calc(50%-36rem+1rem)] z-30 rounded-full bg-primary text-white p-3 shadow-md hover:shadow-lg transition-all"
            onClick={() => itemsEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
            aria-label="Torna in fondo"
          >
            <ArrowDown className="size-4" />
          </button>
        ) : null}
        <div className="pb-6 -mb-2 bg-gradient-to-t from-background via-background/70 to-transparent">
          <div className="flex items-center">
            <div className="flex w-full items-center">
              <div className="flex w-full flex-col gap-1.5 rounded-[26px] p-2 transition-all duration-200 ease-out bg-white border border-border shadow-sm focus-within:shadow-md">
                <div className="flex flex-wrap gap-1.5 px-2 pt-1 pb-0.5">
                  {suggestions.map(s => (
                    <button
                      key={s}
                      className="rounded-full border border-border bg-secondary px-3 py-1 text-xs text-zinc-700 hover:bg-accent transition-colors"
                      onClick={() => setinputMessageText(s)}
                      type="button"
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-1.5 md:gap-2 pl-4">
                  <div className="flex min-w-0 flex-1 flex-col">
                    <textarea
                      id="prompt-textarea"
                      tabIndex={0}
                      dir="auto"
                      rows={1}
                      placeholder="Scrivi un messaggio..."
                      className="m-0 resize-none border-0 focus:outline-none text-sm bg-transparent px-0 py-3 max-h-[20dvh] placeholder:text-zinc-400"
                      value={inputMessageText}
                      onChange={e => setinputMessageText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          onSendMessage(inputMessageText)
                          setinputMessageText('')
                        }
                      }}
                    />
                  </div>
                  <button
                    disabled={!inputMessageText}
                    data-testid="send-button"
                    className="flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground transition-all duration-200 hover:shadow-md hover:bg-primary/90 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:bg-[#D7D7D7] disabled:text-[#f4f4f4] disabled:hover:opacity-100"
                    onClick={() => {
                      onSendMessage(inputMessageText)
                      setinputMessageText('')
                    }}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="32"
                      height="32"
                      fill="none"
                      viewBox="0 0 32 32"
                      className="icon-2xl"
                    >
                      <path
                        fill="currentColor"
                        fillRule="evenodd"
                        d="M15.192 8.906a1.143 1.143 0 0 1 1.616 0l5.143 5.143a1.143 1.143 0 0 1-1.616 1.616l-3.192-3.192v9.813a1.143 1.143 0 0 1-2.286 0v-9.813l-3.192 3.192a1.143 1.143 0 1 1-1.616-1.616z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Chat
