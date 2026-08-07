"use client";

import { BsRobot, BsSendFill, BsTrash3, BsXLg } from "react-icons/bs";
import { FormEvent, useState } from "react";
import { apiClient, getApiErrorMessage } from "@/lib/api-client";

type SupportMessage = {
  role: "user" | "assistant";
  content: string;
};

type SupportAction = {
  type: "login" | "logout" | "open_chat" | "find_people";
  label: string;
  target?: string | null;
};

type SupportAssistantProps = {
  conversations: Array<{ id: string; name: string }>;
  onClose: () => void;
  onFindPeople: (query: string) => void;
  onLogin: () => void;
  onLogout: () => void;
  onOpenConversation: (conversationId: string) => void;
};

const welcomeMessage: SupportMessage = {
  role: "assistant",
  content: "Hi! I’m Relay Support, running on your local Ollama model. How can I help?",
};

function directAuthAction(message: string): "login" | "logout" | null {
  const request = message.toLowerCase().replace(/[^a-z\s]/g, " ").replace(/\s+/g, " ").trim();
  if (/^(please )?((can|could|would|will) you )?(log|sign)( me)? out( now)?( please)?$/.test(request) || /^(i (want|need|would like) (you )?to )?(log out|logout|sign out)( now)?( please)?$/.test(request)) return "logout";
  if (/^(please )?(open|go to|take me to)( the)? (log in|login|sign in)( page| screen)?( now)?$/.test(request)) return "login";
  if (/^(please )?((can|could|would|will) you )?(log|sign)( me)? in( now)?( please)?$/.test(request) || /^(i (want|need|would like) (you )?to )?(log in|login|sign in)( now)?( please)?$/.test(request)) return "login";
  return null;
}

export function SupportAssistant({ conversations, onClose, onFindPeople, onLogin, onLogout, onOpenConversation }: SupportAssistantProps) {
  const [messages, setMessages] = useState<SupportMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message || loading) return;

    const history = messages.filter((item) => item !== welcomeMessage).slice(-20).map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, { role: "user", content: message }]);
    setInput("");
    setError("");
    const authAction = directAuthAction(message);
    if (authAction) {
      setMessages((current) => [...current, { role: "assistant", content: authAction === "logout" ? "Logging you out now." : "Opening the sign-in screen now." }]);
      if (authAction === "logout") onLogout();
      else onLogin();
      return;
    }
    setLoading(true);
    try {
      const response = await apiClient.post<{ reply: string; model: string; actions: SupportAction[] }>("/support/chat", {
        message,
        history,
        available_conversations: conversations.map((conversation) => conversation.name),
      });
      setMessages((current) => [...current, { role: "assistant", content: response.data.reply }]);
      const action = response.data.actions[0];
      if (action) runAction(action);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "The support assistant could not answer right now."));
    } finally {
      setLoading(false);
    }
  }

  function runAction(action: SupportAction) {
    if (action.type === "login") {
      onLogin();
      return;
    }
    if (action.type === "logout") {
      onLogout();
      return;
    }
    const target = (action.target ?? action.label.replace(/^(find|search for|chat with|message)\s+/i, "")).trim();
    if (action.type === "open_chat") {
      const conversation = conversations.find((item) => item.name.toLowerCase() === target.toLowerCase());
      if (conversation) {
        onOpenConversation(conversation.id);
        onClose();
        return;
      }
    }
    onFindPeople(target);
    onClose();
  }

  return <div className="support-backdrop" onMouseDown={onClose}>
    <section className="support-panel" onMouseDown={(event) => event.stopPropagation()} aria-label="Relay Support assistant">
      <header>
        <div className="support-heading"><span><BsRobot size={19}/></span><div><strong>Relay Support</strong><small>Local Ollama assistant</small></div></div>
        <div className="support-actions"><button type="button" onClick={() => { setMessages([welcomeMessage]); setError(""); }} aria-label="Clear assistant chat" title="Clear chat"><BsTrash3 size={17}/></button><button type="button" onClick={onClose} aria-label="Close assistant"><BsXLg size={19}/></button></div>
      </header>
      <div className="support-messages" aria-live="polite">
        {messages.map((item, index) => <div key={index} className={`support-message ${item.role}`}><div className="support-message-content"><span>{item.content}</span></div></div>)}
        {loading && <div className="support-message assistant"><span className="support-thinking">Thinking<span>…</span></span></div>}
      </div>
      {error && <p className="support-error">{error}</p>}
      <form className="support-composer" onSubmit={sendMessage}>
        <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Ask a question…" rows={1} maxLength={4000}/>
        <button disabled={!input.trim() || loading} aria-label="Send to support assistant"><BsSendFill size={18}/></button>
      </form>
    </section>
  </div>;
}
