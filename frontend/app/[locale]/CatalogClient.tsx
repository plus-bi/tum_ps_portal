"use client";

import {useMemo, useState} from "react";
import AuthControls from "./AuthControls";

export type Project = {slug: string; title: string; summary?: string; department: string; chair: string; language?: string; topics: string[]; freshness: string; source_url: string; artifact_url?: string; published_at?: string};
export type Department = {slug: string; name: string};
export type Chair = {slug: string; name: string; department: string; source_state: string};

type Copy = {brand: string; title: string; lede: string; notice: string; search: string; filters: string; foundOne: string; foundMany: string; source: string; artifact: string; unknown: string; published: string; current: string; old: string; undated: string};

export default function CatalogClient({lang, copy, initialProjects, departments, chairs}: {lang: "en" | "de"; copy: Copy; initialProjects: Project[]; departments: Department[]; chairs: Chair[]}) {
  const [selectedChairs, setSelectedChairs] = useState<Set<string>>(() => new Set());
  const [query, setQuery] = useState("");
  const chairsByDepartment = useMemo(() => new Map(departments.map((department) => [department.name, chairs.filter((chair) => chair.department === department.name).sort((a, b) => a.name.localeCompare(b.name))])), [chairs, departments]);
  const displayedProjects = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return initialProjects.filter((project) => {
      const matchesChair = selectedChairs.size === 0 || selectedChairs.has(project.chair);
      const text = `${project.title} ${project.summary || ""} ${project.chair} ${project.department}`.toLocaleLowerCase();
      return matchesChair && (!needle || text.includes(needle));
    });
  }, [initialProjects, query, selectedChairs]);
  const date = (value: string) => new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}).format(new Date(`${value}T00:00:00Z`));

  function toggleChair(name: string, checked: boolean) {
    setSelectedChairs((current) => {
      const next = new Set(current);
      if (checked) next.add(name); else next.delete(name);
      return next;
    });
  }

  function toggleDepartment(departmentChairs: Chair[], checked: boolean) {
    setSelectedChairs((current) => {
      const next = new Set(current);
      for (const chair of departmentChairs) {
        if (checked) next.add(chair.name); else next.delete(chair.name);
      }
      return next;
    });
  }

  return <>
    <header className="top"><div className="shell"><a className="brand" href={`/${lang}`}>{copy.brand}</a><div className="top-actions"><nav className="lang" aria-label="Language"><a href="/en" lang="en">EN</a><a href="/de" lang="de">DE</a></nav><AuthControls/></div></div></header>
    <main><section className="hero"><div className="shell"><h1>{copy.title}</h1><p className="lede">{copy.lede}</p><p className="notice">{copy.notice}</p></div></section><div className="shell catalog">
      <aside className="filters"><fieldset><legend>{copy.filters}</legend>{departments.map((department) => {
        const departmentChairs = chairsByDepartment.get(department.name) || [];
        const selectedCount = departmentChairs.filter((chair) => selectedChairs.has(chair.name)).length;
        const allSelected = departmentChairs.length > 0 && selectedCount === departmentChairs.length;
        const partlySelected = selectedCount > 0 && !allSelected;
        return <details className="department-filter" key={department.slug}><summary><label className="department-label" onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={allSelected} ref={(input) => { if (input) input.indeterminate = partlySelected; }} onChange={(event) => toggleDepartment(departmentChairs, event.target.checked)}/><span>{department.name}</span></label></summary><div className="chair-filter-list">{departmentChairs.map((chair) => <label className="chair-label" key={chair.slug}><input type="checkbox" checked={selectedChairs.has(chair.name)} onChange={(event) => toggleChair(chair.name, event.target.checked)}/><span>{chair.name}</span></label>)}</div></details>;
      })}</fieldset></aside>
      <section aria-live="polite"><div className="results-head"><input className="search" value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={copy.search} aria-label={copy.search}/></div><p><strong>{displayedProjects.length}</strong> {displayedProjects.length === 1 ? copy.foundOne : copy.foundMany}</p>{displayedProjects.map((project) => <article className="card" key={project.slug}><p className="meta">{project.department} · {project.chair}</p><h2>{project.title}</h2><p>{project.summary || copy.unknown}</p><div className="tags">{project.language && <span className="tag">{project.language}</span>}{project.topics.map((topic) => <span className="tag" key={topic}>{topic.replaceAll("_", " / ")}</span>)}<span className="tag">{project.published_at ? `${copy.published} ${date(project.published_at)} · ${copy[project.freshness as "current" | "old"]}` : copy.undated}</span></div><p className="links"><a className="source" href={project.source_url} target="_blank" rel="noopener noreferrer">{copy.source} ↗</a>{project.artifact_url && <a className="source" href={project.artifact_url} target="_blank" rel="noopener noreferrer">{copy.artifact} ↗</a>}</p></article>)}</section>
    </div></main>
    <footer className="footer"><div className="shell">{copy.notice}</div></footer>
  </>;
}
