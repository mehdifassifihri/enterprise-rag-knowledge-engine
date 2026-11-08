"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { Brand } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
export default function Login() {
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const client = useQueryClient();
  return (
    <main className="login-page">
      <section className="card login-card">
        <Brand />
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Private demo workspace
        </div>
        <h1>
          Good knowledge.
          <br />
          Better decisions.
        </h1>
        <p>
          Sign in to explore your documents, test retrieval and trace answers
          back to their sources.
        </p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setPending(true);
            setError("");
            try {
              const response = await fetch("/api/session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password }),
              });
              if (!response.ok)
                throw new Error(
                  response.status === 401
                    ? "That demo password isn’t correct."
                    : "Demo sign-in is unavailable. Check the server configuration.",
                );
              setPassword("");
              await client.invalidateQueries({ queryKey: ["session"] });
              router.replace("/dashboard");
            } catch (e) {
              setError(e instanceof Error ? e.message : "Sign-in failed");
            } finally {
              setPending(false);
            }
          }}
        >
          <label htmlFor="password">Demo password</label>
          <div className="input-wrap">
            <LockKeyhole size={15} />
            <input
              className="input"
              type="password"
              id="password"
              autoComplete="current-password"
              required
              maxLength={256}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your workspace password"
            />
          </div>
          {error && (
            <p role="alert" style={{ color: "var(--danger)", marginBottom: 0 }}>
              {error}
            </p>
          )}
          <Button type="submit" disabled={pending}>
            {pending ? "Signing in…" : "Open workspace"}
            <ArrowRight size={14} />
          </Button>
        </form>
        <p style={{ fontSize: 10, marginBottom: 0 }}>
          A shared, tenant-bound demo. This is not a multi-user identity system.
        </p>
      </section>
    </main>
  );
}
