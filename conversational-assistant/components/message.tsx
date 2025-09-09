import { MessageItem } from '@/lib/assistant'
import React from 'react'
import ReactMarkdown from 'react-markdown'
import './message.css'
import { Bot, User as UserIcon } from 'lucide-react'

interface MessageProps {
  message: MessageItem
}

const Message: React.FC<MessageProps> = ({ message }) => {
  const AssistantAvatar = () => (
    <div className="shrink-0 size-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
      <Bot size={16} />
    </div>
  )

  const UserAvatar = () => (
    <div className="shrink-0 size-9 rounded-full bg-zinc-200 text-zinc-700 flex items-center justify-center shadow-sm">
      <UserIcon size={16} />
    </div>
  )

  return (
    <div className="text-sm">
      {message.role === 'user' ? (
        <div className="flex items-start justify-end gap-3 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-right-2 motion-safe:duration-300 motion-safe:ease-out">
          <div className="max-w-[70%] rounded-[18px] px-4 py-2 bg-white text-zinc-900 font-light border border-border shadow-sm">
            <ReactMarkdown>{message.content as string}</ReactMarkdown>
          </div>
          <UserAvatar />
        </div>
      ) : (
        <div className="flex items-start gap-3 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-left-2 motion-safe:duration-300 motion-safe:ease-out">
          <AssistantAvatar />
          <div className="max-w-[70%] rounded-[18px] px-4 py-2 font-light bg-accent text-foreground border border-border">
            <ReactMarkdown>{message.content as string}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

export default Message
