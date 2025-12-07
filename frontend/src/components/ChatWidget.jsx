import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, Bot, User, Loader2, Sparkles, Minimize2, Maximize2 } from 'lucide-react';
import api from '../utils/api';
import { clsx } from 'clsx';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am your AI financial assistant. Ask me about stock prices, news, or market analysis.' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [thinkingText, setThinkingText] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen, thinkingText]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);
    setThinkingText('Processing...');

    try {
      // Build history
      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      
      const response = await fetch(`${api.defaults.baseURL}/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMsg,
          history: history
        })
      });

      if (!response.ok) throw new Error(response.statusText);

      // Create a new assistant message placeholder
      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Process buffer line by line
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // Keep incomplete last chunk
        
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const [eventLine, dataLine] = line.split('\n');
            const eventType = eventLine.replace('event: ', '').trim();
            const dataStr = dataLine ? dataLine.replace('data: ', '') : '{}';
            
            if (eventType === 'done') {
                setIsLoading(false);
                setThinkingText('');
                break;
            }
            
            try {
                const data = JSON.parse(dataStr);
                
                if (eventType === 'thinking') {
                    setThinkingText(data.text || 'Thinking...');
                } else if (eventType === 'content') {
                    setMessages(prev => {
                        const newMsgs = [...prev];
                        const lastMsg = newMsgs[newMsgs.length - 1];
                        if (lastMsg.role === 'assistant' && typeof data.text === 'string') {
                            lastMsg.content += data.text;
                        }
                        return newMsgs;
                    });
                }
            } catch (e) {
                console.error("Error parsing stream data", e);
            }
          }
        }
      }

    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error. Please try again." }]);
    } finally {
      setIsLoading(false);
      setThinkingText('');
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-[999] flex flex-col items-end">
      {/* Chat Window */}
      {isOpen && (
        <div className={clsx(
          "mb-4 bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col transition-all duration-300",
          isExpanded ? "w-[600px] h-[80vh]" : "w-[380px] h-[500px]"
        )}>
          {/* Header */}
          <div className="p-4 bg-gradient-to-r from-blue-600 to-indigo-600 flex items-center justify-between">
            <div className="flex items-center gap-2 text-white">
              <Bot className="w-5 h-5" />
              <span className="font-semibold">AI Assistant</span>
            </div>
            <div className="flex items-center gap-1 text-white/80">
              <button 
                onClick={() => setIsExpanded(!isExpanded)} 
                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
              >
                {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
              <button 
                onClick={() => setIsOpen(false)} 
                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-900/50 backdrop-blur-sm custom-scrollbar">
            {messages.map((msg, idx) => (
              <div 
                key={idx} 
                className={clsx(
                  "flex gap-3 max-w-[85%]",
                  msg.role === 'user' ? "ml-auto flex-row-reverse" : ""
                )}
              >
                <div className={clsx(
                  "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                  msg.role === 'user' ? "bg-blue-500/20 text-blue-400" : "bg-indigo-500/20 text-indigo-400"
                )}>
                  {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>
                <div className={clsx(
                  "p-3 rounded-2xl text-sm leading-relaxed",
                  msg.role === 'user' 
                    ? "bg-blue-600 text-white rounded-tr-sm" 
                    : "bg-white/10 text-slate-200 rounded-tl-sm border border-white/5"
                )}>
                  <div 
                    className="prose prose-invert prose-sm max-w-none break-words [&>a]:text-blue-300 [&>a]:break-all [&>table]:w-full [&>table]:border-collapse [&>table]:border [&>table]:border-white/20 [&>th]:border [&>th]:border-white/20 [&>th]:p-2 [&>th]:bg-white/5 [&>th]:text-left [&>td]:border [&>td]:border-white/20 [&>td]:p-2"
                    dangerouslySetInnerHTML={{ 
                      __html: DOMPurify.sanitize(marked.parse(msg.content)) 
                    }} 
                  />
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3 max-w-[85%]">
                <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="p-3 rounded-2xl bg-white/5 text-slate-200 rounded-tl-sm border border-white/5 flex items-center gap-3 max-w-[80%]">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-400 shrink-0" />
                  <span className="text-xs font-mono text-indigo-200/70 break-words leading-relaxed">{thinkingText}</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} className="p-4 bg-slate-900 border-t border-white/10">
            <div className="relative">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about stocks..."
                className="w-full pl-4 pr-12 py-3 bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-blue-500/50 focus:bg-white/10 text-white text-sm placeholder:text-slate-500 transition-all"
              />
              <button 
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <div className="text-center mt-2">
               <span className="text-[10px] text-slate-600 flex items-center justify-center gap-1">
                 <Sparkles className="w-3 h-3" /> AI can make mistakes. Check important info.
               </span>
            </div>
          </form>
        </div>
      )}

      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="group relative flex items-center justify-center w-14 h-14 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-full shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:scale-105 transition-all duration-300"
        >
          <MessageSquare className="w-6 h-6 text-white" />
          <span className="absolute right-0 top-0 flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-sky-500"></span>
          </span>
        </button>
      )}
    </div>
  );
};

export default ChatWidget;
