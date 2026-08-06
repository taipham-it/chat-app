"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { RiChat3Fill } from "react-icons/ri";
import { apiClient, clearLegacyTokenStorage, getApiErrorCode, getApiErrorMessage } from "@/lib/api-client";

export default function RegisterPage() {
  const router = useRouter(); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const data = new FormData(event.currentTarget);
    const body = { email: data.get("email"), username: data.get("username"), password: data.get("password") };
    try { await apiClient.post("/auth/register", body); await apiClient.post("/auth/login", { email: body.email, password: body.password });
      clearLegacyTokenStorage(); router.push("/chat");
    } catch (err: unknown) {
      if (["USER_EMAIL_EXISTS", "USER_EXISTS"].includes(getApiErrorCode(err) ?? "")) {
        try {
          await apiClient.post("/auth/login", {
            email: body.email,
            password: body.password,
          });
          clearLegacyTokenStorage();
          router.push("/chat");
          return;
        } catch {
          setError("This email is already registered. Sign in with the original password.");
          return;
        }
      }
      setError(getApiErrorMessage(err, "Could not create your account."));
    } finally { setBusy(false); }
  }
  return <main className="auth-page"><section className="auth-card"><div className="brand-mark"><RiChat3Fill size={27}/></div>
    <p className="eyebrow">START A CONVERSATION</p><h1>A quieter place to connect.</h1><p className="muted">Simple, quick, and built around the people who matter.</p>
    <form onSubmit={submit} className="auth-form"><label>Username<input required minLength={3} name="username" placeholder="yourname"/></label>
      <label>Email<input required type="email" name="email" placeholder="you@example.com"/></label><label>Password<input required minLength={8} type="password" name="password" placeholder="Upper, lower & number"/></label>
      {error && <p className="form-error">{error}</p>}<button disabled={busy} className="primary-button">{busy ? "Creating…" : "Create account"}</button>
    </form><p className="auth-switch">Already have an account? <Link href="/login">Sign in</Link></p></section></main>;
}
