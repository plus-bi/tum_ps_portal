import type {Metadata} from "next";
import Link from "next/link";
import SiteFooter from "../SiteFooter";
import SiteHeader from "../SiteHeader";

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  return {title: locale === "de" ? "Datenschutzerklärung | Plus BI Projektangebote" : "Privacy policy | Plus BI Project Opportunities"};
}

export default async function PrivacyPage({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  const lang = locale === "de" ? "de" : "en";

  return <>
    <SiteHeader lang={lang} brand={lang === "de" ? "Projektangebote der TU München" : "Project Opportunities from TU Munich"} enHref="/en/privacy" deHref="/de/privacy"/>
    <main className="shell legal-page">
      {lang === "de" ? <>
        <h1>Datenschutzerklärung</h1>
        <p className="legal-intro">Stand: 30. September 2026. Dies ist ein Beta-Dienst von Plus BI, unabhängig von der TUM.</p>
        <h2>Verantwortlicher und Kontakt</h2>
        <p>Plus BI betreibt diesen Dienst. Für Fragen zum Dienst oder zum Datenschutz schreibe an <a href="mailto:psidp@giving.plus.bi">psidp@giving.plus.bi</a>. Weitere Angaben zum Betreiber findest du auf <a href="https://plus.bi" target="_blank" rel="noopener noreferrer">plus.bi</a>.</p>
        <h2>Gemerkte Projekte und Cookies</h2>
        <p>Wenn du ein Projekt merkst, speichern wir dessen Kennung in dem Cookie <code>project_bookmarks</code> in deinem Browser. So bleibt deine Projektauswahl auf diesem Gerät erhalten. Das Cookie wird für höchstens ein Jahr gesetzt; bei einer Änderung wird die Frist erneut gestartet. Du kannst einzelne Projekte entfernen oder das Cookie in deinem Browser löschen. Die gemerkten Projekte werden nicht als Nutzerkonto auf unserem Server gespeichert.</p>
        <p>Das Cookie wird nur gesetzt, wenn du die Merkfunktion benutzt. Wir verwenden es, um die von dir gewünschte Funktion bereitzustellen. Wenn Cookies gesperrt sind, funktioniert das Merken möglicherweise nicht.</p>
        <h2>Aufruf der Website</h2>
        <p>Beim Aufruf der Website werden technisch erforderliche Verbindungsdaten, etwa IP-Adresse, Zeitpunkt und angeforderte URL, durch die Server verarbeitet, um die Seiten auszuliefern und den Betrieb abzusichern. Grundlage ist unser berechtigtes Interesse am sicheren Betrieb des Dienstes (Art. 6 Abs. 1 lit. f DSGVO). Serverprotokolle werden nur so lange aufbewahrt, wie es für Betrieb und Sicherheit erforderlich ist.</p>
        <h2>Externe Quellen</h2>
        <p>Wenn du einen Link zu einer Projektquelle oder zu Plus BI öffnest, verlässt du diesen Dienst. Die jeweilige Website verarbeitet deine Daten nach ihrer eigenen Datenschutzerklärung.</p>
        <h2>Deine Rechte</h2>
        <p>Nach Maßgabe der DSGVO kannst du Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung und Datenübertragbarkeit verlangen sowie einer Verarbeitung auf Grundlage berechtigter Interessen widersprechen. Du kannst dich auch bei einer Datenschutzaufsichtsbehörde beschweren. Kontaktiere Plus BI über die oben genannte E-Mail-Adresse. Weitere Hinweise zur Nutzung stehen in den <Link href="/de/terms">Nutzungsbedingungen</Link>.</p>
      </> : <>
        <h1>Privacy policy</h1>
        <p className="legal-intro">Last updated: 30 September 2026. This is a Plus BI beta service, independent of TUM.</p>
        <h2>Operator and contact</h2>
        <p>Plus BI operates this service. For questions about the service or privacy, email <a href="mailto:psidp@giving.plus.bi">psidp@giving.plus.bi</a>. Further operator information is available at <a href="https://plus.bi" target="_blank" rel="noopener noreferrer">plus.bi</a>.</p>
        <h2>Saved projects and cookies</h2>
        <p>When you save a project, we store its identifier in the <code>project_bookmarks</code> cookie in your browser. This keeps your project choices on this device. The cookie lasts for up to one year; changing your saved projects restarts that period. You can remove individual projects or delete the cookie in your browser. Saved projects are not stored in a user account on our server.</p>
        <p>The cookie is set only when you use the save feature. We use it to provide the feature you requested. Saving projects may fail if cookies are blocked.</p>
        <h2>Visiting the website</h2>
        <p>When you visit, the servers process connection data such as your IP address, time, and requested URL to deliver the pages and protect the service. The legal basis is our legitimate interest in operating the service securely (GDPR Article 6(1)(f)). Server logs are kept only as long as needed for operation and security.</p>
        <h2>External sources</h2>
        <p>Opening a link to a project source or Plus BI takes you to another website. That site processes data under its own privacy policy.</p>
        <h2>Your rights</h2>
        <p>Subject to the GDPR, you may request access, correction, deletion, restriction, and portability of your data, and object to processing based on legitimate interests. You may also complain to a data protection authority. Contact Plus BI at the email address above. See the <Link href="/en/terms">terms of service</Link> for use of the service.</p>
      </>}
    </main>
    <SiteFooter lang={lang}/>
  </>;
}
