"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format, isToday } from "date-fns";
import {
  BsArrowLeft,
  BsBell,
  BsBellFill,
  BsBoxArrowRight,
  BsCheck2,
  BsCheck2All,
  BsClock,
  BsFileEarmarkText,
  BsPaperclip,
  BsPersonPlus,
  BsRobot,
  BsSearch,
  BsSendFill,
  BsStars,
  BsChatSquareText,
  BsXLg,
  BsEmojiSmile,
} from "react-icons/bs";
import { CgSpinner } from "react-icons/cg";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { apiClient, clearLegacyTokenStorage, getApiBaseUrl, getApiErrorMessage } from "@/lib/api-client";
import { SupportAssistant } from "@/components/support-assistant";
import type { Conversation, Friendship, Message, MessageReaction, User } from "@/lib/types";
import { useWebSocketStore } from "@/stores/websocket-store";

const QUICK_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥"];
const EXTRA_EMOJIS = ["👏", "🎉", "🚀", "💯", "👀", "🙏", "⚡", "⭐", "💙", "🤝"];

function initials(name: string) { return name.slice(0, 2).toUpperCase(); }
function displayTime(value: string) { const date = new Date(value); return isToday(date) ? format(date, "h:mm a") : format(date, "MMM d"); }
function displayFileSize(value?: number | null) { if (!value) return "File"; if (value < 1024 * 1024) return `${Math.ceil(value / 1024)} KB`; return `${(value / (1024 * 1024)).toFixed(1)} MB`; }

function playChimeSound(type: "message" | "friend") {
  if (typeof window === "undefined") return;
  const AudioContextClass = window.AudioContext || (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) return;
  try {
    const ctx = new AudioContextClass();
    const now = ctx.currentTime;
    
    if (type === "message") {
      // Soft modern ping chime: two sine waves (C5 -> E5) decaying quickly
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(523.25, now); // C5
      osc1.frequency.exponentialRampToValueAtTime(659.25, now + 0.12); // Ramp to E5
      
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(659.25, now); // E5
      osc2.frequency.exponentialRampToValueAtTime(783.99, now + 0.12); // Ramp to G5
      
      gainNode.gain.setValueAtTime(0.08, now);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      
      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 0.25);
      osc2.stop(now + 0.25);
    } else if (type === "friend") {
      // Cheerful chime: fast arpeggio C5 -> E5 -> G5 -> C6 -> E6
      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      osc.type = "triangle";
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.08); // E5
      osc.frequency.setValueAtTime(783.99, now + 0.16); // G5
      osc.frequency.setValueAtTime(1046.50, now + 0.24); // C6
      osc.frequency.exponentialRampToValueAtTime(1318.51, now + 0.35); // E6
      
      gainNode.gain.setValueAtTime(0.08, now);
      gainNode.gain.setValueAtTime(0.08, now + 0.24);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
      
      osc.connect(gainNode);
      gainNode.connect(ctx.destination);
      
      osc.start(now);
      osc.stop(now + 0.45);
    }
  } catch (e) {
    console.error("Failed to play chime sound", e);
  }
}

export default function ChatPage() {
  const router = useRouter(); const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null); const [composer, setComposer] = useState("");
  const [search, setSearch] = useState(""); const [showNew, setShowNew] = useState(false); const [mobileList, setMobileList] = useState(true);
  const [peopleFinderMode, setPeopleFinderMode] = useState<"message" | "friend">("message");
  const [friendActionId, setFriendActionId] = useState<string | null>(null);
  const [friendError, setFriendError] = useState("");
  const [notice, setNotice] = useState<{ text: string; conversationId?: string; friend?: boolean } | null>(null);
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission | "unsupported">("default");
  const [showSupport, setShowSupport] = useState(false);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [pickerMessageId, setPickerMessageId] = useState<string | null>(null);
  const [typingByConversation, setTypingByConversation] = useState<Record<string, string[]>>({});
  const typingExpiryTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const { connect, disconnect, sendEvent, subscribe, status } = useWebSocketStore();

  useEffect(() => { return () => disconnect(); }, [disconnect]);
  useEffect(() => {
    const timer = window.setTimeout(() => setNotificationPermission("Notification" in window ? Notification.permission : "unsupported"), 0);
    return () => window.clearTimeout(timer);
  }, []);
  const me = useQuery<User>({ queryKey: ["me"], queryFn: async () => (await apiClient.get("/users/me")).data, retry: false });
  useEffect(() => {
    if (me.data) connect();
    else if (me.isError) disconnect();
  }, [connect, disconnect, me.data, me.isError]);
  useEffect(() => { if (me.isError) router.replace("/login"); }, [me.isError, router]);
  useEffect(() => {
    if (me.data && "Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then((perm) => {
        setNotificationPermission(perm);
      });
    }
  }, [me.data]);
  const conversations = useQuery<Conversation[]>({ queryKey: ["conversations"], queryFn: async () => (await apiClient.get("/conversations")).data, enabled: !!me.data });
  const selectedId = activeId ?? conversations.data?.[0]?.id ?? null;
  const messages = useQuery<Message[]>({ queryKey: ["messages", selectedId], queryFn: async () => (await apiClient.get(`/conversations/${selectedId}/messages`)).data, enabled: !!selectedId });
  const users = useQuery<User[]>({ queryKey: ["user-search", search], queryFn: async () => (await apiClient.get("/users/search", { params: { q: search } })).data, enabled: showNew && search.trim().length > 0 });
  const friends = useQuery<Friendship[]>({ queryKey: ["friends"], queryFn: async () => (await apiClient.get("/friends")).data, enabled: showNew && peopleFinderMode === "friend" });
  const friendRequests = useQuery<Friendship[]>({ queryKey: ["friend-requests"], queryFn: async () => (await apiClient.get("/friends/requests")).data, enabled: !!me.data });

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => subscribe((raw) => {
    const event = raw as { event_type?: string; data?: Record<string, unknown> };
    if (event.event_type === "message.created" && event.data) {
      const incoming = { ...event.data, id: event.data.message_id } as unknown as Message;
      queryClient.setQueryData<Message[]>(["messages", incoming.conversation_id], (old = []) => {
        const index = old.findIndex((item) => item.client_message_id === incoming.client_message_id);
        if (index >= 0) return old.map((item, i) => i === index ? incoming : item);
        return [...old, incoming];
      });
      const shouldMarkUnread = incoming.sender_id !== me.data?.id;
      queryClient.setQueryData<Conversation[]>(["conversations"], (old = []) => old.map((conversation) => conversation.id === incoming.conversation_id ? {
        ...conversation,
        last_message: incoming,
        updated_at: incoming.created_at,
        unread_count: shouldMarkUnread ? conversation.unread_count + 1 : conversation.unread_count,
      } : conversation).sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()));
      
      const isFromMe = incoming.sender_id === me.data?.id;
      if (!isFromMe) {
        const isBackgrounded = document.visibilityState !== "visible" || !document.hasFocus();
        const isActiveConversation = incoming.conversation_id === selectedId;

        if (isBackgrounded || !isActiveConversation) {
          playChimeSound("message");
        }

        if (isBackgrounded && "Notification" in window && Notification.permission === "granted") {
          const conversation = queryClient.getQueryData<Conversation[]>(["conversations"])?.find((item) => item.id === incoming.conversation_id);
          const sender = conversation?.members.find((member) => member.user_id === incoming.sender_id)?.user.username ?? "Someone";
          const notification = new Notification(`New message from ${sender}`, { body: incoming.content ?? "Sent you a message", tag: incoming.conversation_id });
          notification.onclick = () => { window.focus(); setActiveId(incoming.conversation_id); setMobileList(false); notification.close(); };
        }

        if (!isActiveConversation && !isBackgrounded) {
          const conversation = queryClient.getQueryData<Conversation[]>(["conversations"])?.find((item) => item.id === incoming.conversation_id);
          const sender = conversation?.members.find((member) => member.user_id === incoming.sender_id)?.user.username ?? "Someone";
          setNotice({ text: `${sender} sent you a new message.`, conversationId: incoming.conversation_id });
        }
      }
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    }
    if (event.event_type === "message.reaction_updated" && event.data) {
      const messageId = String(event.data.message_id ?? "");
      const conversationId = String(event.data.conversation_id ?? "");
      const reactions = (event.data.reactions ?? []) as MessageReaction[];
      if (conversationId && messageId) {
        queryClient.setQueryData<Message[]>(["messages", conversationId], (old = []) =>
          old.map((msg) => (msg.id === messageId ? { ...msg, reactions } : msg))
        );
      }
    }
    if (event.event_type === "typing.changed" && event.data) {
      const conversationId = String(event.data.conversation_id ?? "");
      const userId = String(event.data.user_id ?? "");
      if (!conversationId || !userId || userId === me.data?.id) return;
      const timerKey = `${conversationId}:${userId}`;
      const clearTyping = () => setTypingByConversation((old) => ({
        ...old,
        [conversationId]: (old[conversationId] ?? []).filter((id) => id !== userId),
      }));
      const priorTimer = typingExpiryTimers.current.get(timerKey);
      if (priorTimer) clearTimeout(priorTimer);
      if (event.data.is_typing) {
        setTypingByConversation((old) => ({
          ...old,
          [conversationId]: Array.from(new Set([...(old[conversationId] ?? []), userId])),
        }));
        typingExpiryTimers.current.set(timerKey, setTimeout(() => {
          clearTyping();
          typingExpiryTimers.current.delete(timerKey);
        }, 4000));
      } else {
        clearTyping();
        typingExpiryTimers.current.delete(timerKey);
      }
    }
    if (event.event_type === "error" && event.data?.client_message_id) {
      const conversationId = String(event.data.conversation_id ?? "");
      const clientMessageId = String(event.data.client_message_id);
      if (conversationId) queryClient.setQueryData<Message[]>(["messages", conversationId], (old = []) => old.map((item) => item.client_message_id === clientMessageId ? { ...item, status: "failed" } : item));
    }
    if ((event.event_type === "friend.requested" || event.event_type === "friend.accepted") && event.data) {
      const username = String(event.data.username ?? "Someone");
      const text = event.event_type === "friend.requested" ? `${username} sent you a friend request.` : `${username} accepted your friend request.`;
      queryClient.invalidateQueries({ queryKey: ["friend-requests"] });
      queryClient.invalidateQueries({ queryKey: ["friends"] });
      queryClient.invalidateQueries({ queryKey: ["user-search"] });
      
      playChimeSound("friend");
      setNotice({ text, friend: true });
      
      const isBackgrounded = document.visibilityState !== "visible" || !document.hasFocus();
      if (isBackgrounded && "Notification" in window && Notification.permission === "granted") {
        const notification = new Notification(event.event_type === "friend.requested" ? "New friend request" : "Friend request accepted", { body: text, tag: `friend-${event.data.friendship_id}` });
        notification.onclick = () => { window.focus(); openPeopleFinder("friend"); notification.close(); };
      }
    }
  }), [me.data?.id, queryClient, subscribe, selectedId]);

  useEffect(() => () => {
    typingExpiryTimers.current.forEach((timer) => clearTimeout(timer));
    typingExpiryTimers.current.clear();
  }, []);

  const active = conversations.data?.find((item) => item.id === selectedId);
  const other = active?.members.find((member) => member.user_id !== me.data?.id)?.user;
  const titleFor = (conversation: Conversation) => conversation.title || conversation.members.find((member) => member.user_id !== me.data?.id)?.user.username || "Conversation";
  const filtered = conversations.data?.filter((item) => titleFor(item).toLowerCase().includes(search.toLowerCase())) ?? [];
  const unreadMessages = conversations.data?.reduce((total, conversation) => total + conversation.unread_count, 0) ?? 0;

  function openPeopleFinder(mode: "message" | "friend", query = "") {
    setPeopleFinderMode(mode); setSearch(query); setFriendError(""); setShowNew(true);
  }

  async function refreshFriendData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["user-search"] }),
      queryClient.invalidateQueries({ queryKey: ["friends"] }),
      queryClient.invalidateQueries({ queryKey: ["friend-requests"] }),
    ]);
  }

  async function sendFriendRequest(userId: string) {
    setFriendActionId(userId); setFriendError("");
    try { await apiClient.post(`/friends/requests/${userId}`); await refreshFriendData(); }
    catch { setFriendError("Could not send that friend request. Please try again."); }
    finally { setFriendActionId(null); }
  }

  async function acceptFriendRequest(friendshipId: string) {
    setFriendActionId(friendshipId); setFriendError("");
    try { await apiClient.post(`/friends/requests/${friendshipId}/accept`); await refreshFriendData(); }
    catch { setFriendError("Could not accept that friend request. Please try again."); }
    finally { setFriendActionId(null); }
  }

  async function startConversation(userId: string) {
    const response = await apiClient.post("/conversations/direct", { target_user_id: userId });
    await queryClient.invalidateQueries({ queryKey: ["conversations"] }); setActiveId(response.data.id); setShowNew(false); setSearch(""); setMobileList(false);
  }
  async function enableNotifications() {
    if (!("Notification" in window)) { setNotificationPermission("unsupported"); return; }
    setNotificationPermission(await Notification.requestPermission());
  }
  function openConversation(conversationId: string) {
    setActiveId(conversationId); setMobileList(false);
    queryClient.setQueryData<Conversation[]>(["conversations"], (old = []) => old.map((conversation) => conversation.id === conversationId ? { ...conversation, unread_count: 0 } : conversation));
    apiClient.post(`/conversations/${conversationId}/read`).then(() => queryClient.invalidateQueries({ queryKey: ["conversations"] }));
  }
  async function toggleReaction(messageId: string, emoji: string) {
    if (!selectedId || !me.data) return;
    queryClient.setQueryData<Message[]>(["messages", selectedId], (old = []) =>
      old.map((msg) => {
        if (msg.id !== messageId) return msg;
        const current = msg.reactions ?? [];
        const exists = current.some((r) => r.user_id === me.data?.id && r.emoji === emoji);
        const updated = exists
          ? current.filter((r) => !(r.user_id === me.data?.id && r.emoji === emoji))
          : [...current, { id: crypto.randomUUID(), message_id: messageId, user_id: me.data.id, emoji, created_at: new Date().toISOString() }];
        return { ...msg, reactions: updated };
      })
    );
    const sent = sendEvent({
      event_type: "message.reaction.toggle",
      data: { conversation_id: selectedId, message_id: messageId, emoji },
    });
    if (!sent) {
      try {
        const response = await apiClient.post<Message>(
          `/conversations/${selectedId}/messages/${messageId}/reactions`,
          { emoji }
        );
        queryClient.setQueryData<Message[]>(["messages", selectedId], (old = []) =>
          old.map((msg) => (msg.id === messageId ? response.data : msg))
        );
      } catch {
        queryClient.invalidateQueries({ queryKey: ["messages", selectedId] });
      }
    }
  }
  function sendMessage(event: FormEvent) {
    event.preventDefault(); const content = composer.trim(); if (!content || !selectedId || !me.data) return;
    const clientId = crypto.randomUUID(); const optimistic: Message = { id: clientId, client_message_id: clientId, conversation_id: selectedId, sender_id: me.data.id, content, type: "text", status: "pending", created_at: new Date().toISOString() };
    queryClient.setQueryData<Message[]>(["messages", selectedId], (old = []) => [...old, optimistic]); setComposer("");
    sendEvent({ event_type: "typing.set", data: { conversation_id: selectedId, is_typing: false } });
    const sent = sendEvent({ event_type: "message.send", data: { conversation_id: selectedId, client_message_id: clientId, content } });
    if (!sent) apiClient.post(`/conversations/${selectedId}/messages`, { client_message_id: clientId, content }).then((response) => queryClient.setQueryData<Message[]>(["messages", selectedId], (old = []) => old.map((item) => item.client_message_id === clientId ? response.data : item))).catch(() => queryClient.setQueryData<Message[]>(["messages", selectedId], (old = []) => old.map((item) => item.client_message_id === clientId ? { ...item, status: "failed" } : item)));
  }
  async function uploadMedia(file: File) {
    if (!selectedId || uploadingMedia) return;
    const clientId = crypto.randomUUID();
    const form = new FormData();
    form.append("client_message_id", clientId);
    form.append("file", file);
    setUploadingMedia(true); setUploadError("");
    try {
      const response = await apiClient.post<Message>(`/conversations/${selectedId}/media`, form);
      queryClient.setQueryData<Message[]>(["messages", selectedId], (old = []) => {
        const index = old.findIndex((item) => item.client_message_id === clientId);
        if (index >= 0) return old.map((item, i) => i === index ? response.data : item);
        return [...old, response.data];
      });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    } catch (error) {
      setUploadError(getApiErrorMessage(error, "Could not upload that file."));
    } finally {
      setUploadingMedia(false);
    }
  }
  async function logout() {
    try { await apiClient.post("/auth/logout"); } finally {
      clearLegacyTokenStorage(); disconnect(); queryClient.clear(); window.location.replace("/login");
    }
  }

  return <main className="chat-shell">
    <aside className={`sidebar ${mobileList ? "mobile-open" : ""}`}>
      <div className="sidebar-top"><div><p className="eyebrow">RELAY</p><h1>Messages</h1></div><div className="sidebar-actions"><button className="icon-button friend-button" onClick={() => openPeopleFinder("friend")} aria-label={`Make a friend${friendRequests.data?.length ? `, ${friendRequests.data.length} pending requests` : ""}`} title="Make a friend"><BsPersonPlus size={20}/>{!!friendRequests.data?.length && <span className="action-badge">{friendRequests.data.length > 9 ? "9+" : friendRequests.data.length}</span>}</button><button className="icon-button support-button" onClick={() => setShowSupport(true)} aria-label="Open Relay Support" title="Ask Relay Support"><BsRobot size={20}/></button><button className="icon-button accent" onClick={() => openPeopleFinder("message")} aria-label={`New message${unreadMessages ? `, ${unreadMessages} unread` : ""}`}><BsChatSquareText size={20}/>{unreadMessages > 0 && <span className="action-badge message-count">{unreadMessages > 99 ? "99+" : unreadMessages}</span>}</button></div></div>
      <div className="search-box"><BsSearch size={17}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search conversations"/></div>
      <div className="connection-line"><span className={`status-dot ${status}`}/>{status === "connected" ? "Live and connected" : status}</div>
      <div className="conversation-list">{conversations.isLoading && <p className="list-note">Loading your conversations…</p>}{!conversations.isLoading && filtered.length === 0 && <div className="empty-list"><BsStars size={20}/><p>Your next conversation starts here.</p><button onClick={() => openPeopleFinder("friend")}>Find someone</button></div>}
        {filtered.map((conversation, index) => { const name = titleFor(conversation); return <button key={conversation.id} className={`conversation-row ${selectedId === conversation.id ? "active" : ""} ${conversation.unread_count > 0 ? "unread" : ""}`} onClick={() => openConversation(conversation.id)}>
          <div className={`avatar tone-${index % 4}`}>{initials(name)}<span className="online-dot"/></div><div className="conversation-copy"><div><strong>{name}</strong><time>{displayTime(conversation.last_message?.created_at ?? conversation.updated_at)}</time></div><p>{conversation.last_message?.content ?? "Ready when you are"}</p></div>{conversation.unread_count > 0 && <span className="unread-badge">{conversation.unread_count > 99 ? "99+" : conversation.unread_count}</span>}</button>; })}
      </div>
      <div className="profile-strip"><Link href="/profile" className="profile-strip-link"><div className="avatar small">{me.data?.avatar_url ? <img src={me.data.avatar_url} alt="" /> : initials(me.data?.username ?? "ME")}</div><div><strong>{me.data?.username ?? "Loading…"}</strong><span>{me.data?.email}</span></div></Link><button onClick={logout} aria-label="Sign out"><BsBoxArrowRight size={18}/></button></div>
    </aside>
    <section className={`conversation-panel ${!mobileList ? "mobile-open" : ""}`}>
      {active ? <><header className="conversation-header"><button className="mobile-back" onClick={() => setMobileList(true)}><BsArrowLeft size={20}/></button><div className="avatar">{initials(other?.username ?? active.title ?? "CH")}</div><div><h2>{active.title || other?.username || "Conversation"}</h2><p>{status === "connected" ? "Available now" : "Reconnecting…"}</p></div><button className="header-menu" onClick={enableNotifications} disabled={notificationPermission === "unsupported"} aria-label={notificationPermission === "granted" ? "Notifications enabled" : "Enable message notifications"} title={notificationPermission === "denied" ? "Notifications are blocked in browser settings" : notificationPermission === "granted" ? "Message notifications enabled" : "Enable message notifications"}>{notificationPermission === "granted" ? <BsBellFill size={20}/> : <BsBell size={20}/>}</button></header>
        <div className="message-area"><div className="thread-intro"><div className="avatar large">{initials(other?.username ?? "CH")}</div><h3>{other?.username ?? active.title}</h3><p>This is the start of your conversation.</p></div>
          {(messages.data ?? []).map((message, index, all) => {
            const mine = message.sender_id === me.data?.id;
            const senderName = mine ? "You" : active.members.find((member) => member.user_id === message.sender_id)?.user.username ?? "Unknown sender";
            const sentAt = new Date(message.created_at);
            const prior = all[index - 1];
            const showTime = !prior || sentAt.getTime() - new Date(prior.created_at).getTime() > 10 * 60 * 1000;
            const reactions = message.reactions ?? [];
            const groupedReactions = reactions.reduce((acc, r) => {
              if (!acc[r.emoji]) acc[r.emoji] = [];
              acc[r.emoji].push(r);
              return acc;
            }, {} as Record<string, MessageReaction[]>);
            return <div key={message.id} className={`message-wrap ${mine ? "mine" : "theirs"}`}>
              {showTime && <time dateTime={message.created_at}>{format(sentAt, "MMM d · h:mm a")}</time>}
              <div className="message-info"><strong>{senderName}</strong><span>·</span><time dateTime={message.created_at}>{format(sentAt, "h:mm a")}</time></div>
              <div className="bubble-container">
                <div className={`bubble ${message.type !== "text" ? "media-bubble" : ""} ${message.status === "failed" ? "failed" : ""}`}>
                  {message.type === "image" && <a className="media-preview" href={`${getApiBaseUrl()}/messages/${message.id}/media`} target="_blank" rel="noreferrer">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`${getApiBaseUrl()}/messages/${message.id}/media`} alt={message.media_filename ?? "Shared image"}/>
                  </a>}
                  {message.type === "video" && <video className="media-preview" src={`${getApiBaseUrl()}/messages/${message.id}/media`} controls preload="metadata"/>}
                  {message.type === "audio" && <audio className="audio-preview" src={`${getApiBaseUrl()}/messages/${message.id}/media`} controls preload="metadata"/>}
                  {message.type === "file" && <a className="file-card" href={`${getApiBaseUrl()}/messages/${message.id}/media`}><BsFileEarmarkText size={22}/><span><strong>{message.media_filename ?? message.content ?? "Attachment"}</strong><small>{displayFileSize(message.media_size)}</small></span></a>}
                  {message.type !== "text" && message.type !== "file" && <span className="media-caption">{message.media_filename}</span>}
                  {message.type === "text" && message.content}
                </div>
                {message.status !== "pending" && message.status !== "failed" && (
                  <div className={`reaction-action-bar ${pickerMessageId === message.id ? "has-active-picker" : ""}`}>
                    {QUICK_EMOJIS.map((emoji) => {
                      const reacted = reactions.some((r) => r.user_id === me.data?.id && r.emoji === emoji);
                      return (
                        <button
                          key={emoji}
                          className={`reaction-btn ${reacted ? "active" : ""}`}
                          onClick={() => toggleReaction(message.id, emoji)}
                          title={`React with ${emoji}`}
                        >
                          {emoji}
                        </button>
                      );
                    })}
                    <button
                      className="reaction-btn picker-toggle"
                      onClick={() => setPickerMessageId(pickerMessageId === message.id ? null : message.id)}
                      title="More reactions"
                    >
                      <BsEmojiSmile size={14} />
                    </button>
                    {pickerMessageId === message.id && (
                      <div className="extra-emoji-picker">
                        {EXTRA_EMOJIS.map((emoji) => (
                          <button
                            key={emoji}
                            className="reaction-btn"
                            onClick={() => {
                              toggleReaction(message.id, emoji);
                              setPickerMessageId(null);
                            }}
                          >
                            {emoji}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              {Object.keys(groupedReactions).length > 0 && (
                <div className="message-reactions-bar">
                  {Object.entries(groupedReactions).map(([emoji, list]) => {
                    const reactedByMe = list.some((r) => r.user_id === me.data?.id);
                    const userNames = list.map((r) => {
                      if (r.user_id === me.data?.id) return "You";
                      return active.members.find((m) => m.user_id === r.user_id)?.user.username ?? "Someone";
                    }).join(", ");
                    return (
                      <button
                        key={emoji}
                        className={`reaction-pill ${reactedByMe ? "reacted-by-me" : ""}`}
                        onClick={() => toggleReaction(message.id, emoji)}
                        title={`Reacted by ${userNames}`}
                      >
                        <span className="pill-emoji">{emoji}</span>
                        {list.length > 1 && <span className="pill-count">{list.length}</span>}
                      </button>
                    );
                  })}
                </div>
              )}
              {mine && <span className="delivery">{message.status === "failed" ? "Not sent" : message.status === "pending" ? "Sending…" : <><BsCheck2All size={14}/> Sent</>}</span>}
            </div>;
          })}
          {(typingByConversation[selectedId ?? ""] ?? []).length > 0 && <p className="typing-indicator">{other?.username ?? "Someone"} is typing…</p>}
        </div>{uploadError && <p className="upload-error">{uploadError}</p>}<form className="composer" onSubmit={sendMessage}><label className={`file-button ${uploadingMedia ? "disabled" : ""}`} aria-label="Upload media" title="Upload image, video, audio, or file">{uploadingMedia ? <CgSpinner className="spin" size={19}/> : <BsPaperclip size={19}/>}<input type="file" disabled={uploadingMedia} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) uploadMedia(file); }}/></label><input value={composer} onChange={(e) => { setComposer(e.target.value); if (selectedId) sendEvent({ event_type: "typing.set", data: { conversation_id: selectedId, is_typing: !!e.target.value } }); }} placeholder={uploadingMedia ? "Uploading attachment…" : `Message ${other?.username ?? "conversation"}`}/><button disabled={!composer.trim()} aria-label="Send"><BsSendFill size={18}/></button></form></> : <div className="no-conversation"><div className="brand-mark"><BsChatSquareText size={36}/></div><h2>Your conversations live here.</h2><p>Choose one from the left, or start something new.</p><button className="primary-button" onClick={() => openPeopleFinder("message")}>New message</button></div>}
    </section>
    {showNew && <div className="modal-backdrop" onMouseDown={() => setShowNew(false)}><section className="new-modal" onMouseDown={(e) => e.stopPropagation()}><header><div><p className="eyebrow">{peopleFinderMode === "friend" ? "MAKE A FRIEND" : "NEW MESSAGE"}</p><h2>{peopleFinderMode === "friend" ? "Find someone new" : "Who are you looking for?"}</h2></div><button onClick={() => setShowNew(false)}><BsXLg size={18}/></button></header><div className="search-box large"><BsSearch size={18}/><input autoFocus value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by username or email"/></div>{friendError && <p className="friend-error">{friendError}</p>}<div className="user-results">
      {search && users.isLoading && <p className="list-note">Searching…</p>}
      {users.data?.map((user, index) => {
        const accepting = peopleFinderMode === "friend" && user.friendship_status === "incoming_pending";
        const actionId = accepting ? user.friendship_id : user.id;
        const disabled = friendActionId === actionId || (peopleFinderMode === "friend" && (user.friendship_status === "outgoing_pending" || user.friendship_status === "friends"));
        const action = peopleFinderMode === "message" ? () => startConversation(user.id) : accepting && user.friendship_id ? () => acceptFriendRequest(user.friendship_id!) : () => sendFriendRequest(user.id);
        const label = peopleFinderMode === "message" ? "Message" : user.friendship_status === "friends" ? "Friends" : user.friendship_status === "outgoing_pending" ? "Requested" : accepting ? "Accept" : "Add friend";
        return <button key={user.id} disabled={disabled} onClick={action}><div className={`avatar tone-${index % 4}`}>{initials(user.username)}</div><div><strong>{user.username}</strong><span>{user.email}</span></div><span>{user.friendship_status === "friends" ? <BsCheck2 size={14}/> : user.friendship_status === "outgoing_pending" ? <BsClock size={14}/> : peopleFinderMode === "friend" ? <BsPersonPlus size={14}/> : null} {friendActionId === actionId ? "Working…" : label}</span></button>;
      })}
      {search && !users.isLoading && users.data?.length === 0 && <p className="list-note">No people found.</p>}
      {!search && peopleFinderMode === "friend" && <div className="friend-overview">
        {(friendRequests.data?.length ?? 0) > 0 && <><h3>Friend requests</h3>{friendRequests.data?.map((request, index) => <div className="friend-row" key={request.id}><div className={`avatar tone-${index % 4}`}>{initials(request.user.username)}</div><div><strong>{request.user.username}</strong><span>{request.user.email}</span></div><button disabled={friendActionId === request.id} onClick={() => acceptFriendRequest(request.id)}><BsCheck2 size={14}/> {friendActionId === request.id ? "Accepting…" : "Accept"}</button></div>)}</>}
        <h3>Your friends</h3>
        {friends.isLoading && <p className="list-note">Loading friends…</p>}
        {!friends.isLoading && friends.data?.length === 0 && <p className="list-note compact">Search above to send your first friend request.</p>}
        {friends.data?.map((friend, index) => <div className="friend-row" key={friend.id}><div className={`avatar tone-${(index + 1) % 4}`}>{initials(friend.user.username)}</div><div><strong>{friend.user.username}</strong><span>{friend.user.email}</span></div><button onClick={() => startConversation(friend.user.id)}><BsChatSquareText size={14}/> Message</button></div>)}
      </div>}
    </div></section></div>}
    {showSupport && <SupportAssistant conversations={(conversations.data ?? []).map((conversation) => ({ id: conversation.id, name: titleFor(conversation) }))} onClose={() => setShowSupport(false)} onFindPeople={(query) => openPeopleFinder("friend", query)} onLogin={logout} onLogout={logout} onOpenConversation={openConversation}/>}
    {notice && <button className="app-toast" onClick={() => { if (notice.friend) openPeopleFinder("friend"); else if (notice.conversationId) openConversation(notice.conversationId); setNotice(null); }}><span>{notice.friend ? <BsPersonPlus size={18}/> : <BsChatSquareText size={18}/>}</span><strong>{notice.text}</strong><small>Open</small></button>}
  </main>;
}
