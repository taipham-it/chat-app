"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { BsArrowLeft, BsCamera, BsCheck2 } from "react-icons/bs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, getApiErrorCode, getApiErrorMessage } from "@/lib/api-client";
import type { User } from "@/lib/types";

function initials(name: string) { return name.slice(0, 2).toUpperCase(); }

export default function ProfilePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const me = useQuery<User>({ queryKey: ["me"], queryFn: async () => (await apiClient.get("/users/me")).data, retry: false });
  const [name, setName] = useState("");
  const [avatar, setAvatar] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // The query resolves after the page mounts, so seed the form once the session is available.
    if (me.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setName(me.data.username);
      setAvatar(me.data.avatar_url ?? null);
    }
    if (me.isError) router.replace("/login");
  }, [me.data, me.isError, router]);

  function chooseAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { setError("Please choose an image file."); return; }
    if (file.size > 1_500_000) { setError("Please choose an image smaller than 1.5 MB."); return; }
    const reader = new FileReader();
    reader.onload = () => setAvatar(String(reader.result));
    reader.readAsDataURL(file);
    setError("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed.length < 3) { setError("Your name must be at least 3 characters."); return; }
    setBusy(true); setError(""); setSaved(false);
    try {
      const response = await apiClient.patch<User>("/users/me", { username: trimmed, avatar_url: avatar });
      queryClient.setQueryData(["me"], response.data);
      setSaved(true);
      window.setTimeout(() => router.push("/chat"), 600);
    } catch (err) {
      setError(getApiErrorCode(err) === "USER_EXISTS" ? "That name is already taken." : getApiErrorMessage(err, "Could not update your profile."));
    } finally { setBusy(false); }
  }

  return <main className="profile-page">
    <section className="profile-card">
      <Link href="/chat" className="back-link"><BsArrowLeft /> Back to messages</Link>
      <p className="eyebrow">YOUR PROFILE</p>
      <h1>Make it feel like you.</h1>
      <p className="muted">Update the name and photo your friends see when you chat.</p>
      <form onSubmit={submit} className="profile-form">
        <div className="profile-avatar-wrap">
          <div className="profile-avatar">{avatar ? <img src={avatar} alt="Profile preview" /> : initials(name || "ME")}</div>
          <label className="avatar-upload"><BsCamera size={16} /> Change photo<input type="file" accept="image/*" onChange={chooseAvatar} /></label>
          {avatar && <button type="button" className="remove-photo" onClick={() => setAvatar(null)}>Remove photo</button>}
        </div>
        <label className="profile-label">Display name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={50} autoComplete="name" /></label>
        <div className="profile-email"><span>Email</span><strong>{me.data?.email ?? "Loading…"}</strong><small>Email can’t be changed here.</small></div>
        {error && <p className="form-error">{error}</p>}
        <button disabled={busy || !me.data} className="primary-button profile-save">{saved ? <><BsCheck2 /> Saved</> : busy ? "Saving…" : "Save changes"}</button>
      </form>
    </section>
  </main>;
}
