import CatalogClient, {type Chair, type Department, type Project} from "./CatalogClient";

const copy = {
  en: {brand: "TUM Project Opportunities", title: "Find a Project Study or IDP that fits.", lede: "Search active Project Studies and Informatics IDPs from audited TUM sources.", notice: "Independent portal — verify details and apply on the original chair website.", search: "Search title, company, topic or chair", filters: "Departments", foundOne: "opportunity", foundMany: "opportunities", source: "Chair listing page", artifact: "Project document", unknown: "Not specified", published: "Published", current: "current", old: "old", undated: "undated"},
  de: {brand: "TUM-Projektportal", title: "Finde ein passendes Projektstudium oder IDP.", lede: "Durchsuche aktuelle Projektstudien und Informatik-IDPs aus geprüften TUM-Quellen.", notice: "Unabhängiges Portal — Details bitte auf der Website des Lehrstuhls prüfen; Bewerbungen erfolgen dort.", search: "Titel, Unternehmen, Thema oder Lehrstuhl", filters: "Departments", foundOne: "Angebot", foundMany: "Angebote", source: "Seite des Lehrstuhls", artifact: "Projektdokument", unknown: "Nicht angegeben", published: "Veröffentlicht", current: "aktuell", old: "älter", undated: "undatiert"},
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

export default async function Catalog({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  const lang = locale === "de" ? "de" : "en";
  const [projectData, departments, chairs] = await Promise.all([
    load<{items: Project[]; total: number}>("/projects?page_size=100", {items: [], total: 0}),
    load<Department[]>("/departments", []),
    load<Chair[]>("/chairs", []),
  ]);

  return <CatalogClient lang={lang} copy={copy[lang]} initialProjects={projectData.items} departments={departments} chairs={chairs}/>;
}
