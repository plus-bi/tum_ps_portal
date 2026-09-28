import Link from "next/link";
import AuthControls from "./AuthControls";

export default function SiteHeader({lang, brand, enHref, deHref}: {lang: "en" | "de"; brand: string; enHref: string; deHref: string}) {
  return <header className="top"><div className="shell">
    <Link className="brand" href={`/${lang}`}><span className="brand-mark" aria-hidden="true">PS</span><span className="brand-text">{brand}</span></Link>
    <div className="top-actions">
      <nav className="lang" aria-label="Language">
        <Link href={enHref} lang="en" aria-current={lang === "en" ? "true" : undefined}>EN</Link>
        <Link href={deHref} lang="de" aria-current={lang === "de" ? "true" : undefined}>DE</Link>
      </nav>
      <AuthControls/>
    </div>
  </div></header>;
}
