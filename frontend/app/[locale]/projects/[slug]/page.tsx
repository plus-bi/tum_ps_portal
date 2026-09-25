import Link from "next/link";
import {notFound} from "next/navigation";
import AuthControls from "../../AuthControls";
import type {Project} from "../../CatalogClient";
import styles from "./ProfileDetail.module.css";

type Evidence = {page: number; excerpt: string};
type TextField = {stated: boolean; value: string | null; evidence: Evidence[]};
type DateField = TextField & {normalized: string | null};
type SourcedValue<T> = {value: T; evidence: Evidence[]};
type ListField<T> = {stated: boolean; items: SourcedValue<T>[]};
type Assessment = {level: string; evidence: Evidence[]};
type Contact = {name: string | null; email: string | null};
type EvidenceIssue = {offer_index: number | null; field: string; item_index: number | null; page: number; reason: string};

type Offer = {
  source_pages: number[];
  title: TextField;
  provider_name: TextField;
  project_types: ListField<string>;
  degree_level: ListField<string>;
  project_goal: TextField;
  subjects: ListField<string>;
  application_areas: ListField<string>;
  methods_tools: ListField<string>;
  activities: ListField<string>;
  work_modes: ListField<string>;
  programming_performed: Assessment;
  programming_required: Assessment;
  deliverables: ListField<string>;
  prerequisites_required: ListField<string>;
  prerequisites_recommended: ListField<string>;
  eligible_study_fields: ListField<string>;
  learning_opportunities: ListField<string>;
  support_offered: ListField<string>;
  team_size: TextField;
  duration: TextField;
  start_date: DateField;
  application_deadline: DateField;
  location: TextField;
  work_location_mode: Assessment;
  working_language: ListField<string>;
  contacts: ListField<Contact>;
  application_instructions: TextField;
  external_url: TextField;
  search_summary_en: string;
};

type ProfileDetail = {
  project: Project;
  document: {document_language: string; document_kind: string; offers: Offer[]};
  coverage: {status: string; blank_markdown_pages: number[]; page_count: number};
  evidence_issues: EvidenceIssue[];
  review_flags: string[];
  extracted_at: string;
};

const translations = {
  en: {
    brand: "TUM Project Opportunities", back: "Back to projects", title: "Project details",
    intro: "Automatically extracted from the linked project document. Check the original PDF before relying on a detail.",
    notice: "This is not an official TUM website and is not endorsed by or associated with TUM. It is provided as a courtesy service by a TUM alumnus.",
    source: "Chair listing page", document: "Original PDF", page: "Page", pages: "Pages", evidence: "Source excerpt",
    unknown: "Not stated in the PDF", summary: "English summary", multiple: "This document contains several project offers.",
    noOffers: "No individual project offer was identified in this document.", incomplete: "Some PDF pages had no readable text:",
    issue: "This citation needs review.", issues: "Some source excerpts could not be verified against the extracted PDF text.",
    overview: "Overview", work: "Topics and work", requirements: "Requirements", practical: "Practical details",
    support: "Learning and support", application: "Application and contacts", normalized: "Normalized date",
    offer: "Offer", documentLanguage: "Document language", extracted: "Extracted", provider: "Organization", projectTypes: "Project formats",
    degree: "Degree levels", goal: "Project goal", subjects: "Subjects", areas: "Application areas",
    methods: "Methods and tools", activities: "Activities", workModes: "Kinds of work", deliverables: "Expected outputs",
    programmingWork: "Programming in the project", programmingSkill: "Programming prerequisite",
    required: "Required skills", recommended: "Recommended skills", studyFields: "Eligible study fields",
    learning: "Learning opportunities", supportOffered: "Support offered", teamSize: "Team size", duration: "Duration",
    start: "Start", deadline: "Application deadline", location: "Work location", locationMode: "Location mode",
    language: "Working language", contacts: "Contacts", instructions: "How to apply", external: "Further information",
  },
  de: {
    brand: "TUM-Projektportal", back: "Zurück zu den Projekten", title: "Projektdetails",
    intro: "Automatisch aus dem verlinkten Projektdokument extrahiert. Prüfe wichtige Angaben im Original-PDF.",
    notice: "Dies ist keine offizielle TUM-Website und wird weder von der TUM unterstützt noch mit ihr in Verbindung gebracht. Sie wird als kostenlose Serviceleistung von einem TUM-Alumnus bereitgestellt.",
    source: "Seite des Lehrstuhls", document: "Original-PDF", page: "Seite", pages: "Seiten", evidence: "Textstelle",
    unknown: "Im PDF nicht angegeben", summary: "Englische Zusammenfassung", multiple: "Dieses Dokument enthält mehrere Projektangebote.",
    noOffers: "In diesem Dokument wurde kein einzelnes Projektangebot erkannt.", incomplete: "Einige PDF-Seiten enthielten keinen lesbaren Text:",
    issue: "Diese Textstelle muss überprüft werden.", issues: "Einige Textstellen konnten im extrahierten PDF-Text nicht überprüft werden.",
    overview: "Überblick", work: "Themen und Aufgaben", requirements: "Voraussetzungen", practical: "Rahmenbedingungen",
    support: "Lernen und Betreuung", application: "Bewerbung und Kontakt", normalized: "Normalisiertes Datum",
    offer: "Angebot", documentLanguage: "Dokumentsprache", extracted: "Extrahiert", provider: "Organisation", projectTypes: "Projektformate",
    degree: "Studienabschlüsse", goal: "Projektziel", subjects: "Themen", areas: "Anwendungsbereiche",
    methods: "Methoden und Werkzeuge", activities: "Aufgaben", workModes: "Art der Arbeit", deliverables: "Erwartete Ergebnisse",
    programmingWork: "Programmierung im Projekt", programmingSkill: "Programmierkenntnisse als Voraussetzung",
    required: "Erforderliche Kenntnisse", recommended: "Wünschenswerte Kenntnisse", studyFields: "Geeignete Studienrichtungen",
    learning: "Lernmöglichkeiten", supportOffered: "Angebotene Betreuung", teamSize: "Teamgröße", duration: "Dauer",
    start: "Beginn", deadline: "Bewerbungsfrist", location: "Arbeitsort", locationMode: "Arbeitsmodus",
    language: "Arbeitssprache", contacts: "Kontaktpersonen", instructions: "Bewerbung", external: "Weitere Informationen",
  },
};
type Copy = typeof translations.en;

const enumLabels: Record<string, {en: string; de: string}> = {
  de: {en: "German", de: "Deutsch"}, en: {en: "English", de: "Englisch"},
  mixed: {en: "Mixed", de: "Gemischt"}, other: {en: "Other", de: "Andere"},
  unknown: {en: "Unknown", de: "Unbekannt"},
  project_study: {en: "Project Study", de: "Projektstudium"}, idp: {en: "IDP", de: "IDP"},
  bachelor_thesis: {en: "Bachelor's thesis", de: "Bachelorarbeit"},
  master_thesis: {en: "Master's thesis", de: "Masterarbeit"},
  semester_thesis: {en: "Semester thesis", de: "Semesterarbeit"},
  bachelor: {en: "Bachelor", de: "Bachelor"}, master: {en: "Master", de: "Master"},
  any: {en: "Any degree level", de: "Alle Studienabschlüsse"},
  software_development: {en: "Software development", de: "Softwareentwicklung"},
  data_analysis_ml: {en: "Data analysis and ML", de: "Datenanalyse und ML"},
  modeling_simulation: {en: "Modeling and simulation", de: "Modellierung und Simulation"},
  hardware_lab: {en: "Hardware and lab work", de: "Hardware und Laborarbeit"},
  literature_research: {en: "Literature research", de: "Literaturrecherche"},
  empirical_user_research: {en: "User research", de: "Nutzerforschung"},
  business_strategy: {en: "Business strategy", de: "Geschäftsstrategie"},
  process_optimization: {en: "Process optimization", de: "Prozessoptimierung"},
  marketing_content: {en: "Marketing and content", de: "Marketing und Inhalte"},
  design_ux: {en: "Design and UX", de: "Design und UX"},
  none: {en: "No programming", de: "Keine Programmierung"},
  some: {en: "Some", de: "Teilweise"}, central: {en: "Central", de: "Zentral"},
  required: {en: "Required", de: "Erforderlich"}, recommended: {en: "Recommended", de: "Wünschenswert"},
  on_site: {en: "On site", de: "Vor Ort"}, hybrid: {en: "Hybrid", de: "Hybrid"},
  remote: {en: "Remote", de: "Remote"},
};

function label(value: string, lang: "en" | "de"): string {
  return enumLabels[value]?.[lang] || value.replaceAll("_", " ");
}

function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function pageUrl(artifactUrl: string | undefined, page: number): string | null {
  const safe = safeHttpUrl(artifactUrl);
  if (!safe) return null;
  const url = new URL(safe);
  url.hash = `page=${page}`;
  return url.toString();
}

function EvidenceView({evidence, artifactUrl, issues, offerIndex, field, itemIndex, copy}: {
  evidence: Evidence[]; artifactUrl?: string; issues: EvidenceIssue[]; offerIndex: number;
  field: string; itemIndex?: number; copy: Copy;
}) {
  if (!evidence.length) return null;
  return <details className={styles.evidence}>
    <summary>{copy.evidence} · {evidence.map((entry) => `${copy.page} ${entry.page}`).join(", ")}</summary>
    <ul>{evidence.map((entry, index) => {
      const link = pageUrl(artifactUrl, entry.page);
      const hasIssue = issues.some((issue) => issue.offer_index === offerIndex && issue.field === field &&
        issue.item_index === (itemIndex ?? null) && issue.page === entry.page);
      return <li key={`${entry.page}-${index}`}>
        <span className={styles.quote}>“{entry.excerpt}”</span>{" "}
        {link ? <a href={link} target="_blank" rel="noopener noreferrer">{copy.page} {entry.page} ↗</a> : <span>{copy.page} {entry.page}</span>}
        {hasIssue && <span className={styles.issue}> {copy.issue}</span>}
      </li>;
    })}</ul>
  </details>;
}

function TextRow({name, title, value, copy, context}: {
  name: string; title: string; value: TextField | DateField; copy: Copy; context: OfferContext;
}) {
  return <div className={styles.field}><dt>{title}</dt><dd>
    {value.stated && value.value ? value.value : <span className={styles.unknown}>{copy.unknown}</span>}
    {"normalized" in value && value.normalized && <small className={styles.normalized}>{copy.normalized}: {value.normalized}</small>}
    <EvidenceView evidence={value.evidence} field={name} copy={copy} {...context}/>
  </dd></div>;
}

type OfferContext = {artifactUrl?: string; issues: EvidenceIssue[]; offerIndex: number};

function ListRow({name, title, value, copy, context, lang}: {
  name: string; title: string; value: ListField<string>; copy: Copy; context: OfferContext; lang: "en" | "de";
}) {
  return <div className={styles.field}><dt>{title}</dt><dd>
    {value.items.length ? <ul className={styles.valueList}>{value.items.map((item, index) =>
      <li key={index}>{label(item.value, lang)}<EvidenceView evidence={item.evidence} field={name} itemIndex={index} copy={copy} {...context}/></li>,
    )}</ul> : <span className={styles.unknown}>{copy.unknown}</span>}
  </dd></div>;
}

function AssessmentRow({name, title, value, copy, context, lang}: {
  name: string; title: string; value: Assessment; copy: Copy; context: OfferContext; lang: "en" | "de";
}) {
  const unstated = value.level === "unknown" || value.level === "not_stated";
  return <div className={styles.field}><dt>{title}</dt><dd>
    {unstated ? <span className={styles.unknown}>{copy.unknown}</span> : label(value.level, lang)}
    <EvidenceView evidence={value.evidence} field={name} copy={copy} {...context}/>
  </dd></div>;
}

function ContactsRow({value, copy, context}: {value: ListField<Contact>; copy: Copy; context: OfferContext}) {
  return <div className={styles.field}><dt>{copy.contacts}</dt><dd>
    {value.items.length ? <ul className={styles.valueList}>{value.items.map((item, index) => {
      const email = item.value.email;
      const validEmail = email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
      return <li key={index}>{item.value.name && <span>{item.value.name}{email && " · "}</span>}
        {email && (validEmail ? <a href={`mailto:${email}`}>{email}</a> : email)}
        <EvidenceView evidence={item.evidence} field="contacts" itemIndex={index} copy={copy} {...context}/>
      </li>;
    })}</ul> : <span className={styles.unknown}>{copy.unknown}</span>}
  </dd></div>;
}

function ProfileSection({title, children}: {title: string; children: React.ReactNode}) {
  return <section className={styles.section}><h3>{title}</h3><dl className={styles.fields}>{children}</dl></section>;
}

function OfferView({offer, index, project, issues, copy, lang}: {
  offer: Offer; index: number; project: Project; issues: EvidenceIssue[]; copy: Copy; lang: "en" | "de";
}) {
  const context: OfferContext = {artifactUrl: project.artifact_url, issues, offerIndex: index};
  const title = offer.title.stated && offer.title.value ? offer.title.value : `${copy.offer} ${index + 1}`;
  return <article id={`offer-${index + 1}`} className={styles.offer}>
    <div className={styles.offerHeading}><div><p className={styles.eyebrow}>{copy.offer} {index + 1}</p><h2>{title}</h2></div>
      <div className={styles.pageBadges}>{offer.source_pages.map((page) => {
        const href = pageUrl(project.artifact_url, page);
        return href ? <a key={page} href={href} target="_blank" rel="noopener noreferrer">{copy.page} {page} ↗</a>
          : <span key={page}>{copy.page} {page}</span>;
      })}</div>
    </div>
    <div className={styles.summary}><strong>{copy.summary}</strong><p>{offer.search_summary_en}</p></div>
    <ProfileSection title={copy.overview}>
      <TextRow name="title" title={copy.title} value={offer.title} copy={copy} context={context}/>
      <TextRow name="provider_name" title={copy.provider} value={offer.provider_name} copy={copy} context={context}/>
      <ListRow name="project_types" title={copy.projectTypes} value={offer.project_types} copy={copy} context={context} lang={lang}/>
      <ListRow name="degree_level" title={copy.degree} value={offer.degree_level} copy={copy} context={context} lang={lang}/>
      <TextRow name="project_goal" title={copy.goal} value={offer.project_goal} copy={copy} context={context}/>
    </ProfileSection>
    <ProfileSection title={copy.work}>
      <ListRow name="subjects" title={copy.subjects} value={offer.subjects} copy={copy} context={context} lang={lang}/>
      <ListRow name="application_areas" title={copy.areas} value={offer.application_areas} copy={copy} context={context} lang={lang}/>
      <ListRow name="methods_tools" title={copy.methods} value={offer.methods_tools} copy={copy} context={context} lang={lang}/>
      <ListRow name="activities" title={copy.activities} value={offer.activities} copy={copy} context={context} lang={lang}/>
      <ListRow name="work_modes" title={copy.workModes} value={offer.work_modes} copy={copy} context={context} lang={lang}/>
      <ListRow name="deliverables" title={copy.deliverables} value={offer.deliverables} copy={copy} context={context} lang={lang}/>
    </ProfileSection>
    <ProfileSection title={copy.requirements}>
      <ListRow name="prerequisites_required" title={copy.required} value={offer.prerequisites_required} copy={copy} context={context} lang={lang}/>
      <ListRow name="prerequisites_recommended" title={copy.recommended} value={offer.prerequisites_recommended} copy={copy} context={context} lang={lang}/>
      <ListRow name="eligible_study_fields" title={copy.studyFields} value={offer.eligible_study_fields} copy={copy} context={context} lang={lang}/>
      <AssessmentRow name="programming_performed" title={copy.programmingWork} value={offer.programming_performed} copy={copy} context={context} lang={lang}/>
      <AssessmentRow name="programming_required" title={copy.programmingSkill} value={offer.programming_required} copy={copy} context={context} lang={lang}/>
    </ProfileSection>
    <ProfileSection title={copy.practical}>
      <TextRow name="team_size" title={copy.teamSize} value={offer.team_size} copy={copy} context={context}/>
      <TextRow name="duration" title={copy.duration} value={offer.duration} copy={copy} context={context}/>
      <TextRow name="start_date" title={copy.start} value={offer.start_date} copy={copy} context={context}/>
      <TextRow name="application_deadline" title={copy.deadline} value={offer.application_deadline} copy={copy} context={context}/>
      <TextRow name="location" title={copy.location} value={offer.location} copy={copy} context={context}/>
      <AssessmentRow name="work_location_mode" title={copy.locationMode} value={offer.work_location_mode} copy={copy} context={context} lang={lang}/>
      <ListRow name="working_language" title={copy.language} value={offer.working_language} copy={copy} context={context} lang={lang}/>
    </ProfileSection>
    <ProfileSection title={copy.support}>
      <ListRow name="learning_opportunities" title={copy.learning} value={offer.learning_opportunities} copy={copy} context={context} lang={lang}/>
      <ListRow name="support_offered" title={copy.supportOffered} value={offer.support_offered} copy={copy} context={context} lang={lang}/>
    </ProfileSection>
    <ProfileSection title={copy.application}>
      <ContactsRow value={offer.contacts} copy={copy} context={context}/>
      <TextRow name="application_instructions" title={copy.instructions} value={offer.application_instructions} copy={copy} context={context}/>
      <TextRow name="external_url" title={copy.external} value={offer.external_url} copy={copy} context={context}/>
    </ProfileSection>
  </article>;
}

export const dynamic = "force-dynamic";

export default async function ProjectDetails({params}: {params: Promise<{locale: string; slug: string}>}) {
  const {locale, slug} = await params;
  const lang = locale === "de" ? "de" : "en";
  const copy = translations[lang];
  const base = process.env.NEXT_PUBLIC_API_URL || "http://api:8000/api/v1";
  let response: Response;
  try {
    response = await fetch(`${base}/projects/${encodeURIComponent(slug)}/profile`, {cache: "no-store"});
  } catch {
    throw new Error("Project profile API is unavailable");
  }
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error(`Project profile API returned ${response.status}`);
  const detail = await response.json() as ProfileDetail;
  const artifactUrl = safeHttpUrl(detail.project.artifact_url);
  const sourceUrl = safeHttpUrl(detail.project.source_url);
  const badPages = detail.coverage.blank_markdown_pages.join(", ");
  const extractedAt = new Intl.DateTimeFormat(lang === "de" ? "de-DE" : "en-GB", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin",
  }).format(new Date(detail.extracted_at));

  return <>
    <header className="top"><div className="shell"><Link className="brand" href={`/${lang}`}>{copy.brand}</Link>
      <div className="top-actions"><nav className="lang" aria-label="Language">
        <Link href={`/en/projects/${encodeURIComponent(slug)}`} lang="en">EN</Link>
        <Link href={`/de/projects/${encodeURIComponent(slug)}`} lang="de">DE</Link>
      </nav><AuthControls/></div></div></header>
    <main className={styles.page}><div className="shell">
      <Link className={styles.back} href={`/${lang}`}>← {copy.back}</Link>
      <div className={styles.intro}><p className={styles.eyebrow}>{detail.project.reference_code} · {detail.project.chair}</p>
        <h1>{detail.project.title}</h1><p>{copy.intro}</p>
        <div className={styles.links}>{sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer">{copy.source} ↗</a>}
          {artifactUrl && <a href={artifactUrl} target="_blank" rel="noopener noreferrer">{copy.document} ↗</a>}</div>
        <p className={styles.documentMeta}>{copy.documentLanguage}: {label(detail.document.document_language, lang)} · {copy.pages}: {detail.coverage.page_count} · {copy.extracted}: {extractedAt}</p>
      </div>
      {detail.coverage.status !== "text_on_all_pages" && badPages && <p className={styles.alert}>{copy.incomplete} {badPages}</p>}
      {detail.review_flags.includes("unverified_citations") && <p className={styles.alert}>{copy.issues}</p>}
      {detail.document.offers.length > 1 && <><p>{copy.multiple}</p><nav className={styles.offerNav} aria-label={copy.multiple}>
        {detail.document.offers.map((offer, index) => <a key={index} href={`#offer-${index + 1}`}>
          {offer.title.value || `${copy.offer} ${index + 1}`}</a>)}
      </nav></>}
      {detail.document.offers.length === 0 && <p className={styles.alert}>{copy.noOffers}</p>}
      {detail.document.offers.map((offer, index) => <OfferView key={index} offer={offer} index={index} project={detail.project}
        issues={detail.evidence_issues} copy={copy} lang={lang}/>)}
    </div></main>
    <footer className="footer"><div className="shell">{copy.notice}</div></footer>
  </>;
}
