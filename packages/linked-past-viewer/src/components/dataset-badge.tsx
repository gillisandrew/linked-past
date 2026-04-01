const COLORS: Record<string, string> = {
  dprr: "bg-blue-500",
  pleiades: "bg-green-500",
  periodo: "bg-purple-500",
  nomisma: "bg-yellow-500 text-black",
  crro: "bg-orange-500",
  ocre: "bg-red-500",
  edh: "bg-cyan-500",
};

export function DatasetBadge({ dataset }: { dataset: string }) {
  const color = COLORS[dataset] ?? "bg-gray-500";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold text-white ${color}`}>
      {dataset}
    </span>
  );
}
