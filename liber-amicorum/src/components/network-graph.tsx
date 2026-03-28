import * as d3 from "d3";
import { useRef, useEffect, useState, useMemo, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { getNetworkData } from "#/lib/data";
import type { NetworkData, NetworkNode, NetworkEdge } from "#/lib/types";

// ---------------------------------------------------------------------------
// Types for D3 simulation (mutable positions added by d3-force)
// ---------------------------------------------------------------------------

interface SimNode extends NetworkNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  connectionCount: number;
}

interface SimEdge {
  source: SimNode;
  target: SimNode;
  type: string;
}

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
// Component
// ---------------------------------------------------------------------------

export function NetworkGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [allData, setAllData] = useState<NetworkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 960, height: 600 });
  const navigate = useNavigate();
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);

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

  // Measure container with ResizeObserver
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

    // Initial measure
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

  // Build the graph
  useEffect(() => {
    if (!svgRef.current || filteredData.nodes.length === 0) {
      // Clear if no data
      if (svgRef.current) {
        d3.select(svgRef.current).selectAll("*").remove();
      }
      if (simulationRef.current) {
        simulationRef.current.stop();
        simulationRef.current = null;
      }
      return;
    }

    const { width, height } = dimensions;
    const svg = d3.select(svgRef.current);
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    // Stop old simulation
    if (simulationRef.current) {
      simulationRef.current.stop();
      simulationRef.current = null;
    }

    // Clear previous render
    svg.selectAll("*").remove();

    // Count connections per node within filtered set
    const connectionCount = new Map<string, number>();
    for (const e of filteredData.edges) {
      connectionCount.set(e.source, (connectionCount.get(e.source) ?? 0) + 1);
      connectionCount.set(e.target, (connectionCount.get(e.target) ?? 0) + 1);
    }

    // Build sim nodes/edges
    const nodes: SimNode[] = filteredData.nodes.map((n) => ({
      ...n,
      connectionCount: connectionCount.get(n.id) ?? 0,
    }));

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const edges: SimEdge[] = filteredData.edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!,
        type: e.type,
      }));

    const nodeCount = nodes.length;
    const showLabels = nodeCount < 100;

    // Nomen color scale
    const nomina = [...new Set(nodes.map((n) => n.nomen).filter(Boolean))] as string[];
    const nomenColor = d3.scaleOrdinal<string>().domain(nomina).range(NOMEN_COLORS);

    // Node radius scale
    const maxConn = d3.max(nodes, (n) => n.connectionCount) ?? 1;
    const radiusScale = d3.scaleSqrt().domain([0, maxConn]).range([3, 11]);

    // Container group for zoom/pan
    const g = svg.append("g");

    // Zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);

    // Edges
    const edgeSelection = g
      .append("g")
      .attr("class", "edges")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("stroke", (d) => EDGE_STYLES[classifyRelationship(d.type)].color)
      .attr("stroke-dasharray", (d) => EDGE_STYLES[classifyRelationship(d.type)].dasharray)
      .attr("stroke-width", 0.8)
      .attr("stroke-opacity", 0.2);

    // Nodes
    const nodeSelection = g
      .append("g")
      .attr("class", "nodes")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => radiusScale(d.connectionCount))
      .attr("fill", (d) => (d.nomen ? nomenColor(d.nomen) : "#999"))
      .attr("stroke", "rgba(37, 36, 54, 0.3)")
      .attr("stroke-width", 0.5)
      .style("cursor", "pointer");

    // Labels (only when few nodes)
    let labelSelection: d3.Selection<SVGTextElement, SimNode, SVGGElement, unknown> | null = null;
    if (showLabels) {
      labelSelection = g
        .append("g")
        .attr("class", "labels")
        .selectAll("text")
        .data(nodes)
        .join("text")
        .text((d) => d.name || d.id)
        .attr("font-size", 9)
        .attr("dx", (d) => radiusScale(d.connectionCount) + 3)
        .attr("dy", "0.35em")
        .attr("fill", "rgba(37, 36, 54, 0.7)")
        .style("pointer-events", "none");
    }

    // Tooltip
    const tooltip = d3.select(tooltipRef.current);

    // Hover interaction
    nodeSelection
      .on("mouseenter", function (event, d) {
        const connectedNodeIds = new Set<string>();
        connectedNodeIds.add(d.id);
        edgeSelection
          .attr("stroke-opacity", (e) => {
            const srcId = (e.source as SimNode).id;
            const tgtId = (e.target as SimNode).id;
            if (srcId === d.id || tgtId === d.id) {
              connectedNodeIds.add(srcId);
              connectedNodeIds.add(tgtId);
              return 0.8;
            }
            return 0.03;
          })
          .attr("stroke-width", (e) => {
            const srcId = (e.source as SimNode).id;
            const tgtId = (e.target as SimNode).id;
            return srcId === d.id || tgtId === d.id ? 1.5 : 0.8;
          });

        nodeSelection.attr("opacity", (n) => (connectedNodeIds.has(n.id) ? 1 : 0.1));
        if (labelSelection) {
          labelSelection.attr("opacity", (n) => (connectedNodeIds.has(n.id) ? 1 : 0.1));
        }

        d3.select(this).attr("stroke", "#333").attr("stroke-width", 2);

        const eraStr =
          d.eraFrom != null && d.eraTo != null
            ? `${Math.abs(d.eraFrom)} \u2013 ${Math.abs(d.eraTo)} BC`
            : d.eraFrom != null
              ? `fl. ${Math.abs(d.eraFrom)} BC`
              : "";

        tooltip
          .style("display", "block")
          .style("left", `${event.pageX + 12}px`)
          .style("top", `${event.pageY - 10}px`)
          .html(
            `<div class="font-heading font-bold">${d.name || d.id}</div>` +
              (d.nomen ? `<div class="text-xs text-ink-muted">gens ${d.nomen}</div>` : "") +
              (eraStr ? `<div class="text-xs text-ink-muted">${eraStr}</div>` : "") +
              `<div class="text-xs text-ink-muted">${d.connectionCount} connections</div>`,
          );
      })
      .on("mousemove", (event) => {
        tooltip.style("left", `${event.pageX + 12}px`).style("top", `${event.pageY - 10}px`);
      })
      .on("mouseleave", function () {
        edgeSelection.attr("stroke-opacity", 0.2).attr("stroke-width", 0.8);
        nodeSelection.attr("opacity", 1);
        if (labelSelection) {
          labelSelection.attr("opacity", 1);
        }
        d3.select(this).attr("stroke", "rgba(37, 36, 54, 0.3)").attr("stroke-width", 0.5);
        tooltip.style("display", "none");
      });

    // Click to navigate
    nodeSelection.on("click", (_event, d) => {
      navigate({ to: "/persons/$personId", params: { personId: d.id } });
    });

    // Drag behavior
    const simulation = d3.forceSimulation<SimNode>(nodes);

    const drag = d3
      .drag<SVGCircleElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    nodeSelection.call(drag);

    // Adaptive force parameters
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

    // Force simulation
    simulation
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(edges)
          .id((d) => d.id)
          .distance(linkDistance),
      )
      .force("charge", d3.forceManyBody().strength(chargeStrength))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((d) => radiusScale(d.connectionCount) + 2),
      )
      .on("tick", () => {
        edgeSelection
          .attr("x1", (d) => d.source.x!)
          .attr("y1", (d) => d.source.y!)
          .attr("x2", (d) => d.target.x!)
          .attr("y2", (d) => d.target.y!);

        nodeSelection.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);

        if (labelSelection) {
          labelSelection.attr("x", (d) => d.x!).attr("y", (d) => d.y!);
        }
      });

    simulationRef.current = simulation;

    simulation.on("end", () => {
      simulation.stop();
    });

    return () => {
      simulation.stop();
    };
  }, [filteredData, dimensions, navigate]);

  // Era input handler — parse BC year string to a number
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
          <svg ref={svgRef} className="block h-full w-full" />
        )}
        <div
          ref={tooltipRef}
          className="pointer-events-none fixed z-50 hidden rounded border border-ink/10 bg-parchment px-3 py-2 shadow-lg"
          style={{ display: "none" }}
        />
      </div>
    </div>
  );
}
