import Image from "next/image";
import Link from "next/link";
import plusBiLogo from "./plus-bi-logo.png";

function UsFlag() {
  return <svg className="flag" viewBox="0 0 19 10" aria-hidden="true" focusable="false">
    <rect width="19" height="10" fill="#b22234"/>
    <path d="M0 1.15h19M0 2.7h19M0 4.23h19M0 5.77h19M0 7.3h19M0 8.85h19" stroke="#fff" strokeWidth=".77"/>
    <rect width="7.6" height="5.38" fill="#3c3b6e"/>
  </svg>;
}

function DeFlag() {
  return <svg className="flag" viewBox="0 0 5 3" aria-hidden="true" focusable="false">
    <rect width="5" height="1" fill="#000"/><rect y="1" width="5" height="1" fill="#dd0000"/><rect y="2" width="5" height="1" fill="#ffce00"/>
  </svg>;
}

export default function SiteHeader({lang, brand, enHref, deHref}: {lang: "en" | "de"; brand: string; enHref: string; deHref: string}) {
  return <header className="top"><div className="shell">
    <Link className="brand" href={`/${lang}`}><Image className="brand-mark" src={plusBiLogo} alt="Plus BI" width={30} height={30} priority unoptimized/><span className="brand-text">{brand}</span></Link>
    <div className="top-actions">
      <nav className="lang" aria-label="Language">
        <Link href={enHref} lang="en" aria-current={lang === "en" ? "true" : undefined}><UsFlag/>EN</Link>
        <Link href={deHref} lang="de" aria-current={lang === "de" ? "true" : undefined}><DeFlag/>DE</Link>
      </nav>
    </div>
  </div></header>;
}
