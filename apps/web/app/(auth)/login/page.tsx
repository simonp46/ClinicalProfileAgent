"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { login, register, requestPasswordReset, resetPassword } from "@/lib/api";
import { saveAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register" | "reset">("login");
  const [resetStep, setResetStep] = useState<"request" | "confirm">("request");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [googleAccountEmail, setGoogleAccountEmail] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  function switchMode(nextMode: "login" | "register" | "reset") {
    setMode(nextMode);
    setError(null);
    setNotice(null);
    if (nextMode !== "reset") {
      setResetStep("request");
      setResetCode("");
      setNewPassword("");
      setConfirmNewPassword("");
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (mode === "register" && password !== confirmPassword) {
      setError("Las contrasenas no coinciden");
      return;
    }

    if (mode === "reset") {
      if (resetStep === "request") {
        setLoading(true);
        try {
          const result = await requestPasswordReset(email);
          setNotice(result.message);
          setResetStep("confirm");
        } catch (err) {
          setError(err instanceof Error ? err.message : "No se pudo solicitar el codigo de verificacion");
        } finally {
          setLoading(false);
        }
        return;
      }

      if (newPassword !== confirmNewPassword) {
        setError("Las nuevas contrasenas no coinciden");
        return;
      }

      setLoading(true);
      try {
        const result = await resetPassword({
          email,
          code: resetCode,
          new_password: newPassword,
        });
        setNotice(result.message);
        setMode("login");
        setResetStep("request");
        setPassword("");
        setConfirmPassword("");
        setResetCode("");
        setNewPassword("");
        setConfirmNewPassword("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo restablecer la contrasena");
      } finally {
        setLoading(false);
      }
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
    <main className="mx-auto w-full max-w-md rounded-3xl border border-brand-200 bg-white/95 p-6 shadow-panel backdrop-blur-sm sm:p-8">
      <p className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-brand-600">Respiro Integral</p>
      <h1 className="mb-2 text-2xl font-semibold text-ink">Ingreso a la plataforma</h1>
      <p className="mb-6 text-sm text-slate-600">Borradores clinicos con apoyo IA para revision profesional.</p>

      {sessionNotice ? <p className="mb-4 rounded-lg bg-brand-50 p-3 text-sm text-brand-700">{sessionNotice}</p> : null}
      {notice ? <p className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p> : null}

      <div className="mb-5 grid grid-cols-2 gap-2 rounded-xl bg-brand-50 p-1 text-sm">
        <button
          className={`rounded-lg px-3 py-2 transition ${mode === "login" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}
          type="button"
          onClick={() => switchMode("login")}
        >
          Ingresar
        </button>
        <button
          className={`rounded-lg px-3 py-2 transition ${mode === "register" ? "bg-white text-brand-700 shadow-sm" : "text-slate-600"}`}
          type="button"
          onClick={() => switchMode("register")}
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

        {mode === "login" ? (
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
        ) : null}

        {mode === "register" ? (
          <>
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
          </>
        ) : null}

        {mode === "reset" ? (
          <div className="rounded-2xl border border-brand-100 bg-brand-50/60 p-4 text-sm text-slate-700">
            <p className="font-medium text-ink">
              {resetStep === "request"
                ? "Solicita un codigo de verificacion al correo registrado."
                : "Ingresa el codigo recibido y define tu nueva contrasena."}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-600">
              Solo se enviara el codigo si el correo ya existe en la plataforma.
            </p>
          </div>
        ) : null}

        {mode === "reset" && resetStep === "confirm" ? (
          <>
            <label className="block text-sm font-medium text-ink">
              Codigo de verificacion
              <input
                className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
                type="text"
                value={resetCode}
                onChange={(event) => setResetCode(event.target.value)}
                required
              />
            </label>
            <label className="block text-sm font-medium text-ink">
              Nueva contrasena
              <input
                className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                required
              />
            </label>
            <label className="block text-sm font-medium text-ink">
              Confirmar nueva contrasena
              <input
                className="mt-1 w-full rounded-xl border border-brand-200 px-3 py-2 outline-none transition focus:border-brand-500"
                type="password"
                value={confirmNewPassword}
                onChange={(event) => setConfirmNewPassword(event.target.value)}
                required
              />
            </label>
            <button
              type="button"
              className="text-sm font-medium text-brand-700 underline decoration-brand-300 underline-offset-4"
              onClick={() => {
                setResetStep("request");
                setResetCode("");
                setNewPassword("");
                setConfirmNewPassword("");
              }}
            >
              Solicitar un nuevo codigo
            </button>
          </>
        ) : null}

        {error ? <p className="rounded-lg bg-rose-50 p-2 text-sm text-alert">{error}</p> : null}

        <button
          className="w-full rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700"
          type="submit"
          disabled={loading}
        >
          {loading
            ? "Procesando..."
            : mode === "login"
              ? "Ingresar"
              : mode === "register"
                ? "Crear cuenta"
                : resetStep === "request"
                  ? "Enviar codigo"
                  : "Actualizar contrasena"}
        </button>

        {mode === "login" ? (
          <div className="text-center">
            <button
              type="button"
              className="inline-flex text-sm font-medium text-brand-700 underline decoration-brand-300 underline-offset-4"
              onClick={() => switchMode("reset")}
            >
              Restablecer contrasena
            </button>
          </div>
        ) : null}

        {mode === "reset" ? (
          <button
            type="button"
            className="block w-full text-center text-sm font-medium text-slate-600 underline decoration-slate-300 underline-offset-4"
            onClick={() => switchMode("login")}
          >
            Volver a ingresar
          </button>
        ) : null}
      </form>
    </main>
  );
}
