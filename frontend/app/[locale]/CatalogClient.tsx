"use client";

import {useMemo, useState} from "react";
import Link from "next/link";
import Disclaimer from "./Disclaimer";
import SiteFooter from "./SiteFooter";
import SiteHeader from "./SiteHeader";
import {BookmarkButton, useBookmarks} from "./Bookmarks";
import {ArrowRightIcon, ExternalIcon, FileIcon, FilterIcon, InfoIcon, LinkIcon, RefreshIcon, SearchIcon} from "./Icons";
import styles from "./CatalogClient.module.css";

type ProfileFilters = {degree_level: ("bachelor" | "master" | "any")[] | null; work_modes: string[] | null; programming_performed: "none" | "some" | "central" | "unknown"; programming_required: "required" | "recommended" | "not_stated"; work_location_mode: "on_site" | "hybrid" | "remote" | "unknown"; working_language: ("en" | "de" | "other")[] | null};
type ProfileField = keyof ProfileFilters;
type OrganizationMention = {name: string; canonical_name: string | null; evidence: {page: number; excerpt: string}; method: string};
export type Project = {slug: string; reference_code: string; title: string; summary?: string; search_summary_en?: string; department: string; chair: string | null; source_name?: string | null; academic_units?: OrganizationMention[]; project_partners?: OrganizationMention[]; opportunity_type: "project_study" | "idp" | "other"; language?: string; topics: string[]; freshness: string; source_url: string; artifact_url?: string; has_profile: boolean; has_description?: boolean; filter_values?: ProfileFilters | null; published_at?: string; first_seen_at: string};
export type Chair = {slug: string; name: string; department: string; source_state: string};

type AgeBand = "lt3" | "lt30" | "lt60" | "lt180" | "gt180";
type OpportunityType = Project["opportunity_type"];
type Copy = {brand: string; titleBefore: string; titleHighlight: string; titleAfter: string; lede: string; search: string; filters: string; entitySearch: string; noEntities: string; lastUpdated: string; age: string; under3: string; under30: string; under60: string; under180: string; over180: string; type: string; display: string; all: string; previous: string; next: string; foundOne: string; foundMany: string; profile: string; source: string; artifact: string; unknown: string; published: string; added: string; filterToggle: string; reset: string; noResults: string; noResultsHint: string; trustDaily: string; trustSources: string; trustChairs: string; pagination: string; noSaved: string; bookmarkError: string};
const ageBands: AgeBand[] = ["lt3", "lt30", "lt60", "lt180", "gt180"];

type FacetOption = {value: string; en: string; de: string};
const profileFacets: Record<ProfileField, {en: string; de: string; options: FacetOption[]}> = {
  degree_level: {en: "Degree level", de: "Studienniveau", options: [
    {value: "bachelor", en: "Bachelor", de: "Bachelor"}, {value: "master", en: "Master", de: "Master"},
    {value: "any", en: "Any level", de: "Alle Studienniveaus"},
  ]},
  work_modes: {en: "Type of work", de: "Art der Arbeit", options: [
    {value: "software_development", en: "Software development", de: "Softwareentwicklung"},
    {value: "data_analysis_ml", en: "Data analysis / ML", de: "Datenanalyse / ML"},
    {value: "modeling_simulation", en: "Modeling / simulation", de: "Modellierung / Simulation"},
    {value: "hardware_lab", en: "Hardware / lab work", de: "Hardware / Laborarbeit"},
    {value: "literature_research", en: "Literature research", de: "Literaturrecherche"},
    {value: "empirical_user_research", en: "Empirical / user research", de: "Empirische / Nutzerforschung"},
    {value: "business_strategy", en: "Business strategy", de: "Unternehmensstrategie"},
    {value: "process_optimization", en: "Process optimization", de: "Prozessoptimierung"},
    {value: "marketing_content", en: "Marketing / content", de: "Marketing / Inhalte"},
    {value: "design_ux", en: "Design / UX", de: "Design / UX"},
  ]},
  programming_performed: {en: "Programming in the project", de: "Programmierung im Projekt", options: [
    {value: "none", en: "No programming", de: "Keine Programmierung"},
    {value: "some", en: "Some", de: "Etwas"}, {value: "central", en: "Central", de: "Zentral"},
  ]},
  programming_required: {en: "Programming prerequisite", de: "Programmierkenntnisse als Voraussetzung", options: [
    {value: "required", en: "Required", de: "Erforderlich"},
    {value: "recommended", en: "Recommended", de: "Empfohlen"},
  ]},
  work_location_mode: {en: "Work location", de: "Arbeitsort", options: [
    {value: "on_site", en: "On site", de: "Vor Ort"},
    {value: "hybrid", en: "Hybrid", de: "Hybrid"}, {value: "remote", en: "Remote", de: "Remote"},
  ]},
  working_language: {en: "Working language includes", de: "Arbeitssprache umfasst", options: [
    {value: "en", en: "English", de: "Englisch"}, {value: "de", en: "German", de: "Deutsch"},
    {value: "other", en: "Other stated language", de: "Andere angegebene Sprache"},
  ]},
};
const profileFieldOrder: ProfileField[] = ["degree_level", "work_modes", "programming_performed", "programming_required", "work_location_mode", "working_language"];

function organizationNames(project: Project): {name: string; role: "academic_unit" | "partner"}[] {
  const units = project.academic_units?.length
    ? project.academic_units.map((item) => item.canonical_name || item.name)
    : project.chair ? [project.chair] : [];
  const partners = (project.project_partners || []).map((item) => item.canonical_name || item.name);
  return [...units.map((name) => ({name, role: "academic_unit" as const})),
          ...partners.map((name) => ({name, role: "partner" as const}))];
}

function profileFieldValues(project: Project, field: ProfileField): string[] | null {
  const profile = project.filter_values;
  if (!profile) return null;
  const value = profile[field];
  if (Array.isArray(value)) return value;
  if (value === null || value === "unknown" || value === "not_stated") return null;
  return [value];
}

function matchesProfileFacet(project: Project, field: ProfileField, selected: Set<string>, includeUnknown: boolean): boolean {
  if (selected.size === 0 && !includeUnknown) return true;
  const values = profileFieldValues(project, field);
  if (values === null) return includeUnknown;
  if (field === "degree_level" && values.includes("any") && (selected.has("bachelor") || selected.has("master"))) return true;
  return values.some((value) => selected.has(value));
}

export default function CatalogClient({lang, copy, initialProjects, lastUpdatedAt, chairs, publishedProfileFilters, pinnedProjectCodes, initialSavedOnly = false}: {lang: "en" | "de"; copy: Copy; initialProjects: Project[]; lastUpdatedAt?: string; chairs: Chair[]; publishedProfileFilters: string[]; pinnedProjectCodes: string[]; initialSavedOnly?: boolean}) {
  const [query, setQuery] = useState("");
  const [selectedAgeBands, setSelectedAgeBands] = useState<Set<AgeBand>>(() => new Set());
  const [selectedTypes, setSelectedTypes] = useState<Set<OpportunityType>>(() => new Set(["project_study", "idp", "other"]));
  const [selectedProfileValues, setSelectedProfileValues] = useState<Record<ProfileField, Set<string>>>(() => Object.fromEntries(profileFieldOrder.map((field) => [field, new Set<string>()])) as Record<ProfileField, Set<string>>);
  const [includeUnknown, setIncludeUnknown] = useState<Set<ProfileField>>(() => new Set());
  const [displayCount, setDisplayCount] = useState("20");
  const [currentPage, setCurrentPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [savedOnly, setSavedOnly] = useState(initialSavedOnly);
  const {bookmarks, loaded: bookmarksLoaded, error: bookmarkError, toggle: toggleBookmark} = useBookmarks();
  const savedSlugs = useMemo(() => new Set(bookmarks), [bookmarks]);
  const publishedFields = useMemo(() => profileFieldOrder.filter((field) => publishedProfileFilters.includes(field)), [publishedProfileFilters]);
  const pinnedOrder = useMemo(() => new Map<string, number>(pinnedProjectCodes.map((code, index) => [code.toLowerCase(), index] as const)), [pinnedProjectCodes]);
  const displayedProjects = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const filtered = initialProjects.filter((project) => {
      const ageTimestamp = project.published_at ? Date.parse(`${project.published_at}T00:00:00Z`) : Date.parse(project.first_seen_at);
      const daysOld = Math.floor((Date.now() - ageTimestamp) / 86_400_000);
      const ageBand = daysOld < 3 ? "lt3" : daysOld < 30 ? "lt30" : daysOld < 60 ? "lt60" : daysOld < 180 ? "lt180" : "gt180";
      const matchesAge = selectedAgeBands.size === 0 || selectedAgeBands.has(ageBand);
      const matchesType = selectedTypes.has(project.opportunity_type);
      const matchesProfile = publishedFields.every((field) => matchesProfileFacet(project, field, selectedProfileValues[field], includeUnknown.has(field)));
      const text = `${project.reference_code} ${project.title} ${project.summary || ""} ${organizationNames(project).map(({name}) => name).join(" ")} ${project.source_name || ""} ${project.department}`.toLocaleLowerCase();
      return matchesAge && matchesType && matchesProfile && (!savedOnly || savedSlugs.has(project.slug)) && (!needle || text.includes(needle));
    });
    return filtered.sort((a, b) => {
      const aPin = pinnedOrder.get(a.reference_code.toLowerCase());
      const bPin = pinnedOrder.get(b.reference_code.toLowerCase());
      if (aPin !== undefined || bPin !== undefined) {
        if (aPin === undefined) return 1;
        if (bPin === undefined) return -1;
        if (aPin !== bPin) return aPin - bPin;
      }
      const aDate = a.published_at ? Date.parse(`${a.published_at}T00:00:00Z`) : Date.parse(a.first_seen_at);
      const bDate = b.published_at ? Date.parse(`${b.published_at}T00:00:00Z`) : Date.parse(b.first_seen_at);
      return bDate - aDate || Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at);
    });
  }, [initialProjects, query, selectedAgeBands, selectedTypes, selectedProfileValues, includeUnknown, publishedFields, savedOnly, savedSlugs, pinnedOrder]);
  const pageSize = displayCount === "all" ? displayedProjects.length || 1 : Number(displayCount);
  const pageCount = Math.max(1, Math.ceil(displayedProjects.length / pageSize));
  const activePage = Math.min(currentPage, pageCount);
  const visibleProjects = displayCount === "all" ? displayedProjects : displayedProjects.slice((activePage - 1) * pageSize, activePage * pageSize);
  const date = (value: string) => new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}).format(new Date(value.includes("T") ? value : `${value}T00:00:00Z`));
  const lastUpdated = lastUpdatedAt ? new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", {dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin"}).format(new Date(lastUpdatedAt)) : null;

  function toggleAgeBand(band: AgeBand, checked: boolean) {
    setCurrentPage(1);
    setSelectedAgeBands((current) => {
      const next = new Set(current);
      const index = ageBands.indexOf(band);
      if (band === "gt180") {
        if (checked) next.add(band); else next.delete(band);
      } else if (checked) {
        for (const candidate of ageBands.slice(0, index + 1)) next.add(candidate);
      } else {
        for (const candidate of ageBands.slice(0, index + 1)) next.delete(candidate);
      }
      return next;
    });
  }

  function toggleType(type: OpportunityType, checked: boolean) {
    setCurrentPage(1);
    setSelectedTypes((current) => {
      const next = new Set(current);
      if (checked) next.add(type); else next.delete(type);
      return next;
    });
  }

  function toggleProfileValue(field: ProfileField, value: string, checked: boolean) {
    setCurrentPage(1);
    setSelectedProfileValues((current) => {
      const next = new Set(current[field]);
      if (checked) next.add(value); else next.delete(value);
      return {...current, [field]: next};
    });
  }

  function toggleProfileUnknown(field: ProfileField, checked: boolean) {
    setCurrentPage(1);
    setIncludeUnknown((current) => {
      const next = new Set(current);
      if (checked) next.add(field); else next.delete(field);
      return next;
    });
  }

  function resetFilters() {
    setCurrentPage(1);
    setQuery("");
    setSelectedAgeBands(new Set());
    setSelectedTypes(new Set(["project_study", "idp", "other"]));
    setSelectedProfileValues(Object.fromEntries(profileFieldOrder.map((field) => [field, new Set<string>()])) as Record<ProfileField, Set<string>>);
    setIncludeUnknown(new Set());
    setSavedOnly(false);
  }

  const filtersActive = query !== "" || selectedAgeBands.size > 0 || selectedTypes.size !== 3 || savedOnly || publishedFields.some((field) => selectedProfileValues[field].size > 0 || includeUnknown.has(field));
  const ageLabels: Record<AgeBand, string> = {lt3: copy.under3, lt30: copy.under30, lt60: copy.under60, lt180: copy.under180, gt180: copy.over180};

  function renderProfileFacet(field: ProfileField) {
    const definition = profileFacets[field];
    const label = lang === "de" ? definition.de : definition.en;
    const unknownLabel = field === "programming_performed" || field === "work_location_mode"
      ? (lang === "de" ? "Unbekannt einbeziehen" : "Include unknown")
      : (lang === "de" ? "Nicht angegeben einbeziehen" : "Include not specified");
    const count = (value: string | null) => initialProjects.filter((project) => {
      if (value === null) return profileFieldValues(project, field) === null;
      return matchesProfileFacet(project, field, new Set([value]), false);
    }).length;
    return <details className="department-filter profile-filter" key={field}><summary>{label}</summary><fieldset><legend className="visually-hidden">{label}</legend><div className="chips">
      {definition.options.map((option) => <label className="chip" key={option.value}>
        <input type="checkbox" checked={selectedProfileValues[field].has(option.value)} onChange={(event) => toggleProfileValue(field, option.value, event.target.checked)}/>
        <span>{lang === "de" ? option.de : option.en} ({count(option.value)})</span>
      </label>)}
      <label className="chip"><input type="checkbox" checked={includeUnknown.has(field)} onChange={(event) => toggleProfileUnknown(field, event.target.checked)}/><span>{unknownLabel} ({count(null)})</span></label>
    </div></fieldset></details>;
  }

  function renderProjectContent(project: Project, includeTitle = true) {
    return <>
      <span className={styles.referenceCode}>{project.reference_code}</span>
      <p className="meta">{organizationNames(project).length ? organizationNames(project).map(({name}) => name).join(" / ") : (lang === "de" ? "Organisation nicht angegeben" : "Organization not specified")}{project.source_name === "Informatics IDP Hub" && ` · ${lang === "de" ? "Quelle" : "Source"}: ${project.source_name}`}</p>
      {includeTitle && <h2>{project.title}</h2>}
      <p className="card-summary">{project.search_summary_en || project.summary || copy.unknown}</p>
      <div className="tags"><span className="tag tag-type">{project.opportunity_type === "idp" ? "IDP" : project.opportunity_type === "other" ? (lang === "de" ? "Sonstige" : "Others") : "Project Study"}</span>{project.language && <span className="tag">{project.language}</span>}{project.topics.map((topic) => <span className="tag" key={topic}>{topic.replaceAll("_", " / ")}</span>)}<span className="tag tag-date">{project.published_at ? `${copy.published} ${date(project.published_at)}` : `${copy.added} ${date(project.first_seen_at)}`}</span></div>
      <p className="links">
        <BookmarkButton slug={project.slug} lang={lang} saved={savedSlugs.has(project.slug)} onToggle={toggleBookmark} disabled={!bookmarksLoaded}/>
        {(project.has_profile || project.has_description) && <Link className="source source-primary" href={`/${lang}/projects/${encodeURIComponent(project.slug)}`}>{copy.profile}<ArrowRightIcon/></Link>}
        <a className="source" href={project.source_url} target="_blank" rel="noopener noreferrer">{project.chair ? copy.source : (lang === "de" ? "Originale Angebotsseite" : "Original listing page")}<ExternalIcon size={14}/></a>
        {project.artifact_url && <a className="source" href={project.artifact_url} target="_blank" rel="noopener noreferrer">{copy.artifact}<ExternalIcon size={14}/></a>}
      </p>
    </>;
  }

  return <>
    <SiteHeader lang={lang} brand={copy.brand} enHref={savedOnly ? "/en?saved=1" : "/en"} deHref={savedOnly ? "/de?saved=1" : "/de"} savedActive={savedOnly}/>
    <main>
      <section className="hero"><div className="shell">
        {lastUpdated && <p className="pill"><span className="pill-dot" aria-hidden="true"/>{copy.lastUpdated}: <time dateTime={lastUpdatedAt}>{lastUpdated}</time></p>}
        <h1>{copy.titleBefore}{copy.titleHighlight && <span className="highlight">{copy.titleHighlight}</span>}{copy.titleAfter}</h1>
        <p className="lede">{copy.lede}</p>
        <div className="hero-search"><SearchIcon size={20}/><input className="search" value={query} onChange={(event) => { setQuery(event.target.value); setCurrentPage(1); }} type="search" placeholder={copy.search} aria-label={copy.search}/></div>
        <ul className="trust">
          <li><RefreshIcon/>{copy.trustDaily}</li>
          <li><LinkIcon/>{copy.trustSources}</li>
          {chairs.length > 0 && <li><FileIcon/>{chairs.length} {copy.trustChairs}</li>}
        </ul>
        <p className={`notice${lang === "de" ? " notice-de" : ""}`}><InfoIcon/><span><Disclaimer lang={lang}/></span></p>
      </div></section>
      <div className="shell catalog">
        <aside className="filters">
          <button type="button" className="filters-toggle" aria-expanded={filtersOpen} aria-controls="filters-body" onClick={() => setFiltersOpen((open) => !open)}><FilterIcon/>{copy.filterToggle}</button>
          <div id="filters-body" className={`filters-body${filtersOpen ? " open" : ""}`}>
            <fieldset><legend>{copy.type}</legend><div className="chips">
              <label className="chip"><input type="checkbox" checked={selectedTypes.has("project_study")} onChange={(event) => toggleType("project_study", event.target.checked)}/><span>Project Study</span></label>
              <label className="chip"><input type="checkbox" checked={selectedTypes.has("idp")} onChange={(event) => toggleType("idp", event.target.checked)}/><span>IDP</span></label>
              <label className="chip"><input type="checkbox" checked={selectedTypes.has("other")} onChange={(event) => toggleType("other", event.target.checked)}/><span>{lang === "de" ? "Sonstige" : "Others"}</span></label>
            </div></fieldset>
            <fieldset><legend>{copy.age}</legend><div className="chips">{ageBands.map((band) => <label className="chip" key={band}><input type="checkbox" checked={selectedAgeBands.has(band)} onChange={(event) => toggleAgeBand(band, event.target.checked)}/><span>{ageLabels[band]}</span></label>)}</div></fieldset>
            {publishedFields.map(renderProfileFacet)}
            {filtersActive && <button type="button" className="reset" onClick={resetFilters}>{copy.reset}</button>}
          </div>
        </aside>
        <section aria-live="polite">
          {bookmarkError && <p role="alert" className={styles.bookmarkError}>{copy.bookmarkError}</p>}
          <div className="results-head">
            <p className="results-count"><strong>{displayedProjects.length}</strong> {displayedProjects.length === 1 ? copy.foundOne : copy.foundMany}</p>
            <div className="controls">
              <label>{copy.display} <select value={displayCount} onChange={(event) => { setDisplayCount(event.target.value); setCurrentPage(1); }} aria-label={copy.display}><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option><option value="all">{copy.all}</option></select></label>
            </div>
          </div>
          {visibleProjects.length === 0 && <div className="empty"><h2>{copy.noResults}</h2><p>{savedOnly && bookmarks.length === 0 ? copy.noSaved : copy.noResultsHint}</p>{filtersActive && <button type="button" onClick={resetFilters}>{copy.reset}</button>}</div>}
          {visibleProjects.map((project) => {
            const isPinned = pinnedOrder.has(project.reference_code.toLowerCase());
            return <article className={`card ${styles.cardWithReference} ${isPinned ? styles.pinnedCard : ""}`} key={project.slug}>
              {isPinned
                ? <details className={styles.pinnedDetails}>
                    <summary className={styles.pinnedSummary}>{project.title}</summary>
                    <div className={styles.pinnedContent}>{renderProjectContent(project, false)}</div>
                  </details>
                : renderProjectContent(project)}
            </article>;
          })}
          {displayCount !== "all" && pageCount > 1 && <nav className="pagination" aria-label={copy.pagination}><button type="button" onClick={() => setCurrentPage(activePage - 1)} disabled={activePage === 1}>{copy.previous}</button>{Array.from({length: pageCount}, (_, index) => index + 1).map((page) => <button type="button" key={page} onClick={() => setCurrentPage(page)} aria-current={page === activePage ? "page" : undefined}>{page}</button>)}<button type="button" onClick={() => setCurrentPage(activePage + 1)} disabled={activePage === pageCount}>{copy.next}</button></nav>}
        </section>
      </div>
    </main>
    <SiteFooter lang={lang}/>
  </>;
}
