"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, Dispatch, SetStateAction, useEffect, useMemo, useState } from "react";

import {
  disconnectGoogleAccount,
  disconnectMicrosoftAccount,
  getGoogleAuthorizationUrl,
  getMicrosoftAuthorizationUrl,
  getMyProfile,
  getProfileAssetBlob,
  logout,
  updateMyProfile,
  uploadProfileAsset,
} from "@/lib/api";
import { endSession, getAccessToken } from "@/lib/auth";
import type { TherapistProfile } from "@/lib/types";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<TherapistProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [connectingGoogle, setConnectingGoogle] = useState(false);
  const [disconnectingGoogle, setDisconnectingGoogle] = useState(false);
  const [connectingMicrosoft, setConnectingMicrosoft] = useState(false);
  const [disconnectingMicrosoft, setDisconnectingMicrosoft] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [googleAccountEmail, setGoogleAccountEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [address, setAddress] = useState("");
  const [profession, setProfession] = useState("");

  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [signaturePreviewUrl, setSignaturePreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const googleStatus = params.get("google");
    const microsoftStatus = params.get("microsoft");
    const reason = params.get("reason");

    if (googleStatus === "connected") {
      setNotice("Cuenta de Google conectada correctamente.");
    } else if (googleStatus === "error") {
      setError(reason ? `No se pudo conectar Google: ${reason}` : "No se pudo conectar Google.");
    }

    if (microsoftStatus === "connected") {
      setNotice("Cuenta de Microsoft Teams conectada correctamente.");
    } else if (microsoftStatus === "error") {
      setError(reason ? `No se pudo conectar Microsoft Teams: ${reason}` : "No se pudo conectar Microsoft Teams.");
    }

    if (googleStatus || microsoftStatus) {
      window.history.replaceState({}, "", "/profile");
    }

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getMyProfile();
        hydrateForm(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo cargar el perfil");
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [router]);

  useEffect(() => {
    void loadAssetPreview("photo", profile?.profile_photo_path, setPhotoPreviewUrl);
    void loadAssetPreview("signature", profile?.signature_image_path, setSignaturePreviewUrl);
  }, [profile?.profile_photo_path, profile?.signature_image_path]);

  useEffect(() => {
    return () => {
      if (photoPreviewUrl) {
        URL.revokeObjectURL(photoPreviewUrl);
      }
      if (signaturePreviewUrl) {
        URL.revokeObjectURL(signaturePreviewUrl);
      }
    };
  }, [photoPreviewUrl, signaturePreviewUrl]);

  const hasTemplatePdf = useMemo(() => Boolean(profile?.template_pdf_path), [profile?.template_pdf_path]);
  const hasTemplateDocx = useMemo(() => Boolean(profile?.template_docx_path), [profile?.template_docx_path]);

  function hydrateForm(data: TherapistProfile): void {
    setProfile(data);
    setFullName(data.full_name ?? "");
    setGoogleAccountEmail(data.google_account_email ?? "");
    setPhone(data.phone ?? "");
    setContactEmail(data.contact_email ?? "");
    setAddress(data.address ?? "");
    setProfession(data.profession ?? "");
  }

  async function loadAssetPreview(
    asset: "photo" | "signature",
    path: string | null | undefined,
    setter: Dispatch<SetStateAction<string | null>>,
  ): Promise<void> {
    setter((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });

    if (!path) {
      return;
    }

    try {
      const blob = await getProfileAssetBlob(asset);
      const objectUrl = URL.createObjectURL(blob);
      setter(objectUrl);
    } catch {
      setter(null);
    }
  }

  async function onSaveProfile(): Promise<void> {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateMyProfile({
        full_name: fullName || null,
        google_account_email: googleAccountEmail || null,
        phone: phone || null,
        contact_email: contactEmail || null,
        address: address || null,
        profession: profession || null,
      });
      hydrateForm(updated);
      setNotice("Perfil actualizado correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el perfil");
    } finally {
      setSaving(false);
    }
  }

  async function onConnectGoogle(): Promise<void> {
    setConnectingGoogle(true);
    setError(null);
    setNotice(null);
    try {
      const authorizationUrl = await getGoogleAuthorizationUrl();
      window.location.assign(authorizationUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar la conexion con Google");
      setConnectingGoogle(false);
    }
  }

  async function onDisconnectGoogle(): Promise<void> {
    setDisconnectingGoogle(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await disconnectGoogleAccount();
      hydrateForm(updated);
      setNotice("Cuenta de Google desconectada correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo desconectar Google");
    } finally {
      setDisconnectingGoogle(false);
    }
  }

  async function onConnectMicrosoft(): Promise<void> {
    setConnectingMicrosoft(true);
    setError(null);
    setNotice(null);
    try {
      const authorizationUrl = await getMicrosoftAuthorizationUrl();
      window.location.assign(authorizationUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar la conexion con Microsoft Teams");
      setConnectingMicrosoft(false);
    }
  }

  async function onDisconnectMicrosoft(): Promise<void> {
    setDisconnectingMicrosoft(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await disconnectMicrosoftAccount();
      hydrateForm(updated);
      setNotice("Cuenta de Microsoft Teams desconectada correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo desconectar Microsoft Teams");
    } finally {
      setDisconnectingMicrosoft(false);
    }
  }

  async function onUploadAsset(asset: "photo" | "signature" | "template", file: File): Promise<void> {
    setUploading(true);
    setError(null);
    setNotice(null);

    try {
      const updated = await uploadProfileAsset(asset, file);
      hydrateForm(updated);
      setNotice("Archivo cargado correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el archivo");
    } finally {
      setUploading(false);
    }
  }

  async function onChangeFile(
    event: ChangeEvent<HTMLInputElement>,
    asset: "photo" | "signature" | "template",
  ): Promise<void> {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    await onUploadAsset(asset, file);
  }

  function triggerBrowserDownload(blob: Blob, fileName: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  async function previewTemplatePdf(): Promise<void> {
    const tab = window.open("", "_blank", "noopener,noreferrer");
    if (!tab) {
      setError("El navegador bloqueo la pestana de previsualizacion.");
      return;
    }

    try {
      const blob = await getProfileAssetBlob("template-pdf");
      const objectUrl = URL.createObjectURL(blob);
      tab.location.href = objectUrl;
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (err) {
      tab.close();
      setError(err instanceof Error ? err.message : "No se pudo abrir la plantilla PDF");
    }
  }

  async function downloadTemplate(type: "template-pdf" | "template-docx"): Promise<void> {
    try {
      const blob = await getProfileAssetBlob(type);
      const extension = type === "template-pdf" ? "pdf" : "docx";
      triggerBrowserDownload(blob, `plantilla-perfil-clinico.${extension}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo descargar la plantilla");
    }
  }

  async function onLogout(): Promise<void> {
    try {
      await logout();
    } catch {
      // The client session still needs to be cleared if the refresh cookie is already invalid.
    } finally {
      endSession("logout");
    }
  }

  if (loading) {
    return <main className="mx-auto max-w-5xl p-6">Cargando perfil...</main>;
  }

  if (!profile) {
    return <main className="mx-auto max-w-5xl p-6">No se encontro el perfil del usuario.</main>;
  }

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-6">
      <header className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-white p-5 shadow-panel">
        <div>
          <p className="text-xs text-slate-500">Cuenta autenticada</p>
          <h1 className="text-xl font-semibold text-ink">Perfil profesional</h1>
          <p className="text-sm text-slate-600">{profile.email}</p>
        </div>
        <div className="flex gap-2">
          <Link href="/sessions" className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            Ir a sesiones
          </Link>
          <button className="rounded-lg border border-slate-300 px-3 py-2 text-sm" onClick={() => void onLogout()}>
            Cerrar sesion
          </button>
        </div>
      </header>

      {error ? <p className="rounded-xl bg-rose-50 p-3 text-sm text-alert">{error}</p> : null}
      {notice ? <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p> : null}

      <section className="rounded-2xl bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="mb-1 text-lg font-semibold text-ink">Conexion con Google</h2>
            <p className="text-sm text-slate-600">
              Autoriza tu cuenta de Google para consultar Google Calendar, Google Meet y las transcripciones de tus reuniones.
            </p>
          </div>
          <div className="rounded-2xl border border-brand-200 bg-brand-50/60 px-4 py-3 text-sm text-ink">
            <p className="font-medium">
              Estado: {profile.google_oauth_connected ? "Cuenta conectada" : "Sin autorizacion activa"}
            </p>
            <p className="text-slate-600">
              {profile.google_oauth_connected
                ? profile.google_oauth_email || profile.google_account_email || "Cuenta vinculada"
                : "Conecta Google para habilitar la lectura real de Calendar y Meet."}
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white"
            disabled={connectingGoogle}
            onClick={() => void onConnectGoogle()}
          >
            {connectingGoogle ? "Redirigiendo a Google..." : "Conectar Google"}
          </button>
          <button
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
            disabled={!profile.google_oauth_connected || disconnectingGoogle}
            onClick={() => void onDisconnectGoogle()}
          >
            {disconnectingGoogle ? "Desconectando..." : "Desconectar Google"}
          </button>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="mb-1 text-lg font-semibold text-ink">Conexion con Microsoft Teams</h2>
            <p className="text-sm text-slate-600">
              Autoriza tu cuenta de Microsoft 365 para trabajar de forma multiplataforma con Teams, calendario y artefactos de reunion.
            </p>
          </div>
          <div className="rounded-2xl border border-brand-200 bg-brand-50/60 px-4 py-3 text-sm text-ink">
            <p className="font-medium">
              Estado: {profile.microsoft_oauth_connected ? "Cuenta conectada" : "Sin autorizacion activa"}
            </p>
            <p className="text-slate-600">
              {profile.microsoft_oauth_connected
                ? profile.microsoft_oauth_email || profile.microsoft_account_email || "Cuenta vinculada"
                : "Conecta Microsoft Teams para habilitar futuras sincronizaciones multiplataforma."}
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white"
            disabled={connectingMicrosoft}
            onClick={() => void onConnectMicrosoft()}
          >
            {connectingMicrosoft ? "Redirigiendo a Microsoft..." : "Conectar Microsoft Teams"}
          </button>
          <button
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
            disabled={!profile.microsoft_oauth_connected || disconnectingMicrosoft}
            onClick={() => void onDisconnectMicrosoft()}
          >
            {disconnectingMicrosoft ? "Desconectando..." : "Desconectar Microsoft Teams"}
          </button>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-panel">
        <h2 className="mb-2 text-lg font-semibold text-ink">Datos personales y de contacto</h2>
        <p className="mb-4 text-xs text-slate-500">
          Puedes trabajar con Google Meet y Microsoft Teams desde un mismo perfil profesional. El pipeline clinico y documental se mantiene comun.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm text-slate-700">
            Nombre completo
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Correo de Google Workspace
            <input
              type="email"
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={googleAccountEmail}
              onChange={(event) => setGoogleAccountEmail(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Telefono
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Email de contacto
            <input
              type="email"
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={contactEmail}
              onChange={(event) => setContactEmail(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700 md:col-span-2">
            Direccion
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700 md:col-span-2">
            Profesion
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={profession}
              onChange={(event) => setProfession(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4">
          <button
            className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white"
            disabled={saving}
            onClick={() => void onSaveProfile()}
          >
            {saving ? "Guardando..." : "Guardar perfil"}
          </button>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl bg-white p-5 shadow-panel">
          <h3 className="text-base font-semibold text-ink">Foto de perfil</h3>
          <p className="mb-3 text-xs text-slate-500">Formatos: JPG, PNG, WEBP.</p>
          {photoPreviewUrl ? (
            <img
              alt="Foto de perfil"
              className="mb-3 h-32 w-32 rounded-full border border-slate-300 object-cover"
              src={photoPreviewUrl}
            />
          ) : (
            <div className="mb-3 flex h-32 w-32 items-center justify-center rounded-full border border-dashed border-slate-300 text-xs text-slate-500">
              Sin foto
            </div>
          )}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={uploading}
            onChange={(event) => void onChangeFile(event, "photo")}
          />
        </article>

        <article className="rounded-2xl bg-white p-5 shadow-panel">
          <h3 className="text-base font-semibold text-ink">Firma personal</h3>
          <p className="mb-3 text-xs text-slate-500">Formatos: JPG, PNG, WEBP.</p>
          {signaturePreviewUrl ? (
            <img
              alt="Firma personal"
              className="mb-3 h-24 w-full max-w-xs rounded border border-slate-300 object-contain"
              src={signaturePreviewUrl}
            />
          ) : (
            <div className="mb-3 flex h-24 w-full max-w-xs items-center justify-center rounded border border-dashed border-slate-300 text-xs text-slate-500">
              Sin firma
            </div>
          )}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={uploading}
            onChange={(event) => void onChangeFile(event, "signature")}
          />
        </article>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-panel">
        <h3 className="text-base font-semibold text-ink">Plantilla para borradores clinicos</h3>
        <p className="mb-3 text-xs text-slate-500">
          Puedes cargar una plantilla PDF, DOC, DOCX o DOCS. Esta plantilla se usara para exportar nuevos borradores.
        </p>
        <input
          type="file"
          accept=".pdf,.doc,.docx,.docs,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={uploading}
          onChange={(event) => void onChangeFile(event, "template")}
        />

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            disabled={!hasTemplatePdf}
            onClick={() => void previewTemplatePdf()}
          >
            Previsualizar PDF
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            disabled={!hasTemplatePdf}
            onClick={() => void downloadTemplate("template-pdf")}
          >
            Descargar PDF
          </button>
          <button
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            disabled={!hasTemplateDocx}
            onClick={() => void downloadTemplate("template-docx")}
          >
            Descargar DOCX
          </button>
        </div>
      </section>
    </main>
  );
}
