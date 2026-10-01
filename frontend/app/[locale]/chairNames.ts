import type {Project} from "./CatalogClient";

export function localizedChairName(name: string | null | undefined, lang: "en" | "de") {
  if (name === "Controlling" || name === "Management Accounting") {
    return lang === "de" ? "Controlling" : "Management Accounting";
  }
  return name;
}

export function localizeProjectChair(project: Project, lang: "en" | "de"): Project {
  return {...project, chair: localizedChairName(project.chair, lang) || null,
    source_name: localizedChairName(project.source_name, lang),
    academic_units: project.academic_units?.map((unit) => ({...unit,
      canonical_name: localizedChairName(unit.canonical_name || unit.name, lang) || null,
    }))};
}
