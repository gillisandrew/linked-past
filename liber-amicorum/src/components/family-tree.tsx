import * as d3 from "d3";
import { useRef, useEffect, useState, useCallback } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronUp, ChevronDown } from "lucide-react";
import { getPersonById } from "#/lib/data";
import type { Person } from "#/lib/types";

// ---------------------------------------------------------------------------
// Relationship classification
// ---------------------------------------------------------------------------

type RelDirection = "ancestor" | "descendant" | "spouse" | "other";

const SPOUSE_TYPES = new Set(["married to", "divorced from", "wife of", "husband of"]);

const ANCESTOR_TYPES = new Set([
  "son of",
  "daughter of",
  "adopted son of",
  "adopted daughter of",
  "grandson of",
  "granddaughter of",
  "great-grandson of",
]);

const DESCENDANT_TYPES = new Set([
  "father of",
  "mother of",
  "grandfather of",
  "grandmother of",
  "great-grandfather of",
]);

function classifyRelationship(type: string): RelDirection {
  const t = type.toLowerCase();
  if (ANCESTOR_TYPES.has(t)) return "ancestor";
  if (DESCENDANT_TYPES.has(t)) return "descendant";
  if (SPOUSE_TYPES.has(t)) return "spouse";
  return "other";
}

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const COLORS = {
  root: "#6b7c6e",
  family: "#a0785a",
  spouse: "#b07080",
  other: "#5a8a8a",
  edge: "rgba(37, 36, 54, 0.35)",
  edgeSpouse: "rgba(159, 90, 90, 0.5)",
  edgeOther: "rgba(80, 130, 130, 0.4)",
  text: "rgba(37, 36, 54, 0.85)",
  textMuted: "rgba(37, 36, 54, 0.55)",
  expandBtn: "#a0785a",
  expandBtnHover: "#8a6548",
  expandBtnUp: "#6b7c6e",
  expandBtnUpHover: "#566654",
  loadingSpinner: "#a0785a",
  generationBand: "rgba(37, 36, 54, 0.03)",
  generationLine: "rgba(37, 36, 54, 0.08)",
  generationLabel: "rgba(37, 36, 54, 0.3)",
};

// ---------------------------------------------------------------------------
// Family node type (flat graph with generation levels)
// ---------------------------------------------------------------------------

interface FamilyNode {
  id: string;
  name: string;
  generation: number; // relative to root: negative = ancestors, positive = descendants
  relationType: string; // relationship label that introduced this node
  direction: RelDirection; // ancestor or descendant direction
  uncertain: boolean;
  expanded: boolean;
  loading: boolean;
  hasPersonId: boolean; // can we navigate / expand?
  parentNodeId: string | null; // the node that introduced this one (for drawing edges)
  spouses: { id: string; name: string; type: string; hasPersonId: boolean }[];
}

interface FamilyGraph {
  nodes: Map<string, FamilyNode>;
  rootId: string;
}

// ---------------------------------------------------------------------------
// Build initial graph from person data
// ---------------------------------------------------------------------------

function buildInitialGraph(person: Person): FamilyGraph {
  const nodes = new Map<string, FamilyNode>();

  const rootNode: FamilyNode = {
    id: person.id,
    name: person.name,
    generation: 0,
    relationType: "",
    direction: "descendant",
    uncertain: false,
    expanded: true,
    loading: false,
    hasPersonId: true,
    parentNodeId: null,
    spouses: [],
  };
  nodes.set(person.id, rootNode);

  for (const rel of person.relationships) {
    const dir = classifyRelationship(rel.type);
    const id = rel.relatedPersonId ?? `unknown-${rel.type}-${rel.relatedPersonName}`;
    const name = rel.relatedPersonName ?? "Unknown";
    const hasId = rel.relatedPersonId != null;

    if (dir === "spouse") {
      rootNode.spouses.push({ id, name, type: rel.type, hasPersonId: hasId });
    } else if (dir === "ancestor") {
      nodes.set(id, {
        id,
        name,
        generation: -1,
        relationType: rel.type,
        direction: "ancestor",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: person.id,
        spouses: [],
      });
    } else if (dir === "descendant") {
      nodes.set(id, {
        id,
        name,
        generation: 1,
        relationType: rel.type,
        direction: "descendant",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: person.id,
        spouses: [],
      });
    }
    // "other" relationships are skipped for tree layout
  }

  return { nodes, rootId: person.id };
}

// ---------------------------------------------------------------------------
// Graph manipulation helpers
// ---------------------------------------------------------------------------

function cloneGraph(graph: FamilyGraph): FamilyGraph {
  const nodes = new Map<string, FamilyNode>();
  for (const [id, node] of graph.nodes) {
    nodes.set(id, { ...node, spouses: [...node.spouses] });
  }
  return { nodes, rootId: graph.rootId };
}

function markLoading(graph: FamilyGraph, nodeId: string): FamilyGraph {
  const clone = cloneGraph(graph);
  const node = clone.nodes.get(nodeId);
  if (node) node.loading = true;
  return clone;
}

function expandGraphNode(graph: FamilyGraph, nodeId: string, personData: Person): FamilyGraph {
  const clone = cloneGraph(graph);
  const node = clone.nodes.get(nodeId);
  if (!node) return clone;

  node.loading = false;
  node.expanded = true;

  const existingIds = new Set(clone.nodes.keys());
  // Also track spouse IDs already present on any node
  for (const n of clone.nodes.values()) {
    for (const s of n.spouses) existingIds.add(s.id);
  }

  for (const rel of personData.relationships) {
    const dir = classifyRelationship(rel.type);
    const id = rel.relatedPersonId ?? `unknown-${rel.type}-${rel.relatedPersonName}`;
    const name = rel.relatedPersonName ?? "Unknown";
    const hasId = rel.relatedPersonId != null;

    if (existingIds.has(id)) continue;
    existingIds.add(id);

    if (dir === "spouse") {
      node.spouses.push({ id, name, type: rel.type, hasPersonId: hasId });
    } else if (dir === "ancestor" && node.direction === "ancestor") {
      // Expanding an ancestor node: look for further ancestors (parents)
      clone.nodes.set(id, {
        id,
        name,
        generation: node.generation - 1,
        relationType: rel.type,
        direction: "ancestor",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: nodeId,
        spouses: [],
      });
    } else if (dir === "descendant" && node.direction === "descendant") {
      // Expanding a descendant node: look for further descendants (children)
      clone.nodes.set(id, {
        id,
        name,
        generation: node.generation + 1,
        relationType: rel.type,
        direction: "descendant",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: nodeId,
        spouses: [],
      });
    } else if (dir === "ancestor" && node.direction === "descendant") {
      // A descendant node reveals a parent -- that goes upward but we only track
      // if we are currently in the root. For non-root descendants, skip ancestors.
    } else if (dir === "descendant" && node.direction === "ancestor") {
      // An ancestor node reveals children -- those go downward but we only track
      // them for the root's immediate context. Skip for non-root ancestors.
    }
  }

  return clone;
}

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const NODE_W = 150;
const NODE_H = 38;
const NODE_RX = 6;
const EXPAND_R = 10;
const GEN_HEIGHT = 110; // vertical spacing between generations
const H_GAP = 30; // horizontal gap between nodes

// ---------------------------------------------------------------------------
// Generation label
// ---------------------------------------------------------------------------

function generationLabel(gen: number): string {
  if (gen === 0) return "Self";
  if (gen === -1) return "Parent";
  if (gen === -2) return "Grandparent";
  if (gen < -2) return `${"Great-".repeat(-gen - 2)}Grandparent`;
  if (gen === 1) return "Child";
  if (gen === 2) return "Grandchild";
  return `${"Great-".repeat(gen - 2)}Grandchild`;
}

// ---------------------------------------------------------------------------
// Custom layout: position nodes by generation
// ---------------------------------------------------------------------------

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  data: FamilyNode;
}

interface LayoutEdge {
  sourceId: string;
  targetId: string;
  label: string;
}

interface Layout {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  generations: Map<number, LayoutNode[]>;
  minGen: number;
  maxGen: number;
  width: number;
  height: number;
}

function computeLayout(graph: FamilyGraph): Layout {
  // Group nodes by generation
  const genGroups = new Map<number, FamilyNode[]>();
  for (const node of graph.nodes.values()) {
    const gen = node.generation;
    if (!genGroups.has(gen)) genGroups.set(gen, []);
    genGroups.get(gen)!.push(node);
  }

  const gens = [...genGroups.keys()].sort((a, b) => a - b);
  const minGen = gens.length > 0 ? gens[0] : 0;
  const maxGen = gens.length > 0 ? gens[gens.length - 1] : 0;

  // Y position: generation 0 is in the middle. Ancestors go up (negative gen),
  // descendants go down (positive gen).
  // We'll compute Y such that gen 0 is at a known position.
  const genOffsetY = -minGen; // shift so minGen maps to row 0

  const layoutNodes: LayoutNode[] = [];
  const layoutGenerations = new Map<number, LayoutNode[]>();
  const nodeMap = new Map<string, LayoutNode>();

  for (const gen of gens) {
    const nodesInGen = genGroups.get(gen)!;

    // Count total items including spouses for width calculation
    let totalSlots = 0;
    for (const n of nodesInGen) {
      totalSlots += 1 + n.spouses.length;
    }

    const rowWidth = totalSlots * (NODE_W + H_GAP) - H_GAP;
    let currentX = -rowWidth / 2;
    const y = (gen + genOffsetY) * GEN_HEIGHT;
    const genLayoutNodes: LayoutNode[] = [];

    for (const node of nodesInGen) {
      const ln: LayoutNode = {
        id: node.id,
        x: currentX + NODE_W / 2,
        y,
        data: node,
      };
      layoutNodes.push(ln);
      genLayoutNodes.push(ln);
      nodeMap.set(node.id, ln);
      currentX += NODE_W + H_GAP;

      // Spouses are positioned right next to this node
      for (const spouse of node.spouses) {
        const sln: LayoutNode = {
          id: spouse.id,
          x: currentX + NODE_W / 2,
          y,
          data: {
            id: spouse.id,
            name: spouse.name,
            generation: node.generation,
            relationType: spouse.type,
            direction: "spouse" as RelDirection,
            uncertain: false,
            expanded: false,
            loading: false,
            hasPersonId: spouse.hasPersonId,
            parentNodeId: null,
            spouses: [],
          },
        };
        layoutNodes.push(sln);
        genLayoutNodes.push(sln);
        nodeMap.set(spouse.id, sln);
        currentX += NODE_W + H_GAP;
      }
    }

    layoutGenerations.set(gen, genLayoutNodes);
  }

  // Build edges from parentNodeId links
  const edges: LayoutEdge[] = [];
  for (const node of graph.nodes.values()) {
    if (node.parentNodeId && nodeMap.has(node.parentNodeId) && nodeMap.has(node.id)) {
      edges.push({
        sourceId: node.parentNodeId,
        targetId: node.id,
        label: node.relationType,
      });
    }
  }

  // Compute bounds
  let minX = Infinity;
  let maxX = -Infinity;
  for (const ln of layoutNodes) {
    if (ln.x - NODE_W / 2 < minX) minX = ln.x - NODE_W / 2;
    if (ln.x + NODE_W / 2 > maxX) maxX = ln.x + NODE_W / 2;
  }

  const pad = 80;
  const width = Math.max(400, maxX - minX + pad * 2);
  const height = Math.max(300, (maxGen - minGen + 1) * GEN_HEIGHT + pad * 2);

  // Re-center: shift all nodes so the layout is centered in the width
  const centerShift = -(minX + maxX) / 2;
  for (const ln of layoutNodes) {
    ln.x += centerShift;
  }

  return {
    nodes: layoutNodes,
    edges,
    generations: layoutGenerations,
    minGen,
    maxGen,
    width,
    height,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface FamilyTreeProps {
  person: Person;
}

export function FamilyTree({ person }: FamilyTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [graph, setGraph] = useState<FamilyGraph>(() => buildInitialGraph(person));
  const [containerWidth, setContainerWidth] = useState(800);

  // Reset graph when person changes
  useEffect(() => {
    setGraph(buildInitialGraph(person));
  }, [person]);

  // Measure container
  useEffect(() => {
    function measure() {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.getBoundingClientRect().width);
      }
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  const expandNode = useCallback(async (nodeId: string) => {
    setGraph((prev) => markLoading(prev, nodeId));
    const personData = await getPersonById(nodeId);
    if (!personData) {
      setGraph((prev) => {
        const clone = cloneGraph(prev);
        const node = clone.nodes.get(nodeId);
        if (node) {
          node.loading = false;
          node.expanded = true;
        }
        return clone;
      });
      return;
    }
    setGraph((prev) => expandGraphNode(prev, nodeId, personData));
  }, []);

  // D3 rendering
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const layout = computeLayout(graph);

    const svgW = Math.max(containerWidth, layout.width);
    const svgH = Math.max(300, layout.height);

    svg.attr("width", svgW).attr("height", svgH);

    // Center offset: put generation 0 in the middle vertically
    const genOffsetY = -layout.minGen;
    const rootY = genOffsetY * GEN_HEIGHT;
    const offsetX = svgW / 2;
    const offsetY = svgH / 2 - rootY + (layout.minGen < 0 ? 0 : 40);

    const g = svg.append("g").attr("transform", `translate(${offsetX},${offsetY})`);

    // Add zoom
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);
    svg.call(zoom.transform, d3.zoomIdentity.translate(offsetX, offsetY));

    // Build node lookup for layout
    const nodeMap = new Map<string, LayoutNode>();
    for (const ln of layout.nodes) {
      nodeMap.set(ln.id, ln);
    }

    // -----------------------------------------------------------------------
    // Draw generation bands and labels
    // -----------------------------------------------------------------------
    const genBandGroup = g.append("g").attr("class", "gen-bands");
    const bandHalfH = GEN_HEIGHT / 2;

    // Compute the horizontal extent for bands
    let bandMinX = -svgW;
    let bandMaxX = svgW;
    for (const ln of layout.nodes) {
      if (ln.x - NODE_W < bandMinX) bandMinX = ln.x - NODE_W;
      if (ln.x + NODE_W > bandMaxX) bandMaxX = ln.x + NODE_W;
    }
    bandMinX -= 200;
    bandMaxX += 200;

    for (let gen = layout.minGen; gen <= layout.maxGen; gen++) {
      const y = (gen + genOffsetY) * GEN_HEIGHT;

      // Alternating band
      if (gen % 2 !== 0) {
        genBandGroup
          .append("rect")
          .attr("x", bandMinX)
          .attr("y", y - bandHalfH)
          .attr("width", bandMaxX - bandMinX)
          .attr("height", GEN_HEIGHT)
          .attr("fill", COLORS.generationBand)
          .attr("pointer-events", "none");
      }

      // Horizontal separator line
      genBandGroup
        .append("line")
        .attr("x1", bandMinX)
        .attr("y1", y - bandHalfH)
        .attr("x2", bandMaxX)
        .attr("y2", y - bandHalfH)
        .attr("stroke", COLORS.generationLine)
        .attr("stroke-width", 1)
        .attr("pointer-events", "none");

      // Generation label on left
      genBandGroup
        .append("text")
        .attr("x", bandMinX + 8)
        .attr("y", y + 4)
        .attr("font-size", 10)
        .attr("fill", COLORS.generationLabel)
        .attr("font-style", "italic")
        .attr("pointer-events", "none")
        .text(generationLabel(gen));
    }

    // -----------------------------------------------------------------------
    // Draw edges (parent-child links)
    // -----------------------------------------------------------------------
    const edgeGroup = g.append("g");
    const edgeLabelGroup = g.append("g");

    for (const edge of layout.edges) {
      const source = nodeMap.get(edge.sourceId);
      const target = nodeMap.get(edge.targetId);
      if (!source || !target) continue;

      // For ancestor direction (target above source), edge exits top of source
      const isUpward = target.data.generation < source.data.generation;
      const sy = source.y + (isUpward ? -NODE_H / 2 : NODE_H / 2);
      const ty = target.y + (isUpward ? NODE_H / 2 : -NODE_H / 2);
      const my = (sy + ty) / 2;

      edgeGroup
        .append("path")
        .attr("d", `M${source.x},${sy} C${source.x},${my} ${target.x},${my} ${target.x},${ty}`)
        .attr("fill", "none")
        .attr("stroke", COLORS.edge)
        .attr("stroke-width", 1.5);

      // Edge label (hidden by default, shown on hover)
      edgeLabelGroup
        .append("text")
        .attr("x", (source.x + target.x) / 2)
        .attr("y", (sy + ty) / 2)
        .attr("text-anchor", "middle")
        .attr("font-size", 9)
        .attr("fill", COLORS.textMuted)
        .attr("opacity", 0)
        .attr("data-source", edge.sourceId)
        .attr("data-target", edge.targetId)
        .text(edge.label);
    }

    // -----------------------------------------------------------------------
    // Draw spouse connectors (horizontal double line)
    // -----------------------------------------------------------------------
    for (const node of graph.nodes.values()) {
      if (node.spouses.length === 0) continue;
      const ln = nodeMap.get(node.id);
      if (!ln) continue;

      for (const spouse of node.spouses) {
        const sln = nodeMap.get(spouse.id);
        if (!sln) continue;

        const isDivorced = spouse.type === "divorced from";
        const x1 = ln.x + NODE_W / 2;
        const x2 = sln.x - NODE_W / 2;
        const cy = ln.y;

        // Double line
        edgeGroup
          .append("line")
          .attr("x1", x1)
          .attr("y1", cy - 2)
          .attr("x2", x2)
          .attr("y2", cy - 2)
          .attr("stroke", COLORS.edgeSpouse)
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", isDivorced ? "3,3" : "");
        edgeGroup
          .append("line")
          .attr("x1", x1)
          .attr("y1", cy + 2)
          .attr("x2", x2)
          .attr("y2", cy + 2)
          .attr("stroke", COLORS.edgeSpouse)
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", isDivorced ? "3,3" : "");
      }
    }

    // -----------------------------------------------------------------------
    // Draw nodes
    // -----------------------------------------------------------------------
    const nodeGroups = g
      .append("g")
      .selectAll<SVGGElement, LayoutNode>("g")
      .data(layout.nodes)
      .join("g")
      .attr("transform", (d) => `translate(${d.x},${d.y})`);

    // Node rectangles
    nodeGroups
      .append("rect")
      .attr("x", -NODE_W / 2)
      .attr("y", -NODE_H / 2)
      .attr("width", NODE_W)
      .attr("height", NODE_H)
      .attr("rx", NODE_RX)
      .attr("fill", "white")
      .attr("stroke", (d) => {
        if (d.data.id === person.id) return COLORS.root;
        if (d.data.direction === "spouse") return COLORS.spouse;
        return COLORS.family;
      })
      .attr("stroke-width", (d) => (d.data.id === person.id ? 2.5 : 1));

    // Node names
    nodeGroups
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", (d) => (d.data.id !== person.id && d.data.relationType ? -2 : 1))
      .attr("font-size", (d) => (d.data.id === person.id ? 12 : 11))
      .attr("font-weight", (d) => (d.data.id === person.id ? "600" : "400"))
      .attr("fill", COLORS.text)
      .text((d) => {
        const name = d.data.name;
        return name.length > 20 ? name.slice(0, 18) + "\u2026" : name;
      });

    // Relationship label below name (for non-root)
    nodeGroups
      .filter((d) => d.data.id !== person.id && d.data.relationType !== "")
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 10)
      .attr("font-size", 8)
      .attr("fill", COLORS.textMuted)
      .text((d) => d.data.relationType);

    // Uncertainty badge
    nodeGroups
      .filter((d) => d.data.uncertain)
      .append("text")
      .attr("x", NODE_W / 2 - 4)
      .attr("y", -NODE_H / 2 + 10)
      .attr("text-anchor", "middle")
      .attr("font-size", 10)
      .attr("font-weight", "bold")
      .attr("fill", COLORS.spouse)
      .text("?");

    // Loading spinner
    nodeGroups
      .filter((d) => d.data.loading)
      .append("circle")
      .attr("cx", 0)
      .attr("cy", (d) => (d.data.direction === "ancestor" ? -NODE_H / 2 - 14 : NODE_H / 2 + 14))
      .attr("r", 4)
      .attr("fill", "none")
      .attr("stroke", COLORS.loadingSpinner)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "6,6")
      .attr("class", "animate-spin-slow");

    // -----------------------------------------------------------------------
    // Expand buttons: upward for ancestors, downward for descendants
    // -----------------------------------------------------------------------

    // Ancestor expand (upward arrow) - nodes with direction "ancestor" that aren't expanded
    const expandableUp = nodeGroups.filter(
      (d) =>
        d.data.direction === "ancestor" &&
        !d.data.expanded &&
        !d.data.loading &&
        d.data.hasPersonId,
    );

    expandableUp
      .append("circle")
      .attr("cy", -NODE_H / 2 - 14)
      .attr("r", EXPAND_R)
      .attr("fill", COLORS.expandBtnUp)
      .attr("stroke", "white")
      .attr("stroke-width", 1.5)
      .style("cursor", "pointer")
      .on("mouseenter", function () {
        d3.select(this).attr("fill", COLORS.expandBtnUpHover);
      })
      .on("mouseleave", function () {
        d3.select(this).attr("fill", COLORS.expandBtnUp);
      })
      .on("click", (_event, d) => {
        _event.stopPropagation();
        expandNode(d.data.id);
      });

    // Upward chevron (▲ shape via path)
    expandableUp
      .append("path")
      .attr("d", `M-4,${-NODE_H / 2 - 11}L0,${-NODE_H / 2 - 17}L4,${-NODE_H / 2 - 11}`)
      .attr("fill", "none")
      .attr("stroke", "white")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .style("pointer-events", "none");

    // Descendant expand (downward arrow)
    const expandableDown = nodeGroups.filter(
      (d) =>
        d.data.direction === "descendant" &&
        !d.data.expanded &&
        !d.data.loading &&
        d.data.hasPersonId,
    );

    expandableDown
      .append("circle")
      .attr("cy", NODE_H / 2 + 14)
      .attr("r", EXPAND_R)
      .attr("fill", COLORS.expandBtn)
      .attr("stroke", "white")
      .attr("stroke-width", 1.5)
      .style("cursor", "pointer")
      .on("mouseenter", function () {
        d3.select(this).attr("fill", COLORS.expandBtnHover);
      })
      .on("mouseleave", function () {
        d3.select(this).attr("fill", COLORS.expandBtn);
      })
      .on("click", (_event, d) => {
        _event.stopPropagation();
        expandNode(d.data.id);
      });

    // Downward chevron (▼ shape via path)
    expandableDown
      .append("path")
      .attr("d", `M-4,${NODE_H / 2 + 11}L0,${NODE_H / 2 + 17}L4,${NODE_H / 2 + 11}`)
      .attr("fill", "none")
      .attr("stroke", "white")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .style("pointer-events", "none");

    // -----------------------------------------------------------------------
    // Hover: show edge labels
    // -----------------------------------------------------------------------
    nodeGroups
      .on("mouseenter", function (_event, d) {
        edgeLabelGroup.selectAll("text").attr("opacity", function () {
          const el = d3.select(this);
          return el.attr("data-source") === d.id || el.attr("data-target") === d.id ? 1 : 0;
        });
        d3.select(this).select("rect").attr("stroke-width", 2.5);
      })
      .on("mouseleave", function (_event, d) {
        edgeLabelGroup.selectAll("text").attr("opacity", 0);
        d3.select(this)
          .select("rect")
          .attr("stroke-width", d.data.id === person.id ? 2.5 : 1);
      });
  }, [graph, containerWidth, person.id, expandNode]);

  return (
    <div className="w-full space-y-2">
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm border"
            style={{ borderColor: COLORS.family }}
          />
          <svg width="20" height="2">
            <line x1="0" y1="1" x2="20" y2="1" stroke={COLORS.edge} strokeWidth="1.5" />
          </svg>
          Family
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm border"
            style={{ borderColor: COLORS.spouse }}
          />
          <svg width="20" height="6">
            <line x1="0" y1="1" x2="20" y2="1" stroke={COLORS.edgeSpouse} strokeWidth="1" />
            <line x1="0" y1="4" x2="20" y2="4" stroke={COLORS.edgeSpouse} strokeWidth="1" />
          </svg>
          Marriage
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-full flex items-center justify-center"
            style={{ backgroundColor: COLORS.expandBtnUp }}
          >
            <ChevronUp className="w-2.5 h-2.5 text-white" />
          </span>
          Expand ancestors
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-full flex items-center justify-center"
            style={{ backgroundColor: COLORS.expandBtn }}
          >
            <ChevronDown className="w-2.5 h-2.5 text-white" />
          </span>
          Expand descendants
        </span>
      </div>

      {/* Navigable node list (for accessibility) */}
      <div className="sr-only">
        {[...graph.nodes.values()]
          .filter((n) => n.id !== person.id && n.hasPersonId)
          .map((n) => (
            <Link key={n.id} to="/persons/$personId" params={{ personId: n.id }}>
              {n.name} ({n.relationType})
            </Link>
          ))}
      </div>

      {/* Tree SVG */}
      <div
        ref={containerRef}
        className="relative overflow-auto rounded-lg border border-ink/10 bg-white/50"
        style={{ maxHeight: 500 }}
      >
        <svg ref={svgRef} width={containerWidth} height={400} className="block" />
      </div>
    </div>
  );
}
