import * as d3 from "d3";
import { useRef, useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { Relationship } from "#/lib/types";

// ---------------------------------------------------------------------------
// Relationship classification (mirrors network-graph.tsx)
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

const EDGE_STYLES: Record<RelCategory, { color: string; dasharray: string }> = {
  family: { color: "rgba(37, 36, 54, 0.4)", dasharray: "" },
  marriage: { color: "rgba(159, 90, 90, 0.6)", dasharray: "4,3" },
  political: { color: "rgba(80, 130, 130, 0.5)", dasharray: "2,3" },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EgoGraphProps {
  personId: string;
  personName: string;
  relationships: Relationship[];
}

interface SimNode {
  id: string;
  name: string;
  isCenter: boolean;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimEdge {
  source: SimNode;
  target: SimNode;
  type: string;
  label: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EgoGraph({ personId, personName, relationships }: EgoGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 300 });
  const navigate = useNavigate();

  // Measure container width
  useEffect(() => {
    function measure() {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height: 300 });
      }
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  useEffect(() => {
    if (!svgRef.current || relationships.length === 0) return;

    const { width, height } = dimensions;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Build nodes: center + unique related persons
    const centerNode: SimNode = {
      id: personId,
      name: personName,
      isCenter: true,
    };

    const seen = new Set<string>();
    const peripheralNodes: SimNode[] = [];
    const edges: { sourceId: string; targetId: string; type: string; label: string }[] = [];

    for (const rel of relationships) {
      const relId = rel.relatedPersonId ?? `unknown-${rel.type}-${rel.relatedPersonName}`;
      const relName = rel.relatedPersonName ?? "Unknown";

      if (!seen.has(relId)) {
        seen.add(relId);
        peripheralNodes.push({
          id: relId,
          name: relName,
          isCenter: false,
        });
      }

      edges.push({
        sourceId: personId,
        targetId: relId,
        type: rel.type,
        label: rel.type,
      });
    }

    const nodes: SimNode[] = [centerNode, ...peripheralNodes];
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    const simEdges: SimEdge[] = edges
      .filter((e) => nodeMap.has(e.sourceId) && nodeMap.has(e.targetId))
      .map((e) => ({
        source: nodeMap.get(e.sourceId)!,
        target: nodeMap.get(e.targetId)!,
        type: e.type,
        label: e.label,
      }));

    // Container group for zoom/pan
    const g = svg.append("g");

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);

    // Edges
    const edgeSelection = g
      .append("g")
      .selectAll("line")
      .data(simEdges)
      .join("line")
      .attr("stroke", (d) => EDGE_STYLES[classifyRelationship(d.type)].color)
      .attr("stroke-dasharray", (d) => EDGE_STYLES[classifyRelationship(d.type)].dasharray)
      .attr("stroke-width", 1.2);

    // Edge labels
    const edgeLabelSelection = g
      .append("g")
      .selectAll("text")
      .data(simEdges)
      .join("text")
      .attr("font-size", 9)
      .attr("fill", "rgba(37, 36, 54, 0.5)")
      .attr("text-anchor", "middle")
      .attr("dy", -4)
      .text((d) => d.label);

    // Nodes
    const nodeSelection = g
      .append("g")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => (d.isCenter ? 10 : 6))
      .attr("fill", (d) => (d.isCenter ? "#6b7c6e" : "#8b7355"))
      .attr("stroke", (d) => (d.isCenter ? "rgba(37, 36, 54, 0.6)" : "rgba(37, 36, 54, 0.3)"))
      .attr("stroke-width", (d) => (d.isCenter ? 2 : 1))
      .style("cursor", (d) =>
        d.isCenter ? "default" : d.id.startsWith("unknown-") ? "default" : "pointer",
      );

    // Node labels
    const labelSelection = g
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("font-size", (d) => (d.isCenter ? 12 : 10))
      .attr("font-weight", (d) => (d.isCenter ? "600" : "400"))
      .attr("fill", "rgba(37, 36, 54, 0.8)")
      .attr("text-anchor", "middle")
      .attr("dy", (d) => (d.isCenter ? -16 : -12))
      .text((d) => d.name);

    // Click to navigate
    nodeSelection.on("click", (_event, d) => {
      if (!d.isCenter && d.id && !d.id.startsWith("unknown-")) {
        navigate({ to: "/persons/$personId", params: { personId: d.id } });
      }
    });

    // Hover highlight
    nodeSelection
      .on("mouseenter", function (_event, d) {
        if (!d.isCenter && d.id && !d.id.startsWith("unknown-")) {
          d3.select(this).attr("stroke-width", 2.5).attr("stroke", "#333");
        }
      })
      .on("mouseleave", function (_event, d) {
        d3.select(this)
          .attr("stroke-width", d.isCenter ? 2 : 1)
          .attr("stroke", d.isCenter ? "rgba(37, 36, 54, 0.6)" : "rgba(37, 36, 54, 0.3)");
      });

    // Drag
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

    // Pin the center node
    centerNode.fx = width / 2;
    centerNode.fy = height / 2;

    // Force simulation -- gentle for small graphs
    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(simEdges)
          .id((d) => d.id)
          .distance(100),
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((d) => (d.isCenter ? 16 : 12)),
      )
      .on("tick", () => {
        edgeSelection
          .attr("x1", (d) => d.source.x!)
          .attr("y1", (d) => d.source.y!)
          .attr("x2", (d) => d.target.x!)
          .attr("y2", (d) => d.target.y!);

        edgeLabelSelection
          .attr("x", (d) => (d.source.x! + d.target.x!) / 2)
          .attr("y", (d) => (d.source.y! + d.target.y!) / 2);

        nodeSelection.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);

        labelSelection.attr("x", (d) => d.x!).attr("y", (d) => d.y!);
      });

    return () => {
      simulation.stop();
    };
  }, [personId, personName, relationships, dimensions, navigate]);

  return (
    <div className="w-full">
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-ink-muted mb-2">
        <span className="flex items-center gap-1.5">
          <svg width="20" height="2">
            <line x1="0" y1="1" x2="20" y2="1" stroke="rgba(37,36,54,0.4)" strokeWidth="1.5" />
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
      <div
        ref={containerRef}
        className="relative overflow-hidden rounded-lg border border-ink/10"
        style={{ height: 300 }}
      >
        <svg ref={svgRef} width={dimensions.width} height={dimensions.height} className="block" />
      </div>
    </div>
  );
}
