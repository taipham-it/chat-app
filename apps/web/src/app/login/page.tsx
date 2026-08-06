"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { RiChat3Fill } from "react-icons/ri";
import { apiClient, clearLegacyTokenStorage, getApiErrorMessage, getGoogleLoginUrl } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("error");
    const messages: Record<string, string> = {
      google_not_configured: "Google sign-in needs a client ID and secret in the server configuration.",
      google_access_denied: "Google sign-in was cancelled.",
      google_invalid_state: "Google sign-in expired. Please try again.",
      google_auth_failed: "Google sign-in could not be completed. Please try again.",
    };
    if (!reason || !messages[reason]) return;
    const timer = window.setTimeout(() => setError(messages[reason]), 0);
    return () => window.clearTimeout(timer);
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      await apiClient.post("/auth/login", { email: data.get("email"), password: data.get("password") });
      clearLegacyTokenStorage();
      router.push("/chat");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Could not sign in. Check your details and try again."));
    } finally { setBusy(false); }
  }
  return <main className="auth-page"><section className="auth-card">
    <div className="brand-mark"><RiChat3Fill size={27}/></div><p className="eyebrow">WELCOME BACK</p>
    <h1>Pick up where you left off.</h1><p className="muted">Your conversations, close at hand.</p>
    <button type="button" className="google-button" onClick={() => window.location.assign(getGoogleLoginUrl())}><span>G</span>Continue with Google</button>
    <div className="auth-divider"><span>or use your password</span></div>
    <form onSubmit={submit} className="auth-form"><label>Email or username<input required type="text" name="email" autoCapitalize="none" placeholder="you@example.com or yourname"/></label>
      <label>Password<input required type="password" name="password" placeholder="Your password"/></label>
      {error && <p className="form-error">{error}</p>}<button disabled={busy} className="primary-button">{busy ? "Signing in…" : "Sign in"}</button>
    </form><p className="auth-switch">New to Relay? <Link href="/register">Create an account</Link></p>
  </section></main>;
}
