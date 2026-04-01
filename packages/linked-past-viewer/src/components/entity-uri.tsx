import { datasetForUri, shortUri } from "../lib/uri";
import { DatasetBadge } from "./dataset-badge";

export function EntityUri({ uri }: { uri: string }) {
  const dataset = datasetForUri(uri);
  return (
    <span className="inline-flex items-center gap-1">
      <code className="text-xs text-primary underline">{shortUri(uri)}</code>
      {dataset && <DatasetBadge dataset={dataset} />}
    </span>
  );
}
