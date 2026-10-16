import { useEffect, useState } from "react";
import { api, type FeatureMeta } from "./api";

let cache: FeatureMeta | null = null;

/** Feature specs served by the backend (single source of truth for forms). */
export function useFeatureMeta() {
  const [meta, setMeta] = useState<FeatureMeta | null>(cache);
  const [error, setError] = useState("");
  useEffect(() => {
    if (cache) return;
    api.features().then((m) => { cache = m; setMeta(m); })
      .catch((e) => setError(e.message || "Could not load form definitions."));
  }, []);
  return { meta, error };
}
