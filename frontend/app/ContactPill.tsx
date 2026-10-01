"use client";

import {useEffect, useRef, useState, type FormEvent} from "react";
import styles from "./ContactPill.module.css";

type Language = "en" | "de";
type TurnstileApi = {
  render: (container: HTMLElement, options: {
    sitekey: string;
    theme: "dark";
    callback: (token: string) => void;
    "expired-callback": () => void;
    "error-callback": () => void;
  }) => string;
  remove: (widgetId: string) => void;
  reset: (widgetId?: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let turnstileScript: Promise<TurnstileApi> | undefined;

function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (!turnstileScript) {
    turnstileScript = new Promise<TurnstileApi>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      script.onload = () => window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile did not load"));
      script.onerror = () => reject(new Error("Turnstile did not load"));
      document.head.appendChild(script);
    }).catch((error: unknown) => {
      turnstileScript = undefined;
      throw error;
    });
  }
  return turnstileScript!;
}

const text = {
  en: {
    contact: "Contact",
    title: "Send us a message",
    intro: "Questions or feedback? We’d be glad to hear from you.",
    email: "Your email",
    emailPlaceholder: "you@example.com",
    message: "Message",
    messagePlaceholder: "How can we help?",
    send: "Send message",
    sending: "Sending…",
    close: "Close contact form",
    loading: "Loading spam protection…",
    captchaError: "Spam protection could not load. Please try again.",
    configError: "The contact form is temporarily unavailable.",
    captchaRequired: "Please complete the spam check before sending.",
    sendError: "Your message could not be sent. Please try again.",
    sent: "Thanks for your message. We’ll get back to you by email.",
    protection: "Spam protection by",
    privacy: "Privacy policy",
    honeypot: "Leave this field empty",
  },
  de: {
    contact: "Kontakt",
    title: "Schreib uns eine Nachricht",
    intro: "Fragen oder Feedback? Wir freuen uns auf deine Nachricht.",
    email: "Deine E-Mail-Adresse",
    emailPlaceholder: "du@beispiel.de",
    message: "Nachricht",
    messagePlaceholder: "Wie können wir helfen?",
    send: "Nachricht senden",
    sending: "Wird gesendet…",
    close: "Kontaktformular schließen",
    loading: "Spamschutz wird geladen…",
    captchaError: "Der Spamschutz konnte nicht geladen werden. Bitte versuche es erneut.",
    configError: "Das Kontaktformular ist vorübergehend nicht verfügbar.",
    captchaRequired: "Bitte schließe vor dem Senden die Spamprüfung ab.",
    sendError: "Deine Nachricht konnte nicht gesendet werden. Bitte versuche es erneut.",
    sent: "Danke für deine Nachricht. Wir antworten dir per E-Mail.",
    protection: "Spamschutz von",
    privacy: "Datenschutz",
    honeypot: "Dieses Feld leer lassen",
  },
} satisfies Record<Language, Record<string, string>>;

export default function ContactPill() {
  const [language, setLanguage] = useState<Language>("en");
  const [open, setOpen] = useState(false);
  const [consentVisible, setConsentVisible] = useState(false);
  const [siteKey, setSiteKey] = useState("");
  const [configError, setConfigError] = useState(false);
  const [configAttempt, setConfigAttempt] = useState(0);
  const [captchaError, setCaptchaError] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const captchaRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | undefined>(undefined);
  const copy = text[language];

  useEffect(() => {
    setLanguage(window.location.pathname.split("/")[1] === "de" ? "de" : "en");
  }, []);

  useEffect(() => {
    const updateConsentVisibility = () => setConsentVisible(Boolean(document.querySelector(".analytics-consent")));
    updateConsentVisibility();
    const observer = new MutationObserver(updateConsentVisibility);
    observer.observe(document.body, {childList: true, subtree: true});
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setSiteKey("");
    setConfigError(false);
    fetch("/api/v1/contact/config", {cache: "no-store"})
      .then(async (response) => {
        if (!response.ok) throw new Error("Contact form is not configured");
        return response.json() as Promise<{site_key: string}>;
      })
      .then(({site_key}) => {
        if (active) setSiteKey(site_key);
      })
      .catch(() => {
        if (active) setConfigError(true);
      });
    return () => { active = false; };
  }, [open, configAttempt]);

  useEffect(() => {
    if (!open || !siteKey || !captchaRef.current) return;
    let active = true;
    setCaptchaError(false);
    loadTurnstile()
      .then((turnstile) => {
        if (!active || !captchaRef.current) return;
        widgetIdRef.current = turnstile.render(captchaRef.current, {
          sitekey: siteKey,
          theme: "dark",
          callback: (token) => setCaptchaToken(token),
          "expired-callback": () => setCaptchaToken(""),
          "error-callback": () => {
            setCaptchaToken("");
            setCaptchaError(true);
          },
        });
      })
      .catch(() => {
        if (active) setCaptchaError(true);
      });
    return () => {
      active = false;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = undefined;
      }
    };
  }, [open, siteKey]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        setCaptchaToken("");
        setError("");
        setSent(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSent(false);
    if (!captchaToken) {
      setError(copy.captchaRequired);
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/v1/contact", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({email, message, turnstile_token: captchaToken, website: honeypot}),
      });
      if (!response.ok) throw new Error("Message delivery failed");
      setSent(true);
      setEmail("");
      setMessage("");
      setHoneypot("");
    } catch {
      setError(copy.sendError);
    } finally {
      setSubmitting(false);
      setCaptchaToken("");
      if (widgetIdRef.current && window.turnstile) window.turnstile.reset(widgetIdRef.current);
    }
  }

  function closePanel() {
    setOpen(false);
    setCaptchaToken("");
    setError("");
    setSent(false);
  }

  return <div className={styles.root} data-consent-visible={consentVisible ? "true" : undefined}>
    {open && <section id="contact-panel" className={styles.panel} role="dialog" aria-modal="false" aria-labelledby="contact-title" aria-describedby="contact-intro">
      <header className={styles.header}>
        <div>
          <h2 id="contact-title">{copy.title}</h2>
          <p id="contact-intro">{copy.intro}</p>
        </div>
        <button type="button" className={styles.close} aria-label={copy.close} onClick={closePanel}>×</button>
      </header>

      {configError ? <div className={styles.unavailable} role="alert">
        <p>{copy.configError}</p>
        <button type="button" className={styles.retry} onClick={() => setConfigAttempt((attempt) => attempt + 1)}>
          {language === "de" ? "Erneut versuchen" : "Try again"}
        </button>
      </div> : <form className={styles.form} onSubmit={submit}>
        <label className={styles.field}>
          <span>{copy.email}</span>
          <input type="email" name="email" autoComplete="email" maxLength={254} required value={email}
            placeholder={copy.emailPlaceholder} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className={styles.field}>
          <span>{copy.message}</span>
          <textarea name="message" rows={4} minLength={1} maxLength={5000} required value={message}
            placeholder={copy.messagePlaceholder} onChange={(event) => setMessage(event.target.value)} />
        </label>

        <div className={styles.trap} aria-hidden="true">
          <label>{copy.honeypot}<input name="website" tabIndex={-1} autoComplete="off" value={honeypot}
            onChange={(event) => setHoneypot(event.target.value)} /></label>
        </div>

        <div className={styles.captcha}>
          {!siteKey && !configError && <span className={styles.captchaHint}>{copy.loading}</span>}
          <div ref={captchaRef} />
          {captchaError && <span className={styles.captchaError}>{copy.captchaError}</span>}
        </div>
        <p className={styles.protection}>{copy.protection} <a href="https://www.cloudflare.com/products/turnstile/" target="_blank" rel="noopener noreferrer">Cloudflare Turnstile</a>. <a href={`/${language}/privacy`}>{copy.privacy}</a></p>
        {error && <p className={styles.error} role="alert">{error}</p>}
        {sent && <p className={styles.success} role="status">{copy.sent}</p>}
        <button className={styles.submit} type="submit" disabled={submitting || !captchaToken || captchaError}>
          {submitting ? copy.sending : copy.send}
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13M10 4l6 6-6 6" /></svg>
        </button>
      </form>}
    </section>}

    <button type="button" className={styles.launcher} aria-expanded={open} aria-controls="contact-panel"
      onClick={() => open ? closePanel() : setOpen(true)}>
      {open ? <span className={styles.launcherClose} aria-hidden="true">×</span> : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5 8 8 0 0 1-3.6-.85L4 20l1.85-4.9A7.5 7.5 0 1 1 20 11.5Z" /><path d="M8.5 11.5h7M8.5 14h4" /></svg>}
      <span>{copy.contact}</span>
    </button>
  </div>;
}
