import type {Bootstrap} from "./catalogTypes";

export const catalogBase = process.env.NEXT_PUBLIC_API_URL || "http://api:8000/api/v1";
export async function loadBootstrap(): Promise<Bootstrap> {
  const response = await fetch(`${catalogBase}/catalog`, {next: {revalidate: 86400, tags: ["catalog"]}});
  if (!response.ok) throw new Error(`Catalog unavailable (${response.status})`);
  return response.json() as Promise<Bootstrap>;
}
