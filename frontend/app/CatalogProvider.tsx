"use client";

import {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction} from "react";
import type {Bootstrap, CatalogData} from "./catalogTypes";

type Store = {
  datasets: Map<string, CatalogData>;
  pending: Map<string, Promise<{bootstrap: Bootstrap; data: CatalogData}>>;
  state: Map<string, unknown>;
};
const Context = createContext<Store | null>(null);

export function CatalogProvider({children}: {children: ReactNode}) {
  const store = useRef<Store>({datasets: new Map(), pending: new Map(), state: new Map()});
  return <Context.Provider value={store.current}>{children}</Context.Provider>;
}

function useStore() {
  const store = useContext(Context);
  if (!store) throw new Error("CatalogProvider is required");
  return store;
}

export function useCatalogState<T>(key: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
  const store = useStore();
  const [value, setValue] = useState<T>(() => store.state.has(key) ? store.state.get(key) as T : initial);
  const set = useCallback<Dispatch<SetStateAction<T>>>((action) => {
    // Update the browser-only store synchronously so a navigation sees the latest value.
    const previous = (store.state.has(key) ? store.state.get(key) : initial) as T;
    const next = typeof action === "function" ? (action as (v: T) => T)(previous) : action;
    store.state.set(key, next);
    setValue(next);
  }, [store, key, initial]);
  return [value, set];
}

async function download(bootstrap: Bootstrap): Promise<{bootstrap: Bootstrap; data: CatalogData}> {
  let current = bootstrap;
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(`/api/v1/catalog/${encodeURIComponent(current.version)}`);
    if (response.status === 410 && attempt === 0) {
      const latest = await fetch("/api/v1/catalog", {cache: "no-cache"});
      if (!latest.ok) throw new Error("Catalog bootstrap unavailable");
      current = await latest.json() as Bootstrap;
      continue;
    }
    if (!response.ok) throw new Error("Catalog download failed");
    const data = await response.json() as CatalogData;
    if (data.version !== current.version || !Array.isArray(data.items) || data.items.length !== current.total) {
      throw new Error("Incomplete catalog download");
    }
    return {bootstrap: current, data};
  }
  throw new Error("Catalog generation expired");
}

export function useCatalog(bootstrap: Bootstrap) {
  const store = useStore();
  const [result, setResult] = useState<{sourceVersion: string; bootstrap: Bootstrap; data: CatalogData} | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let mounted = true;
    setError(false);
    const cached = store.datasets.get(bootstrap.version);
    if (cached) { setResult({sourceVersion: bootstrap.version, bootstrap, data: cached}); return; }
    let request = store.pending.get(bootstrap.version);
    if (!request) {
      request = download(bootstrap).then((value) => {
        store.datasets.set(value.data.version, value.data);
        // Bound memory across long-lived browser sessions.
        if (store.datasets.size > 2) store.datasets.delete(store.datasets.keys().next().value!);
        return value;
      }).finally(() => store.pending.delete(bootstrap.version));
      store.pending.set(bootstrap.version, request);
    }
    request.then((value) => { if (mounted) setResult({...value, sourceVersion: bootstrap.version}); }).catch(() => { if (mounted) setError(true); });
    return () => { mounted = false; };
  }, [bootstrap, store, attempt]);
  const current = result?.sourceVersion === bootstrap.version ? result : null;
  return useMemo(() => ({bootstrap: current?.bootstrap || bootstrap, items: current?.data.items || bootstrap.items,
    ready: !!current, error, retry: () => setAttempt((value) => value + 1)}), [current, bootstrap, error]);
}
