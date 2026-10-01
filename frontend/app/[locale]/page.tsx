import CatalogClient from "./CatalogClient";
import {loadBootstrap} from "../catalogServer";

const copy = {
  en: {brand: "Project Opportunities from TU Munich", titleBefore: "Find your next Project Study or IDP", titleHighlight: "", titleAfter: "", lede: "Search Project Studies, Informatics IDPs and other projects from audited TUM sources.", search: "Search title, company, topic or chair", filters: "Organizations", entitySearch: "Search organizations", noEntities: "No matching organizations", lastUpdated: "Last updated", age: "Age", under3: "< 3 days", under30: "< 30 days", under60: "< 60 days", under180: "< 180 days", over180: "> 180 days", type: "Type", display: "Display", all: "All", previous: "Previous", next: "Next", foundOne: "opportunity", foundMany: "opportunities", profile: "Project details", source: "Chair listing page", artifact: "Project document", unknown: "Not specified", published: "Published", added: "Added", filterToggle: "Filters", reset: "Reset filters", noResults: "No matching opportunities", noResultsHint: "Try a broader search or remove some filters.", trustDaily: "Refreshed daily from chair websites", trustSources: "Every listing links to its source", trustChairs: "chairs covered", pagination: "Pagination", noSaved: "Save a project to see it here.", bookmarkError: "Could not save the bookmark. Check cookie settings or the number of saved projects."},
  de: {brand: "Projektangebote der TU München", titleBefore: "Finde dein nächstes Projektstudium oder IDP", titleHighlight: "", titleAfter: "", lede: "Durchsuche Projektstudien, Informatik-IDPs und weitere Projekte aus geprüften TUM-Quellen.", search: "Titel, Unternehmen, Thema oder Lehrstuhl", filters: "Organisationen", entitySearch: "Organisationen suchen", noEntities: "Keine passenden Organisationen", lastUpdated: "Zuletzt aktualisiert", age: "Alter", under3: "< 3 Tage", under30: "< 30 Tage", under60: "< 60 Tage", under180: "< 180 Tage", over180: "> 180 Tage", type: "Typ", display: "Anzeigen", all: "Alle", previous: "Zurück", next: "Weiter", foundOne: "Angebot", foundMany: "Angebote", profile: "Projektdetails", source: "Seite des Lehrstuhls", artifact: "Projektdokument", unknown: "Nicht angegeben", published: "Veröffentlicht", added: "Hinzugefügt", filterToggle: "Filter", reset: "Filter zurücksetzen", noResults: "Keine passenden Angebote", noResultsHint: "Versuche eine allgemeinere Suche oder entferne Filter.", trustDaily: "Täglich von den Lehrstuhlseiten aktualisiert", trustSources: "Jedes Angebot verlinkt seine Quelle", trustChairs: "Lehrstühle erfasst", pagination: "Seitennavigation", noSaved: "Merke ein Projekt, um es hier zu sehen.", bookmarkError: "Lesezeichen konnte nicht gespeichert werden. Prüfe die Cookie-Einstellungen oder die Anzahl gespeicherter Projekte."},
};

export const revalidate = 86400;
export function generateStaticParams() { return []; }

export default async function Catalog({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  const lang = locale === "de" ? "de" : "en";
  const projectData = await loadBootstrap();
  return <CatalogClient lang={lang} copy={copy[lang]} bootstrap={projectData}/>;
}
