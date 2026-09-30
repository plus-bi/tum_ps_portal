import CatalogClient, {type Chair, type Project} from "./CatalogClient";

const copy = {
  en: {brand: "Project Opportunities from TU Munich", titleBefore: "Find a Project Study or IDP that ", titleHighlight: "fits", titleAfter: ".", lede: "Search active Project Studies and Informatics IDPs from audited TUM sources.", search: "Search title, company, topic or chair", filters: "Organizations", entitySearch: "Search organizations", noEntities: "No matching organizations", lastUpdated: "Last updated", age: "Age", under3: "< 3 days", under30: "< 30 days", under60: "< 60 days", under180: "< 180 days", over180: "> 180 days", type: "Type", sort: "Sort", publicationDate: "Publication date", recentlyAdded: "Recently added", display: "Display", all: "All", previous: "Previous", next: "Next", foundOne: "opportunity", foundMany: "opportunities", profile: "Project details", source: "Chair listing page", artifact: "Project document", unknown: "Not specified", published: "Published", added: "Added", filterToggle: "Filters", reset: "Reset filters", noResults: "No matching opportunities", noResultsHint: "Try a broader search or remove some filters.", trustDaily: "Refreshed daily from chair websites", trustSources: "Every listing links to its source", trustChairs: "chairs covered", pagination: "Pagination", savedOnly: "Saved projects", savedNote: "Stored in a cookie on this browser. Clearing cookies removes bookmarks.", noSaved: "Save a project to see it here.", bookmarkError: "Could not save the bookmark. Check cookie settings or the number of saved projects."},
  de: {brand: "Projektangebote der TU München", titleBefore: "Finde ein ", titleHighlight: "passendes", titleAfter: " Projektstudium oder IDP.", lede: "Durchsuche aktuelle Projektstudien und Informatik-IDPs aus geprüften TUM-Quellen.", search: "Titel, Unternehmen, Thema oder Lehrstuhl", filters: "Organisationen", entitySearch: "Organisationen suchen", noEntities: "Keine passenden Organisationen", lastUpdated: "Zuletzt aktualisiert", age: "Alter", under3: "< 3 Tage", under30: "< 30 Tage", under60: "< 60 Tage", under180: "< 180 Tage", over180: "> 180 Tage", type: "Typ", sort: "Sortierung", publicationDate: "Veröffentlichungsdatum", recentlyAdded: "Kürzlich hinzugefügt", display: "Anzeigen", all: "Alle", previous: "Zurück", next: "Weiter", foundOne: "Angebot", foundMany: "Angebote", profile: "Projektdetails", source: "Seite des Lehrstuhls", artifact: "Projektdokument", unknown: "Nicht angegeben", published: "Veröffentlicht", added: "Hinzugefügt", filterToggle: "Filter", reset: "Filter zurücksetzen", noResults: "Keine passenden Angebote", noResultsHint: "Versuche eine allgemeinere Suche oder entferne Filter.", trustDaily: "Täglich von den Lehrstuhlseiten aktualisiert", trustSources: "Jedes Angebot verlinkt seine Quelle", trustChairs: "Lehrstühle erfasst", pagination: "Seitennavigation", savedOnly: "Gemerkte Projekte", savedNote: "In einem Cookie dieses Browsers gespeichert. Beim Löschen der Cookies gehen die Lesezeichen verloren.", noSaved: "Merke ein Projekt, um es hier zu sehen.", bookmarkError: "Lesezeichen konnte nicht gespeichert werden. Prüfe die Cookie-Einstellungen oder die Anzahl gespeicherter Projekte."},
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

type ProjectPage = {items: Project[]; total: number; page: number; page_size: number; last_updated_at?: string; published_profile_filters: string[]};

async function loadProjects(): Promise<ProjectPage> {
  const first = await load<ProjectPage>("/projects?page_size=100", {items: [], total: 0, page: 1, page_size: 100, published_profile_filters: []});
  const additionalPages = Math.ceil(first.total / first.page_size) - 1;
  if (additionalPages <= 0) return first;

  const remaining = await Promise.all(Array.from(
    {length: additionalPages},
    (_, index) => load<ProjectPage>(`/projects?page=${index + 2}&page_size=${first.page_size}`, {items: [], total: 0, page: index + 2, page_size: first.page_size, published_profile_filters: []}),
  ));
  return {...first, items: [...first.items, ...remaining.flatMap((page) => page.items)]};
}

export default async function Catalog({params, searchParams}: {params: Promise<{locale: string}>; searchParams: Promise<{saved?: string | string[]}>}) {
  const [{locale}, query] = await Promise.all([params, searchParams]);
  const lang = locale === "de" ? "de" : "en";
  const [projectData, chairs] = await Promise.all([
    loadProjects(),
    load<Chair[]>("/chairs", []),
  ]);

  return <CatalogClient lang={lang} copy={copy[lang]} initialProjects={projectData.items} lastUpdatedAt={projectData.last_updated_at} chairs={chairs} publishedProfileFilters={projectData.published_profile_filters || []} initialSavedOnly={query.saved === "1"}/>;
}
