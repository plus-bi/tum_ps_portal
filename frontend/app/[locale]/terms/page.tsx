import type {Metadata} from "next";
import Link from "next/link";
import SiteFooter from "../SiteFooter";
import SiteHeader from "../SiteHeader";

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  return {title: locale === "de" ? "Nutzungsbedingungen | Plus BI Projektangebote" : "Terms of service | Plus BI Project Opportunities"};
}

export default async function TermsPage({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  const lang = locale === "de" ? "de" : "en";

  return <>
    <SiteHeader lang={lang} brand={lang === "de" ? "Projektangebote der TU München" : "Project Opportunities from TU Munich"} enHref="/en/terms" deHref="/de/terms"/>
    <main className="shell legal-page">
      {lang === "de" ? <>
        <h1>Nutzungsbedingungen</h1>
        <p className="legal-intro">Stand: 30. September 2026. Dieser kostenlose Dienst wird von Plus BI als Beta-Version bereitgestellt.</p>
        <h2>Unabhängiger Dienst</h2>
        <p>Dies ist keine offizielle Website der Technischen Universität München (TUM). Der Dienst ist weder mit der TUM verbunden noch wird er von ihr unterstützt oder empfohlen. Plus BI betreibt ihn als Serviceleistung eines TUM-Alumnus.</p>
        <h2>Informationen zu Projektangeboten</h2>
        <p>Der Dienst sammelt und strukturiert öffentlich zugängliche Projektangebote. Angaben können unvollständig, veraltet oder fehlerhaft sein. Auch automatisch extrahierte Zusammenfassungen und Filter können Inhalte falsch wiedergeben. Maßgeblich sind stets die verlinkten Originalquellen und die Angaben des jeweiligen Projektanbieters. Prüfe insbesondere Fristen, Voraussetzungen und Verfügbarkeit dort, bevor du dich bewirbst oder andere Entscheidungen triffst.</p>
        <p>Unsere Crawler beachten die für jede abgerufene Website und URL geltenden Crawling-Regeln, einschließlich der robots.txt-Vorgaben und Abrufabstände. Die Quellen werden vor der Aufnahme geprüft; Zugriffe auf nicht freigegebene URLs werden unterbunden.</p>
        <h2>Beta-Verfügbarkeit</h2>
        <p>Funktionen und Inhalte können sich ändern, zeitweise ausfallen oder eingestellt werden. Es besteht kein Anspruch auf eine bestimmte Verfügbarkeit, Vollständigkeit oder Aktualität.</p>
        <h2>Haftung</h2>
        <p>Plus BI übernimmt, soweit gesetzlich zulässig, keine Haftung für Entscheidungen oder Schäden, die auf unrichtigen, unvollständigen oder nicht mehr aktuellen Projektinformationen beruhen. Die Haftung für Vorsatz, grobe Fahrlässigkeit, Schäden aus der Verletzung von Leben, Körper oder Gesundheit und sonstige gesetzlich zwingende Haftung bleibt unberührt.</p>
        <h2>Externe Seiten und Datenschutz</h2>
        <p>Links führen zu Websites Dritter mit eigenen Inhalten und Regeln. Informationen über das Speichern gemerkter Projekte findest du in der <Link href="/de/privacy">Datenschutzerklärung</Link>.</p>
        <h2>Kontakt</h2>
        <p>Fragen zu diesem Dienst kannst du an <a href="mailto:psidp@giving.plus.bi">psidp@giving.plus.bi</a> senden.</p>
      </> : <>
        <h1>Terms of service</h1>
        <p className="legal-intro">Last updated: 30 September 2026. Plus BI provides this free service in beta.</p>
        <h2>Independent service</h2>
        <p>This is not an official Technical University of Munich (TUM) website. It is not associated with, supported by, or endorsed by TUM. Plus BI provides it as a courtesy service by a TUM alumnus.</p>
        <h2>Project information</h2>
        <p>The service collects and structures publicly available project opportunities. Details may be incomplete, outdated, or incorrect. Automatically extracted summaries and filters may also misrepresent source material. The linked original source and the project provider are authoritative. Check deadlines, requirements, and availability there before applying or making other decisions.</p>
        <p>Our scrapers follow the crawling policies that apply to each website and URL they access, including robots.txt rules and crawl delays. Sources are reviewed before inclusion, and requests to disallowed URLs are blocked.</p>
        <h2>Beta availability</h2>
        <p>Features and content may change, be temporarily unavailable, or be discontinued. We do not guarantee any particular availability, completeness, or freshness.</p>
        <h2>Liability</h2>
        <p>To the extent permitted by law, Plus BI is not liable for decisions or losses caused by inaccurate, incomplete, or outdated project information. Nothing here limits liability for intentional misconduct, gross negligence, injury to life, body, or health, or other liability that cannot legally be excluded.</p>
        <h2>External sites and privacy</h2>
        <p>Links lead to third-party sites with their own content and terms. See our <Link href="/en/privacy">privacy policy</Link> for information about saved project preferences.</p>
        <h2>Contact</h2>
        <p>For questions about this service, email <a href="mailto:psidp@giving.plus.bi">psidp@giving.plus.bi</a>.</p>
      </>}
    </main>
    <SiteFooter lang={lang}/>
  </>;
}
