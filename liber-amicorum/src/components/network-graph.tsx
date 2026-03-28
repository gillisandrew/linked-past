import { useRef, useEffect, useState, useMemo, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  ReactFlow,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import * as d3 from "d3";
import { getNetworkData } from "#/lib/data";
import type { NetworkData, NetworkNode, NetworkEdge } from "#/lib/types";

// ---------------------------------------------------------------------------
// Relationship classification
// ---------------------------------------------------------------------------

type RelCategory = "family" | "marriage" | "political";

const FAMILY_TYPES = new Set([
  "father of",
  "mother of",
  "son of",
  "daughter of",
  "brother of",
  "sister of",
  "grandson of",
  "grandfather of",
  "grandmother of",
  "granddaughter of",
  "great-grandfather of",
  "great-grandson of",
]);

const MARRIAGE_TYPES = new Set(["married to", "divorced from"]);

function classifyRelationship(type: string): RelCategory {
  const t = type.toLowerCase();
  if (FAMILY_TYPES.has(t)) return "family";
  if (MARRIAGE_TYPES.has(t)) return "marriage";
  return "political";
}

// ---------------------------------------------------------------------------
// Color scales
// ---------------------------------------------------------------------------

const NOMEN_COLORS = [
  "#8b7355",
  "#6b7c6e",
  "#7a6b8a",
  "#8a6b6b",
  "#6b7a8a",
  "#7a8a6b",
  "#8a7a6b",
  "#6b8a7a",
  "#7a6b7a",
  "#6b6b8a",
  "#8a8a6b",
  "#6b8a8a",
  "#8a6b8a",
  "#7a7a6b",
  "#6b7a7a",
  "#7a6b6b",
  "#6b6b7a",
  "#7a7a7a",
  "#8b8b7a",
  "#7a8b8b",
];

const EDGE_STYLES: Record<RelCategory, { color: string; dasharray: string }> = {
  family: { color: "rgba(37, 36, 54, 0.25)", dasharray: "" },
  marriage: { color: "rgba(159, 90, 90, 0.6)", dasharray: "4,3" },
  political: { color: "rgba(80, 130, 130, 0.5)", dasharray: "2,3" },
};

// ---------------------------------------------------------------------------
// D3-force simulation types
// ---------------------------------------------------------------------------

interface SimNode extends NetworkNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  connectionCount: number;
}

interface SimEdge {
  source: string | SimNode;
  target: string | SimNode;
  type: string;
}

// ---------------------------------------------------------------------------
// React Flow custom node data
// ---------------------------------------------------------------------------

interface NetworkNodeData extends Record<string, unknown> {
  name: string;
  nomen: string | null;
  eraFrom: number | null;
  eraTo: number | null;
  size: number;
  color: string;
  showLabel: boolean;
  connectionCount: number;
}

type NetNode = RFNode<NetworkNodeData, "network">;
type NetEdge = RFEdge<Record<string, unknown>>;

// ---------------------------------------------------------------------------
// Custom Network Node
// ---------------------------------------------------------------------------

function NetworkNodeComponent({ data }: NodeProps<NetNode>) {
  const eraStr =
    data.eraFrom != null && data.eraTo != null
      ? `${Math.abs(data.eraFrom)} \u2013 ${Math.abs(data.eraTo)} BC`
      : data.eraFrom != null
        ? `fl. ${Math.abs(data.eraFrom)} BC`
        : "";

  const titleParts = [data.name];
  if (data.nomen) titleParts.push(`gens ${data.nomen}`);
  if (eraStr) titleParts.push(eraStr);
  titleParts.push(`${data.connectionCount} connections`);

  return (
    <div
      className="rounded-full flex items-center justify-center cursor-pointer relative"
      style={{
        width: data.size,
        height: data.size,
        backgroundColor: data.color,
      }}
      title={titleParts.join("\n")}
    >
      {data.showLabel && (
        <span className="absolute top-full mt-1 whitespace-nowrap text-[9px] text-ink pointer-events-none left-1/2 -translate-x-1/2">
          {data.name}
        </span>
      )}
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
    </div>
  );
}

const nodeTypes: NodeTypes = { network: NetworkNodeComponent };

// ---------------------------------------------------------------------------
// Run D3-force simulation synchronously to get positions
// ---------------------------------------------------------------------------

function computeForceLayout(
  rawNodes: NetworkNode[],
  rawEdges: NetworkEdge[],
  width: number,
  height: number,
): { simNodes: SimNode[]; simEdges: SimEdge[] } {
  // Count connections per node
  const connectionCount = new Map<string, number>();
  for (const e of rawEdges) {
    connectionCount.set(e.source, (connectionCount.get(e.source) ?? 0) + 1);
    connectionCount.set(e.target, (connectionCount.get(e.target) ?? 0) + 1);
  }

  const simNodes: SimNode[] = rawNodes.map((n) => ({
    ...n,
    connectionCount: connectionCount.get(n.id) ?? 0,
  }));

  const nodeIds = new Set(simNodes.map((n) => n.id));
  const simEdges: SimEdge[] = rawEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({ source: e.source, target: e.target, type: e.type }));

  const nodeCount = simNodes.length;
  let chargeStrength: number;
  let linkDistance: number;
  if (nodeCount < 100) {
    chargeStrength = -300;
    linkDistance = 100;
  } else if (nodeCount <= 500) {
    chargeStrength = -200;
    linkDistance = 80;
  } else {
    chargeStrength = -100;
    linkDistance = 50;
  }

  const maxConn = d3.max(simNodes, (n) => n.connectionCount) ?? 1;
  const radiusScale = d3.scaleSqrt().domain([0, maxConn]).range([3, 11]);

  const simulation = d3
    .forceSimulation<SimNode>(simNodes)
    .force(
      "link",
      d3
        .forceLink<SimNode, SimEdge>(simEdges)
        .id((d) => d.id)
        .distance(linkDistance),
    )
    .force("charge", d3.forceManyBody().strength(chargeStrength))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force(
      "collision",
      d3.forceCollide<SimNode>().radius((d) => radiusScale(d.connectionCount) + 2),
    )
    .stop();

  // Run simulation synchronously
  const iterations = Math.ceil(
    Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay()),
  );
  for (let i = 0; i < iterations; i++) {
    simulation.tick();
  }

  return { simNodes, simEdges };
}

// ---------------------------------------------------------------------------
// Inner component
// ---------------------------------------------------------------------------

function NetworkGraphInner() {
  const [allData, setAllData] = useState<NetworkData | null>(null);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 960, height: 600 });
  const navigate = useNavigate();
  const { fitView } = useReactFlow();

  // Filter state
  const [eraFrom, setEraFrom] = useState<number | null>(null);
  const [eraTo, setEraTo] = useState<number | null>(null);
  const [gensInput, setGensInput] = useState("");
  const [showFamily, setShowFamily] = useState(true);
  const [showMarriage, setShowMarriage] = useState(true);
  const [showPolitical, setShowPolitical] = useState(true);

  // Load data
  useEffect(() => {
    getNetworkData().then((d) => {
      setAllData(d);
      setLoading(false);
    });
  }, []);

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });
    observer.observe(el);

    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setDimensions({ width: rect.width, height: rect.height });
    }

    return () => observer.disconnect();
  }, []);

  // Parse gens filter
  const gensFilter = useMemo(() => {
    if (!gensInput.trim()) return [];
    return gensInput
      .split(",")
      .map((g) => g.trim().toLowerCase())
      .filter(Boolean);
  }, [gensInput]);

  // Filter data
  const filteredData = useMemo(() => {
    if (!allData) return { nodes: [] as NetworkNode[], edges: [] as NetworkEdge[] };

    let nodes = allData.nodes;
    let edges = allData.edges;

    // 1. Filter by era range (values are negative for BC)
    if (eraFrom != null) {
      const fromVal = -Math.abs(eraFrom);
      nodes = nodes.filter((n) => n.eraTo == null || n.eraTo >= fromVal);
    }
    if (eraTo != null) {
      const toVal = -Math.abs(eraTo);
      nodes = nodes.filter((n) => n.eraFrom == null || n.eraFrom <= toVal);
    }

    // 2. Filter by gens (with 1-degree neighbors)
    if (gensFilter.length > 0) {
      const nodeIds = new Set(nodes.map((n) => n.id));
      const directMatches = new Set(
        nodes.filter((n) => n.nomen && gensFilter.includes(n.nomen.toLowerCase())).map((n) => n.id),
      );
      const neighbors = new Set<string>();
      for (const e of edges) {
        if (nodeIds.has(e.source) && nodeIds.has(e.target)) {
          if (directMatches.has(e.source)) neighbors.add(e.target);
          if (directMatches.has(e.target)) neighbors.add(e.source);
        }
      }
      const keepIds = new Set([...directMatches, ...neighbors]);
      nodes = nodes.filter((n) => keepIds.has(n.id));
    }

    // 3. Filter edges to remaining nodes + relationship types
    const nodeIds = new Set(nodes.map((n) => n.id));
    edges = edges.filter((e) => {
      if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) return false;
      const cat = classifyRelationship(e.type);
      if (cat === "family" && !showFamily) return false;
      if (cat === "marriage" && !showMarriage) return false;
      if (cat === "political" && !showPolitical) return false;
      return true;
    });

    // 4. Remove orphan nodes
    const connectedIds = new Set<string>();
    for (const e of edges) {
      connectedIds.add(e.source);
      connectedIds.add(e.target);
    }
    nodes = nodes.filter((n) => connectedIds.has(n.id));

    return { nodes, edges };
  }, [allData, eraFrom, eraTo, gensFilter, showFamily, showMarriage, showPolitical]);

  // Build React Flow nodes/edges from force layout
  const { rfNodes, rfEdges } = useMemo(() => {
    if (filteredData.nodes.length === 0) {
      return { rfNodes: [] as NetNode[], rfEdges: [] as NetEdge[] };
    }

    const { width, height } = dimensions;
    const { simNodes } = computeForceLayout(filteredData.nodes, filteredData.edges, width, height);

    const showLabels = simNodes.length < 100;
    const nomina = [...new Set(simNodes.map((n) => n.nomen).filter(Boolean))] as string[];
    const nomenColor = d3.scaleOrdinal<string>().domain(nomina).range(NOMEN_COLORS);
    const maxConn = d3.max(simNodes, (n) => n.connectionCount) ?? 1;
    const radiusScale = d3.scaleSqrt().domain([0, maxConn]).range([6, 22]);

    const rfNodes: NetNode[] = simNodes.map((n) => {
      const size = radiusScale(n.connectionCount);
      return {
        id: n.id,
        type: "network",
        position: { x: (n.x ?? 0) - size / 2, y: (n.y ?? 0) - size / 2 },
        data: {
          name: n.name,
          nomen: n.nomen,
          eraFrom: n.eraFrom,
          eraTo: n.eraTo,
          size,
          color: n.nomen ? nomenColor(n.nomen) : "#999",
          showLabel: showLabels,
          connectionCount: n.connectionCount,
        },
      };
    });

    const rfEdges: NetEdge[] = filteredData.edges
      .filter((e) => {
        const nodeIds = new Set(simNodes.map((n) => n.id));
        return nodeIds.has(e.source) && nodeIds.has(e.target);
      })
      .map((e, i) => {
        const cat = classifyRelationship(e.type);
        const style = EDGE_STYLES[cat];
        return {
          id: `net-e-${i}`,
          source: e.source,
          target: e.target,
          style: {
            stroke: style.color,
            strokeDasharray: style.dasharray || undefined,
            strokeWidth: 0.8,
            opacity: 0.4,
          },
        };
      });

    return { rfNodes, rfEdges };
  }, [filteredData, dimensions]);

  // Fit view when data changes
  useEffect(() => {
    if (rfNodes.length > 0) {
      const t = setTimeout(() => fitView({ padding: 0.05, duration: 300 }), 50);
      return () => clearTimeout(t);
    }
  }, [rfNodes, rfEdges, fitView]);

  const handleEraInput = useCallback(
    (setter: (v: number | null) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value.trim();
      if (raw === "") {
        setter(null);
      } else {
        const num = parseInt(raw, 10);
        if (!isNaN(num)) setter(num);
      }
    },
    [],
  );

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-200px)] items-center justify-center">
        <p className="text-ink-muted">Loading network data...</p>
      </div>
    );
  }

  const totalNodes = allData?.nodes.length ?? 0;

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Filter controls */}
      <div className="space-y-2">
        {/* Era range */}
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="font-heading font-semibold text-ink">Era</label>
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              inputMode="numeric"
              placeholder="e.g. 100"
              value={eraFrom ?? ""}
              onChange={handleEraInput(setEraFrom)}
              className="w-20 rounded border border-ink/20 bg-parchment px-2 py-1 text-sm text-ink placeholder:text-ink-muted/50 focus:border-ink/40 focus:outline-none"
            />
            <span className="text-ink-muted">BC to</span>
            <input
              type="text"
              inputMode="numeric"
              placeholder="e.g. 50"
              value={eraTo ?? ""}
              onChange={handleEraInput(setEraTo)}
              className="w-20 rounded border border-ink/20 bg-parchment px-2 py-1 text-sm text-ink placeholder:text-ink-muted/50 focus:border-ink/40 focus:outline-none"
            />
            <span className="text-ink-muted">BC</span>
          </div>
        </div>

        {/* Gens filter */}
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="font-heading font-semibold text-ink">Gens</label>
          <input
            type="text"
            placeholder='e.g. "Cornelius" or "Cornelius, Caecilius"'
            value={gensInput}
            onChange={(e) => setGensInput(e.target.value)}
            className="w-full max-w-sm rounded border border-ink/20 bg-parchment px-2 py-1 text-sm text-ink placeholder:text-ink-muted/50 focus:border-ink/40 focus:outline-none"
          />
        </div>

        {/* Relationship toggles + count */}
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={showFamily}
              onChange={(e) => setShowFamily(e.target.checked)}
              className="accent-ink"
            />
            <svg width="20" height="2" className="inline">
              <line x1="0" y1="1" x2="20" y2="1" stroke="rgba(37,36,54,0.25)" strokeWidth="1.5" />
            </svg>
            <span className="text-ink-muted">Family</span>
          </label>
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={showMarriage}
              onChange={(e) => setShowMarriage(e.target.checked)}
              className="accent-ink"
            />
            <svg width="20" height="2" className="inline">
              <line
                x1="0"
                y1="1"
                x2="20"
                y2="1"
                stroke="rgba(159,90,90,0.6)"
                strokeWidth="1.5"
                strokeDasharray="4,3"
              />
            </svg>
            <span className="text-ink-muted">Marriage</span>
          </label>
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={showPolitical}
              onChange={(e) => setShowPolitical(e.target.checked)}
              className="accent-ink"
            />
            <svg width="20" height="2" className="inline">
              <line
                x1="0"
                y1="1"
                x2="20"
                y2="1"
                stroke="rgba(80,130,130,0.5)"
                strokeWidth="1.5"
                strokeDasharray="2,3"
              />
            </svg>
            <span className="text-ink-muted">Political</span>
          </label>

          <span className="text-xs text-ink-muted">
            Showing {filteredData.nodes.length} of {totalNodes} persons, {filteredData.edges.length}{" "}
            edges
          </span>
        </div>
      </div>

      {/* Graph */}
      <div
        ref={containerRef}
        className="relative min-h-0 w-full flex-1 overflow-hidden rounded-lg border border-ink/10 bg-parchment-dark"
        style={{ height: "calc(100vh - 280px)" }}
      >
        {filteredData.nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-ink-muted">
              No persons match the current filters. Try widening the era range or clearing the gens
              filter.
            </p>
          </div>
        ) : (
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.1}
            maxZoom={8}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            onNodeClick={(_event, node) => {
              navigate({ to: "/persons/$personId", params: { personId: node.id } });
            }}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported component
// ---------------------------------------------------------------------------

export function NetworkGraph() {
  return (
    <ReactFlowProvider>
      <NetworkGraphInner />
    </ReactFlowProvider>
  );
}
