"use client";

import {useEffect, useRef, useState} from "react";
import {usePathname} from "next/navigation";
import Link from "next/link";

const MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA4_MEASUREMENT_ID ?? "";
const STORAGE_KEY = "psidp_analytics_consent";
const SETTINGS_EVENT = "psidp-analytics-settings";
const DISABLE_KEY = `ga-disable-${MEASUREMENT_ID}`;

type Choice = "granted" | "denied";

declare global {
  interface Window {
    dataLayer?: unknown[][];
    gtag?: (...args: unknown[]) => void;
  }
}

function clearAnalyticsCookies() {
  if (!MEASUREMENT_ID) return;
  for (const name of ["_ga", `_ga_${MEASUREMENT_ID.slice(2)}`]) {
    document.cookie = `${name}=; Path=/; Max-Age=0`;
    document.cookie = `${name}=; Domain=${location.hostname}; Path=/; Max-Age=0`;
  }
}

export function AnalyticsSettingsButton({lang}: {lang: "en" | "de"}) {
  if (!MEASUREMENT_ID) return null;
  return <button type="button" className="footer-settings" onClick={() => window.dispatchEvent(new Event(SETTINGS_EVENT))}>
    {lang === "de" ? "Cookie-Einstellungen" : "Cookie settings"}
  </button>;
}

export default function AnalyticsConsent() {
  const pathname = usePathname();
  const lang = pathname?.startsWith("/de") ? "de" : "en";
  const [choice, setChoice] = useState<Choice | null | undefined>(undefined);
  const [showSettings, setShowSettings] = useState(false);
  const initialized = useRef(false);
  const lastPage = useRef<string | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      setChoice(stored === "granted" || stored === "denied" ? stored : null);
    } catch {
      setChoice(null);
    }
    const openSettings = () => setShowSettings(true);
    window.addEventListener(SETTINGS_EVENT, openSettings);
    return () => window.removeEventListener(SETTINGS_EVENT, openSettings);
  }, []);

  useEffect(() => {
    if (!MEASUREMENT_ID || choice !== "granted" || !pathname) return;
    Object.assign(window, {[DISABLE_KEY]: false});
    if (!initialized.current) {
      window.dataLayer = window.dataLayer || [];
      window.gtag = (...args: unknown[]) => { window.dataLayer?.push(args); };
      window.gtag("consent", "default", {
        analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied",
      });
      window.gtag("js", new Date());
      window.gtag("config", MEASUREMENT_ID, {send_page_view: false, cookie_domain: location.hostname});
      const script = document.createElement("script");
      script.id = "psidp-ga4";
      script.async = true;
      script.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
      document.head.appendChild(script);
      initialized.current = true;
    } else {
      window.gtag?.("consent", "update", {analytics_storage: "granted"});
    }
    if (lastPage.current !== pathname) {
      window.gtag?.("event", "page_view", {page_location: `${location.origin}${pathname}`, page_path: pathname});
      lastPage.current = pathname;
    }
  }, [choice, pathname]);

  function saveChoice(next: Choice) {
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* Keep the choice for this visit. */ }
    if (next === "denied") {
      Object.assign(window, {[DISABLE_KEY]: true});
      window.gtag?.("consent", "update", {analytics_storage: "denied"});
      clearAnalyticsCookies();
      lastPage.current = null;
    }
    setChoice(next);
    setShowSettings(false);
  }

  if (!MEASUREMENT_ID || choice === undefined || (choice !== null && !showSettings)) return null;

  return <aside className="analytics-consent" aria-label={lang === "de" ? "Analyse-Cookies" : "Analytics cookies"}>
    <div>
      <strong>{lang === "de" ? "Optionale Nutzungsanalyse" : "Optional analytics"}</strong>
      <p>{lang === "de"
        ? "Mit deiner Zustimmung verwenden wir Google Analytics, um die Nutzung dieses Beta-Dienstes zu verstehen. Ohne Zustimmung laden wir das Analyse-Skript nicht."
        : "With your permission, we use Google Analytics to understand how this beta service is used. We do not load the analytics script without it."} <Link href={`/${lang}/privacy`}>{lang === "de" ? "Datenschutzerklärung" : "Privacy policy"}</Link></p>
    </div>
    <div className="analytics-actions">
      <button type="button" onClick={() => saveChoice("denied")}>{lang === "de" ? "Ablehnen" : "Decline"}</button>
      <button type="button" className="analytics-allow" onClick={() => saveChoice("granted")}>{lang === "de" ? "Zustimmen" : "Allow analytics"}</button>
    </div>
  </aside>;
}
