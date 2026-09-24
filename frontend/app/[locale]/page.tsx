import CatalogClient, {type Chair, type Department, type Project} from "./CatalogClient";

const copy = {
  en: {brand: "TUM Project Opportunities", title: "Find a Project Study or IDP that fits.", lede: "Search active Project Studies and Informatics IDPs from audited TUM sources.", notice: "This is not an official TUM website and is not endorsed by or associated with TUM. It is provided as a courtesy service by a TUM alumnus.", search: "Search title, company, topic or chair", filters: "Departments", lastUpdated: "Last updated", age: "Age", under3: "< 3 days", under30: "< 30 days", under60: "< 60 days", under180: "< 180 days", over180: "> 180 days", type: "Type", sort: "Sort", publicationDate: "Publication date", recentlyAdded: "Recently added", display: "Display", all: "All", previous: "Previous", next: "Next", foundOne: "opportunity", foundMany: "opportunities", source: "Chair listing page", artifact: "Project document", unknown: "Not specified", published: "Published", current: "current", old: "old", undated: "undated"},
  de: {brand: "TUM-Projektportal", title: "Finde ein passendes Projektstudium oder IDP.", lede: "Durchsuche aktuelle Projektstudien und Informatik-IDPs aus geprüften TUM-Quellen.", notice: "Dies ist keine offizielle TUM-Website und wird weder von der TUM unterstützt noch mit ihr in Verbindung gebracht. Sie wird als kostenlose Serviceleistung von einem TUM-Alumnus bereitgestellt.", search: "Titel, Unternehmen, Thema oder Lehrstuhl", filters: "Departments", lastUpdated: "Zuletzt aktualisiert", age: "Alter", under3: "< 3 Tage", under30: "< 30 Tage", under60: "< 60 Tage", under180: "< 180 Tage", over180: "> 180 Tage", type: "Typ", sort: "Sortierung", publicationDate: "Veröffentlichungsdatum", recentlyAdded: "Kürzlich hinzugefügt", display: "Anzeigen", all: "Alle", previous: "Zurück", next: "Weiter", foundOne: "Angebot", foundMany: "Angebote", source: "Seite des Lehrstuhls", artifact: "Projektdokument", unknown: "Nicht angegeben", published: "Veröffentlicht", current: "aktuell", old: "älter", undated: "undatiert"},
};

export const dynamic = "force-dynamic";

async function load<T>(path: string, fallback: T): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://api:8000/api/v1";
  try {
    const response = await fetch(`${base}${path}`, {cache: "no-store"});
    if (response.ok) return response.json() as Promise<T>;
  } catch {}
  return fallback;
}

type ProjectPage = {items: Project[]; total: number; page: number; page_size: number; last_updated_at?: string};

async function loadProjects(): Promise<ProjectPage> {
  const first = await load<ProjectPage>("/projects?page_size=100", {items: [], total: 0, page: 1, page_size: 100});
  const additionalPages = Math.ceil(first.total / first.page_size) - 1;
  if (additionalPages <= 0) return first;

  const remaining = await Promise.all(Array.from(
    {length: additionalPages},
    (_, index) => load<ProjectPage>(`/projects?page=${index + 2}&page_size=${first.page_size}`, {items: [], total: 0, page: index + 2, page_size: first.page_size}),
  ));
  return {...first, items: [...first.items, ...remaining.flatMap((page) => page.items)]};
}

export default async function Catalog({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  const lang = locale === "de" ? "de" : "en";
  const [projectData, departments, chairs] = await Promise.all([
    loadProjects(),
    load<Department[]>("/departments", []),
    load<Chair[]>("/chairs", []),
  ]);

  return <CatalogClient lang={lang} copy={copy[lang]} initialProjects={projectData.items} lastUpdatedAt={projectData.last_updated_at} departments={departments} chairs={chairs}/>;
}
