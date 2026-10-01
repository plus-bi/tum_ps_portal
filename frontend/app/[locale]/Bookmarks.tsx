"use client";

import {useEffect, useState} from "react";
import styles from "./Bookmarks.module.css";

const COOKIE_NAME = "project_bookmarks";
const CHANGE_EVENT = "project-bookmarks-change";
const MAX_COOKIE_VALUE_LENGTH = 3500;
const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{0,127}$/;
let aliasRequest: Promise<Record<string, string>> | undefined;

function bookmarkAliases(): Promise<Record<string, string>> {
  aliasRequest ||= fetch("/api/v1/project-aliases").then(async (response) => {
    if (!response.ok) throw new Error("Alias lookup unavailable");
    return await response.json() as Record<string, string>;
  }).catch(() => { aliasRequest = undefined; return {}; });
  return aliasRequest;
}

function writeBookmarks(bookmarks: string[]): boolean {
  const value = encodeURIComponent(JSON.stringify(bookmarks));
  if (value.length > MAX_COOKIE_VALUE_LENGTH) return false;
  document.cookie = `${COOKIE_NAME}=${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  return document.cookie.split("; ").some((part) => part === `${COOKIE_NAME}=${value}`);
}

function readBookmarks(): string[] {
  const value = document.cookie.split("; ").find((part) => part.startsWith(`${COOKIE_NAME}=`))?.slice(COOKIE_NAME.length + 1);
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(decodeURIComponent(value));
    return Array.isArray(parsed) ? [...new Set(parsed.filter((slug): slug is string => typeof slug === "string" && SLUG_PATTERN.test(slug)))] : [];
  } catch {
    return [];
  }
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    const sync = async () => {
      const aliases = await bookmarkAliases();
      if (!mounted) return;
      const stored = readBookmarks();
      const canonical = [...new Set(stored.map((slug) => SLUG_PATTERN.test(aliases[slug] || "") ? aliases[slug] : slug))];
      if (JSON.stringify(stored) !== JSON.stringify(canonical)) writeBookmarks(canonical);
      setBookmarks(canonical); setLoaded(true);
    };
    sync();
    window.addEventListener(CHANGE_EVENT, sync);
    window.addEventListener("pageshow", sync);
    return () => {
      mounted = false;
      window.removeEventListener(CHANGE_EVENT, sync);
      window.removeEventListener("pageshow", sync);
    };
  }, []);

  function toggle(slug: string) {
    if (!SLUG_PATTERN.test(slug)) return;
    const current = readBookmarks();
    const next = current.includes(slug) ? current.filter((item) => item !== slug) : [...current, slug];
    if (writeBookmarks(next)) {
      setError(false);
      window.dispatchEvent(new Event(CHANGE_EVENT));
    } else {
      setError(true);
    }
  }

  return {bookmarks, loaded, error, toggle};
}

export function BookmarkButton({slug, lang, saved, onToggle, disabled = false}: {
  slug: string; lang: "en" | "de"; saved: boolean; onToggle: (slug: string) => void; disabled?: boolean;
}) {
  const label = lang === "de" ? (saved ? "Lesezeichen entfernen" : "Projekt merken") : (saved ? "Remove bookmark" : "Bookmark project");
  return <button type="button" className={`${styles.button}${saved ? ` ${styles.saved}` : ""}`}
    aria-label={label} aria-pressed={saved} title={label} disabled={disabled} onClick={() => onToggle(slug)}>
    <svg viewBox="0 0 24 24" width="17" height="17" fill={saved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 3.75h12v16.5l-6-4-6 4z"/></svg>
    <span>{lang === "de" ? (saved ? "Gemerkt" : "Merken") : (saved ? "Saved" : "Save")}</span>
  </button>;
}

export function SavedProjectsPill({lang, active}: {lang: "en" | "de"; active: boolean}) {
  const {bookmarks, loaded} = useBookmarks();
  const note = lang === "de"
    ? "In einem Cookie dieses Browsers gespeichert. Beim Löschen der Cookies gehen die Lesezeichen verloren."
    : "Stored in a cookie on this browser. Clearing cookies removes bookmarks.";
  return <span className="saved-pill-wrapper">
    <a className="saved-pill" href={active ? `/${lang}` : `/${lang}?saved=1`}
      aria-current={active ? "page" : undefined} aria-describedby="saved-projects-note">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 3.75h12v16.5l-6-4-6 4z"/></svg>
      {lang === "de" ? "Gemerkte Projekte" : "Saved projects"}
      <span className="saved-count">{loaded ? bookmarks.length : "…"}</span>
    </a>
    <span className="saved-tooltip" id="saved-projects-note" role="tooltip">{note}</span>
  </span>;
}

export function ProjectBookmark({slug, lang}: {slug: string; lang: "en" | "de"}) {
  const {bookmarks, loaded, error, toggle} = useBookmarks();
  return <span className={styles.detailControl}>
    <BookmarkButton slug={slug} lang={lang} saved={bookmarks.includes(slug)} onToggle={toggle} disabled={!loaded}/>
    {error && <span role="alert" className={styles.error}>{lang === "de" ? "Lesezeichen konnte nicht gespeichert werden. Prüfe die Cookie-Einstellungen oder die Anzahl gespeicherter Projekte." : "Could not save the bookmark. Check cookie settings or the number of saved projects."}</span>}
  </span>;
}
