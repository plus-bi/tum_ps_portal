const plusBi = <a href="https://plus.bi" target="_blank" rel="noopener noreferrer">Plus BI</a>;

export default function Disclaimer({lang}: {lang: "en" | "de"}) {
  return lang === "de"
    ? <>Dies ist keine offizielle TUM-Website und wird weder von der TUM unterstützt noch mit ihr in Verbindung gebracht.<br/>Sie wird als kostenlose Serviceleistung von {plusBi} (einem TUM-Alumnus) bereitgestellt.</>
    : <>This is not an official TUM website and is not endorsed by or associated with TUM.<br/>It is provided as a courtesy service by {plusBi} (a TUM alumnus).</>;
}
