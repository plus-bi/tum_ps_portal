import Link from "next/link";
import {AnalyticsSettingsButton} from "../AnalyticsConsent";
import Disclaimer from "./Disclaimer";

export default function SiteFooter({lang}: {lang: "en" | "de"}) {
  return <footer className="footer"><div className="shell footer-content">
    <p className="footer-disclaimer"><Disclaimer lang={lang}/></p>
    <nav className="footer-links" aria-label={lang === "de" ? "Rechtliche Informationen" : "Legal information"}>
      <Link href={`/${lang}/terms`}>{lang === "de" ? "Nutzungsbedingungen" : "Terms of service"}</Link>
      <Link href={`/${lang}/privacy`}>{lang === "de" ? "Datenschutzerklärung" : "Privacy policy"}</Link>
      <AnalyticsSettingsButton lang={lang}/>
    </nav>
  </div></footer>;
}
