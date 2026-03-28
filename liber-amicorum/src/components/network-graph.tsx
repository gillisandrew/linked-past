import * as d3 from "d3";
import { useRef, useEffect, useState, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { getNetworkData } from "#/lib/data";
import type { NetworkData, NetworkNode } from "#/lib/types";

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

// Muted scholarly palette for nomen-based coloring
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
  const [data, setData] = useState<NetworkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dimensions, setDimensions] = useState({ width: 960, height: 600 });
  const navigate = useNavigate();
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);

  // Load data
  useEffect(() => {
    getNetworkData().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  // Measure container
  useEffect(() => {
    function measure() {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height: rect.height });
      }
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  // Build the graph
  useEffect(() => {
    if (!data || !svgRef.current) return;

    const { width, height } = dimensions;
    const svg = d3.select(svgRef.current);

    // Clear previous render
    svg.selectAll("*").remove();

    // Count connections per node
    const connectionCount = new Map<string, number>();
    for (const e of data.edges) {
      connectionCount.set(e.source, (connectionCount.get(e.source) ?? 0) + 1);
      connectionCount.set(e.target, (connectionCount.get(e.target) ?? 0) + 1);
    }

    // Build sim nodes/edges
    const nodes: SimNode[] = data.nodes.map((n) => ({
      ...n,
      connectionCount: connectionCount.get(n.id) ?? 0,
    }));

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const edges: SimEdge[] = data.edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!,
        type: e.type,
      }));

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
      .attr("stroke-width", 0.8);

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

    // Tooltip
    const tooltip = d3.select(tooltipRef.current);

    // Hover interaction
    nodeSelection
      .on("mouseenter", function (event, d) {
        // Highlight connected edges
        const connectedNodeIds = new Set<string>();
        connectedNodeIds.add(d.id);
        edgeSelection
          .attr("stroke-opacity", (e) => {
            const srcId = (e.source as SimNode).id;
            const tgtId = (e.target as SimNode).id;
            if (srcId === d.id || tgtId === d.id) {
              connectedNodeIds.add(srcId);
              connectedNodeIds.add(tgtId);
              return 1;
            }
            return 0.05;
          })
          .attr("stroke-width", (e) => {
            const srcId = (e.source as SimNode).id;
            const tgtId = (e.target as SimNode).id;
            return srcId === d.id || tgtId === d.id ? 1.5 : 0.8;
          });

        nodeSelection.attr("opacity", (n) => (connectedNodeIds.has(n.id) ? 1 : 0.1));

        d3.select(this).attr("stroke", "#333").attr("stroke-width", 2);

        // Show tooltip
        const eraStr =
          d.eraFrom != null && d.eraTo != null
            ? `${Math.abs(d.eraFrom)} - ${Math.abs(d.eraTo)} BC`
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
        edgeSelection.attr("stroke-opacity", 1).attr("stroke-width", 0.8);
        nodeSelection.attr("opacity", 1);
        d3.select(this).attr("stroke", "rgba(37, 36, 54, 0.3)").attr("stroke-width", 0.5);
        tooltip.style("display", "none");
      });

    // Click to navigate
    nodeSelection.on("click", (_event, d) => {
      navigate({ to: "/persons/$personId", params: { personId: d.id } });
    });

    // Drag behavior
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

    // Force simulation
    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(edges)
          .id((d) => d.id)
          .distance(80),
      )
      .force("charge", d3.forceManyBody().strength(-120))
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
      });

    simulationRef.current = simulation;

    // Stop after stabilization
    simulation.on("end", () => {
      simulation.stop();
    });

    return () => {
      simulation.stop();
    };
  }, [data, dimensions, navigate]);

  // Search/filter highlight
  const handleSearch = useCallback(
    (term: string) => {
      setSearch(term);
      if (!svgRef.current || !data) return;

      const svg = d3.select(svgRef.current);
      const lower = term.toLowerCase().trim();

      if (!lower) {
        svg.selectAll("circle").attr("opacity", 1);
        svg.selectAll("line").attr("stroke-opacity", 1);
        return;
      }

      const matchIds = new Set(
        data.nodes
          .filter(
            (n) =>
              n.name.toLowerCase().includes(lower) ||
              n.id.toLowerCase().includes(lower) ||
              (n.nomen && n.nomen.toLowerCase().includes(lower)),
          )
          .map((n) => n.id),
      );

      svg
        .selectAll<SVGCircleElement, SimNode>("circle")
        .attr("opacity", (d) => (matchIds.has(d.id) ? 1 : 0.08));

      svg.selectAll<SVGLineElement, SimEdge>("line").attr("stroke-opacity", (d) => {
        const srcId = (d.source as SimNode).id;
        const tgtId = (d.target as SimNode).id;
        return matchIds.has(srcId) || matchIds.has(tgtId) ? 1 : 0.03;
      });

      // Zoom to first match
      if (matchIds.size > 0 && matchIds.size <= 10) {
        const simNodes = simulationRef.current?.nodes() ?? [];
        const matchSimNodes = simNodes.filter((n) => matchIds.has(n.id));
        if (matchSimNodes.length > 0) {
          const xExtent = d3.extent(matchSimNodes, (n) => n.x) as [number, number];
          const yExtent = d3.extent(matchSimNodes, (n) => n.y) as [number, number];
          const cx = (xExtent[0] + xExtent[1]) / 2;
          const cy = (yExtent[0] + yExtent[1]) / 2;
          const dx = xExtent[1] - xExtent[0] || 200;
          const dy = yExtent[1] - yExtent[0] || 200;
          const scale = Math.min(dimensions.width / (dx + 100), dimensions.height / (dy + 100), 4);

          const transform = d3.zoomIdentity
            .translate(dimensions.width / 2, dimensions.height / 2)
            .scale(scale)
            .translate(-cx, -cy);

          d3.select(svgRef.current)
            .transition()
            .duration(750)
            .call(d3.zoom<SVGSVGElement, unknown>().transform as any, transform);
        }
      }
    },
    [data, dimensions],
  );

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-200px)] items-center justify-center">
        <p className="text-ink-muted">Loading network data...</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Filter by name, ID, or nomen..."
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="w-full max-w-sm rounded border border-ink/20 bg-parchment px-3 py-1.5 text-sm text-ink placeholder:text-ink-muted/60 focus:border-ink/40 focus:outline-none"
        />
        {data && (
          <span className="text-xs text-ink-muted">
            {data.nodes.length} persons &middot; {data.edges.length} relationships
          </span>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5">
          <svg width="20" height="2">
            <line x1="0" y1="1" x2="20" y2="1" stroke="rgba(37,36,54,0.25)" strokeWidth="1.5" />
          </svg>
          Family
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="20" height="2">
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
          Marriage
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="20" height="2">
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
          Political
        </span>
      </div>

      {/* Graph */}
      <div
        ref={containerRef}
        className="relative overflow-hidden rounded-lg border border-ink/10 bg-parchment-dark"
        style={{ height: "calc(100vh - 260px)" }}
      >
        <svg ref={svgRef} width={dimensions.width} height={dimensions.height} className="block" />
        <div
          ref={tooltipRef}
          className="pointer-events-none fixed z-50 hidden rounded border border-ink/10 bg-parchment px-3 py-2 shadow-lg"
          style={{ display: "none" }}
        />
      </div>
    </div>
  );
}
