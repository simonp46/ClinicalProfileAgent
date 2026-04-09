"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getMyProfile, getProfileAssetBlob, logout } from "@/lib/api";
import { endSession } from "@/lib/auth";
import type { TherapistProfile } from "@/lib/types";

function getInitials(profile: TherapistProfile | null): string {
  if (!profile?.full_name?.trim()) {
    return "RI";
  }

  const parts = profile.full_name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "RI";
}

export function ProfileMenu() {
  const [profile, setProfile] = useState<TherapistProfile | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [loadingLogout, setLoadingLogout] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const photoUrlRef = useRef<string | null>(null);

  const initials = useMemo(() => getInitials(profile), [profile]);

  const loadProfile = useCallback(async (): Promise<void> => {
    try {
      const nextProfile = await getMyProfile();
      setProfile(nextProfile);

      if (photoUrlRef.current) {
        URL.revokeObjectURL(photoUrlRef.current);
        photoUrlRef.current = null;
        setPhotoUrl(null);
      }

      if (nextProfile.profile_photo_path) {
        const blob = await getProfileAssetBlob("photo");
        const objectUrl = URL.createObjectURL(blob);
        photoUrlRef.current = objectUrl;
        setPhotoUrl(objectUrl);
      }
    } catch {
      setProfile(null);
      if (photoUrlRef.current) {
        URL.revokeObjectURL(photoUrlRef.current);
        photoUrlRef.current = null;
        setPhotoUrl(null);
      }
    }
  }, []);

  useEffect(() => {
    void loadProfile();

    function handleProfileUpdated() {
      void loadProfile();
    }

    function handleClickOutside(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("profile-updated", handleProfileUpdated);
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("profile-updated", handleProfileUpdated);
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [loadProfile]);

  useEffect(() => {
    return () => {
      if (photoUrlRef.current) {
        URL.revokeObjectURL(photoUrlRef.current);
      }
    };
  }, []);

  async function onLogout(): Promise<void> {
    setLoadingLogout(true);
    try {
      await logout();
    } catch {
      // We still clear the client session when the refresh cookie is already invalid.
    } finally {
      endSession("logout");
      setLoadingLogout(false);
    }
  }

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        aria-label="Abrir menu de usuario"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full border-2 border-white bg-brand-100 shadow-md ring-1 ring-brand-200 transition hover:scale-[1.02] hover:shadow-lg sm:h-12 sm:w-12"
      >
        {photoUrl ? (
          <img src={photoUrl} alt="Foto de perfil" className="h-full w-full object-cover" />
        ) : (
          <span className="text-sm font-semibold text-brand-700 sm:text-base">{initials}</span>
        )}
      </button>

      {open ? (
        <div className="absolute right-0 top-full z-30 mt-3 w-[15.5rem] overflow-hidden rounded-2xl border border-brand-200 bg-white/95 p-2 shadow-2xl backdrop-blur-sm sm:w-[17rem]">
          <div className="border-b border-slate-100 px-3 py-3">
            <p className="truncate text-sm font-semibold text-ink">{profile?.full_name ?? "Perfil profesional"}</p>
            <p className="truncate text-xs text-slate-500">{profile?.email ?? "Sesion activa"}</p>
          </div>

          <div className="py-2">
            <Link
              href="/profile"
              onClick={() => setOpen(false)}
              className="flex w-full items-center rounded-xl px-3 py-2 text-sm text-ink transition hover:bg-brand-50"
            >
              Editar perfil
            </Link>
            <button
              type="button"
              disabled={loadingLogout}
              onClick={() => void onLogout()}
              className="flex w-full items-center rounded-xl px-3 py-2 text-left text-sm font-medium text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loadingLogout ? "Cerrando..." : "Cerrar sesion"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
