export type User = {
  id: string; email: string; username: string; avatar_url?: string | null; is_active: boolean; created_at: string; last_seen_at?: string | null;
  friendship_status?: "none" | "outgoing_pending" | "incoming_pending" | "friends";
  friendship_id?: string | null;
};
export type Friendship = {
  id: string; status: "pending" | "accepted"; user: User; requested_by_me: boolean; created_at: string;
};
export type Member = { user_id: string; role: string; user: User };
export type Conversation = {
  id: string; type: string; title?: string | null; avatar_url?: string | null;
  creator_id: string; created_at: string; updated_at: string; members: Member[];
  last_message?: Message | null; unread_count: number;
};
export type MessageReaction = {
  id: string;
  message_id: string;
  user_id: string;
  emoji: string;
  created_at: string;
};
export type Message = {
  id: string; conversation_id: string; sender_id: string; client_message_id: string;
  type: string; content?: string | null; status: string; created_at: string;
  media_filename?: string | null; media_content_type?: string | null; media_size?: number | null;
  edited_at?: string | null; deleted_at?: string | null;
  reactions?: MessageReaction[];
};
