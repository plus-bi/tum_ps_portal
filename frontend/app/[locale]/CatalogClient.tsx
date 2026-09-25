"use client";

import {useMemo, useState} from "react";
import Link from "next/link";
import AuthControls from "./AuthControls";
import styles from "./CatalogClient.module.css";

export type Project = {slug: string; reference_code: string; title: string; summary?: string; department: string; chair: string; opportunity_type: "project_study" | "idp"; language?: string; topics: string[]; freshness: string; source_url: string; artifact_url?: string; has_profile: boolean; published_at?: string; first_seen_at: string};
export type Department = {slug: string; name: string};
export type Chair = {slug: string; name: string; department: string; source_state: string};

type AgeBand = "lt3" | "lt30" | "lt60" | "lt180" | "gt180";
type OpportunityType = Project["opportunity_type"];
type SortBy = "publication_date" | "recently_added";
type Copy = {brand: string; title: string; lede: string; notice: string; search: string; filters: string; lastUpdated: string; age: string; under3: string; under30: string; under60: string; under180: string; over180: string; type: string; sort: string; publicationDate: string; recentlyAdded: string; display: string; all: string; previous: string; next: string; foundOne: string; foundMany: string; profile: string; source: string; artifact: string; unknown: string; published: string; added: string};
const ageBands: AgeBand[] = ["lt3", "lt30", "lt60", "lt180", "gt180"];

export default function CatalogClient({lang, copy, initialProjects, lastUpdatedAt, departments, chairs}: {lang: "en" | "de"; copy: Copy; initialProjects: Project[]; lastUpdatedAt?: string; departments: Department[]; chairs: Chair[]}) {
  const [selectedChairs, setSelectedChairs] = useState<Set<string>>(() => new Set());
  const [query, setQuery] = useState("");
  const [selectedAgeBands, setSelectedAgeBands] = useState<Set<AgeBand>>(() => new Set());
  const [selectedTypes, setSelectedTypes] = useState<Set<OpportunityType>>(() => new Set());
  const [sortBy, setSortBy] = useState<SortBy>("publication_date");
  const [displayCount, setDisplayCount] = useState("20");
  const [currentPage, setCurrentPage] = useState(1);
  const chairsByDepartment = useMemo(() => new Map(departments.map((department) => [department.name, chairs.filter((chair) => chair.department === department.name).sort((a, b) => a.name.localeCompare(b.name))])), [chairs, departments]);
  const displayedProjects = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const filtered = initialProjects.filter((project) => {
      const matchesChair = selectedChairs.size === 0 || selectedChairs.has(project.chair);
      const ageTimestamp = project.published_at ? Date.parse(`${project.published_at}T00:00:00Z`) : Date.parse(project.first_seen_at);
      const daysOld = Math.floor((Date.now() - ageTimestamp) / 86_400_000);
      const ageBand = daysOld < 3 ? "lt3" : daysOld < 30 ? "lt30" : daysOld < 60 ? "lt60" : daysOld < 180 ? "lt180" : "gt180";
      const matchesAge = selectedAgeBands.size === 0 || selectedAgeBands.has(ageBand);
      const matchesType = selectedTypes.size === 0 || selectedTypes.has(project.opportunity_type);
      const text = `${project.reference_code} ${project.title} ${project.summary || ""} ${project.chair} ${project.department}`.toLocaleLowerCase();
      return matchesChair && matchesAge && matchesType && (!needle || text.includes(needle));
    });
    return filtered.sort((a, b) => {
      if (sortBy === "recently_added") {
        return Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at);
      }
      if (!a.published_at && !b.published_at) return Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at);
      if (!a.published_at) return 1;
      if (!b.published_at) return -1;
      return Date.parse(`${b.published_at}T00:00:00Z`) - Date.parse(`${a.published_at}T00:00:00Z`);
    });
  }, [initialProjects, query, selectedAgeBands, selectedChairs, selectedTypes, sortBy]);
  const pageSize = displayCount === "all" ? displayedProjects.length || 1 : Number(displayCount);
  const pageCount = Math.max(1, Math.ceil(displayedProjects.length / pageSize));
  const activePage = Math.min(currentPage, pageCount);
  const visibleProjects = displayCount === "all" ? displayedProjects : displayedProjects.slice((activePage - 1) * pageSize, activePage * pageSize);
  const date = (value: string) => new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}).format(new Date(value.includes("T") ? value : `${value}T00:00:00Z`));
  const lastUpdated = lastUpdatedAt ? new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", {dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin"}).format(new Date(lastUpdatedAt)) : null;

  function toggleChair(name: string, checked: boolean) {
    setCurrentPage(1);
    setSelectedChairs((current) => {
      const next = new Set(current);
      if (checked) next.add(name); else next.delete(name);
      return next;
    });
  }

  function toggleDepartment(departmentChairs: Chair[], checked: boolean) {
    setCurrentPage(1);
    setSelectedChairs((current) => {
      const next = new Set(current);
      for (const chair of departmentChairs) {
        if (checked) next.add(chair.name); else next.delete(chair.name);
      }
      return next;
    });
  }

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

  const ageLabels: Record<AgeBand, string> = {lt3: copy.under3, lt30: copy.under30, lt60: copy.under60, lt180: copy.under180, gt180: copy.over180};

  return <>
    <header className="top"><div className="shell"><a className="brand" href={`/${lang}`}>{copy.brand}</a><div className="top-actions"><nav className="lang" aria-label="Language"><a href="/en" lang="en">EN</a><a href="/de" lang="de">DE</a></nav><AuthControls/></div></div></header>
    <main><section className="hero"><div className="shell"><h1>{copy.title}</h1><p className="lede">{copy.lede}</p><p className="notice">{copy.notice}</p></div></section><div className="shell catalog">
      <aside className="filters"><fieldset><legend>{copy.filters}</legend>{lastUpdated && <p className="last-updated">{copy.lastUpdated}: <time dateTime={lastUpdatedAt}>{lastUpdated}</time></p>}{departments.map((department) => {
        const departmentChairs = chairsByDepartment.get(department.name) || [];
        const selectedCount = departmentChairs.filter((chair) => selectedChairs.has(chair.name)).length;
        const allSelected = departmentChairs.length > 0 && selectedCount === departmentChairs.length;
        const partlySelected = selectedCount > 0 && !allSelected;
        return <details className="department-filter" key={department.slug}><summary><label className="department-label" onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={allSelected} ref={(input) => { if (input) input.indeterminate = partlySelected; }} onChange={(event) => toggleDepartment(departmentChairs, event.target.checked)}/><span>{department.name}</span></label></summary><div className="chair-filter-list">{departmentChairs.map((chair) => <label className="chair-label" key={chair.slug}><input type="checkbox" checked={selectedChairs.has(chair.name)} onChange={(event) => toggleChair(chair.name, event.target.checked)}/><span>{chair.name}</span></label>)}</div></details>;
      })}</fieldset></aside>
      <section aria-live="polite"><div className="results-head"><input className="search" value={query} onChange={(event) => { setQuery(event.target.value); setCurrentPage(1); }} type="search" placeholder={copy.search} aria-label={copy.search}/><label>{copy.sort} <select value={sortBy} onChange={(event) => { setSortBy(event.target.value as SortBy); setCurrentPage(1); }} aria-label={copy.sort}><option value="publication_date">{copy.publicationDate}</option><option value="recently_added">{copy.recentlyAdded}</option></select></label><label>{copy.display} <select value={displayCount} onChange={(event) => { setDisplayCount(event.target.value); setCurrentPage(1); }} aria-label={copy.display}><option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option><option value="all">{copy.all}</option></select></label></div><div className="filter-row"><fieldset><legend>{copy.age}</legend>{ageBands.map((band) => <label key={band}><input type="checkbox" checked={selectedAgeBands.has(band)} onChange={(event) => toggleAgeBand(band, event.target.checked)}/>{ageLabels[band]}</label>)}</fieldset><fieldset><legend>{copy.type}</legend><label><input type="checkbox" checked={selectedTypes.has("project_study")} onChange={(event) => toggleType("project_study", event.target.checked)}/>Project Study</label><label><input type="checkbox" checked={selectedTypes.has("idp")} onChange={(event) => toggleType("idp", event.target.checked)}/>IDP</label></fieldset></div><p><strong>{displayedProjects.length}</strong> {displayedProjects.length === 1 ? copy.foundOne : copy.foundMany}</p>{visibleProjects.map((project) => <article className={`card ${styles.cardWithReference}`} key={project.slug}><span className={styles.referenceCode}>{project.reference_code}</span><p className="meta">{project.department} · {project.chair}</p><h2>{project.title}</h2><p>{project.summary || copy.unknown}</p><div className="tags"><span className="tag">{project.opportunity_type === "idp" ? "IDP" : "Project Study"}</span>{project.language && <span className="tag">{project.language}</span>}{project.topics.map((topic) => <span className="tag" key={topic}>{topic.replaceAll("_", " / ")}</span>)}<span className="tag">{project.published_at ? `${copy.published} ${date(project.published_at)}` : `${copy.added} ${date(project.first_seen_at)}`}</span></div><p className="links">{project.has_profile && <Link className="source" href={`/${lang}/projects/${encodeURIComponent(project.slug)}`}>{copy.profile} →</Link>}<a className="source" href={project.source_url} target="_blank" rel="noopener noreferrer">{copy.source} ↗</a>{project.artifact_url && <a className="source" href={project.artifact_url} target="_blank" rel="noopener noreferrer">{copy.artifact} ↗</a>}</p></article>)}{displayCount !== "all" && pageCount > 1 && <nav className="pagination" aria-label="Pagination"><button type="button" onClick={() => setCurrentPage(activePage - 1)} disabled={activePage === 1}>{copy.previous}</button>{Array.from({length: pageCount}, (_, index) => index + 1).map((page) => <button type="button" key={page} onClick={() => setCurrentPage(page)} aria-current={page === activePage ? "page" : undefined}>{page}</button>)}<button type="button" onClick={() => setCurrentPage(activePage + 1)} disabled={activePage === pageCount}>{copy.next}</button></nav>}</section>
    </div></main>
    <footer className="footer"><div className="shell">{copy.notice}</div></footer>
  </>;
}
