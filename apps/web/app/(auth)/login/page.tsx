"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { login, register } from "@/lib/api";
import { saveAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("Profesional Demo");
  const [email, setEmail] = useState("demo@clinic.com");
  const [password, setPassword] = useState("demo1234");
  const [confirmPassword, setConfirmPassword] = useState("demo1234");
  const [googleAccountEmail, setGoogleAccountEmail] = useState("demo@clinic.com");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const reason = params.get("reason");

    if (reason === "expired" || reason === "unauthorized") {
      setSessionNotice("Tu sesion caduco. Ingresa de nuevo para continuar.");
      return;
    }

    if (reason === "logout") {
      setSessionNotice("Sesion cerrada correctamente.");
      return;
    }

    setSessionNotice(null);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (mode === "register" && password !== confirmPassword) {
      setError("Las contrasenas no coinciden");
      return;
    }

    setLoading(true);
    try {
      const result =
        mode === "login"
          ? await login(email, password)
          : await register({
              full_name: fullName,
              email,
              password,
              google_account_email: googleAccountEmail || undefined,
            });

      saveAuth(result.access_token, result.csrf_token);
      router.push("/sessions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la autenticacion");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-md rounded-3xl border border-brand-200 bg-white/95 p-8 shadow-panel backdrop-blur-sm">
      <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-brand-600">Respiro Integral</p>
      <h1 className="mb-2 text-2xl font-semibold text-ink">Ingreso a la plataforma</h1>
      <p className="mb-6 text-sm text-slate-600">Borradores clinicos con apoyo IA para revision profesional.</p>

      {sessionNotice ? <p className="mb-4 rounded-lg bg-brand-50 p-3 text-sm text-brand-700">{sessionNotice}</p> : null}

      <div className="mb-5 grid grid-cols-2 gap-2 rounded-xl bg-brand-50 p-1 text-sm">
        <button
          className={`rounded-lg px-3 py-2 transition ${
            mode === "login" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"
          }`}
          type="button"
          onClick={() => setMode("login")}
        >
          Ingresar
        </button>
        <button
          className={`rounded-lg px-3 py-2 transition ${
            mode === "register" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"
          }`}
          type="button"
          onClick={() => setMode("register")}
        >
          Registrar
        </button>
      </div>

      <form className="space-y-4" onSubmit={onSubmit}>
        {mode === "register" ? (
          <label className="block text-sm font-medium text-ink">
            Nombre completo
            <input
              className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
            />
          </label>
        ) : null}

        <label className="block text-sm font-medium text-ink">
          Correo
          <input
            className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        {mode === "register" ? (
          <label className="block text-sm font-medium text-ink">
            Correo de Google Workspace (opcional)
            <input
              className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
              type="email"
              value={googleAccountEmail}
              onChange={(event) => setGoogleAccountEmail(event.target.value)}
            />
          </label>
        ) : null}

        <label className="block text-sm font-medium text-ink">
          Contrasena
          <input
            className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        {mode === "register" ? (
          <label className="block text-sm font-medium text-ink">
            Confirmar contrasena
            <input
              className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
          </label>
        ) : null}

        {error ? <p className="rounded-lg bg-rose-50 p-2 text-sm text-alert">{error}</p> : null}

        <button
          className="w-full rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700"
          type="submit"
          disabled={loading}
        >
          {loading ? "Procesando..." : mode === "login" ? "Ingresar" : "Crear cuenta"}
        </button>
      </form>
    </main>
  );
}
