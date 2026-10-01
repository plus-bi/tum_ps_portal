import type {Chair, Project} from "./[locale]/CatalogClient";

export type Bootstrap = {
  version: string; published_at: string; items: Project[]; total: number;
  last_updated_at?: string; chairs: Chair[]; aliases: Record<string, string>;
  published_profile_filters: string[]; pinned_project_codes: string[];
  facets: {profiles: Record<string, Record<string, number>>};
};
export type CatalogData = {version: string; items: Project[]};
