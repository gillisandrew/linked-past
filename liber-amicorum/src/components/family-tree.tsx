import * as d3 from "d3";
import { useRef, useEffect, useState, useCallback } from "react";
import { Link } from "@tanstack/react-router";
import { getPersonById } from "#/lib/data";
import type { Person } from "#/lib/types";

// ---------------------------------------------------------------------------
// Relationship classification
// ---------------------------------------------------------------------------

type RelCategory = "parent" | "child" | "spouse" | "other";

const SPOUSE_TYPES = new Set(["married to", "divorced from"]);

// Types that imply "this person is above me in the tree" (I am their child)
const ANCESTOR_TYPES = new Set([
  "son of",
  "daughter of",
  "grandson of",
  "granddaughter of",
  "great-grandson of",
]);

// Types that imply "this person is below me in the tree" (I am their parent)
const DESCENDANT_TYPES = new Set([
  "father of",
  "mother of",
  "grandfather of",
  "grandmother of",
  "great-grandfather of",
]);

function classifyForTree(type: string): RelCategory {
  const t = type.toLowerCase();
  if (ANCESTOR_TYPES.has(t)) return "parent";
  if (DESCENDANT_TYPES.has(t)) return "child";
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
  loadingSpinner: "#a0785a",
};

// ---------------------------------------------------------------------------
// Tree node type
// ---------------------------------------------------------------------------

interface TreeNode {
  id: string;
  name: string;
  relationship: string;
  category: RelCategory;
  uncertain: boolean;
  children: TreeNode[];
  spouses: { id: string; name: string; type: string; uncertain: boolean }[];
  expanded: boolean;
  loading: boolean;
  hasRelatedPersonId: boolean; // can we navigate / expand?
}

// ---------------------------------------------------------------------------
// Build initial tree from person data
// ---------------------------------------------------------------------------

function buildInitialTree(person: Person): TreeNode {
  const parents: TreeNode[] = [];
  const children: TreeNode[] = [];
  const others: TreeNode[] = [];
  const spouses: TreeNode["spouses"] = [];

  for (const rel of person.relationships) {
    const cat = classifyForTree(rel.type);
    const id = rel.relatedPersonId ?? `unknown-${rel.type}-${rel.relatedPersonName}`;
    const name = rel.relatedPersonName ?? "Unknown";
    const hasId = rel.relatedPersonId != null;

    if (cat === "spouse") {
      spouses.push({ id, name, type: rel.type, uncertain: false });
    } else {
      const node: TreeNode = {
        id,
        name,
        relationship: rel.type,
        category: cat,
        uncertain: false,
        children: [],
        spouses: [],
        expanded: false,
        loading: false,
        hasRelatedPersonId: hasId,
      };
      if (cat === "parent") parents.push(node);
      else if (cat === "child") children.push(node);
      else others.push(node);
    }
  }

  // Root node: current person
  // Tree structure: parents are "above" (we invert by making root the center)
  // We build: parents -> [ROOT] -> children + others
  const root: TreeNode = {
    id: person.id,
    name: person.name,
    relationship: "",
    category: "parent", // unused for root
    uncertain: false,
    children: [...children, ...others],
    spouses,
    expanded: true,
    loading: false,
    hasRelatedPersonId: true,
  };

  // If there are parents, we need to restructure:
  // grandparent -> parent -> ROOT -> children
  // But since we only have one level initially, just make parents children too
  // but displayed above. We'll use a "generation" concept in layout.
  // For D3 tree, we need a single root. Strategy: virtual root with parents and
  // the person node as children, then person node has its children.
  // Actually, simpler: treat the person as root. Parents go "up" (we'll render
  // the tree top-down with parents above). We'll use a wrapper node.

  if (parents.length > 0) {
    // Create a virtual structure: each parent is above root
    // For display, we'll handle this by making the tree root a virtual node
    // with parents as one branch and the person + children as another.
    // But D3 tree wants a single root. Let's just put parents as children
    // of root with a special marker, and in rendering flip them above.
    // Actually, let's keep it simple: treat everything as children of root
    // and use the category to position them. Parents will be rendered above.
    root.children = [...parents, ...children, ...others];
  }

  return root;
}

// ---------------------------------------------------------------------------
// Tree manipulation helpers
// ---------------------------------------------------------------------------

function findNode(tree: TreeNode, id: string): TreeNode | null {
  if (tree.id === id) return tree;
  for (const child of tree.children) {
    const found = findNode(child, id);
    if (found) return found;
  }
  return null;
}

function cloneTree(tree: TreeNode): TreeNode {
  return {
    ...tree,
    children: tree.children.map(cloneTree),
    spouses: [...tree.spouses],
  };
}

function markLoading(tree: TreeNode, nodeId: string): TreeNode {
  const clone = cloneTree(tree);
  const node = findNode(clone, nodeId);
  if (node) node.loading = true;
  return clone;
}

function expandTreeNode(tree: TreeNode, nodeId: string, personData: Person): TreeNode {
  const clone = cloneTree(tree);
  const node = findNode(clone, nodeId);
  if (!node) return clone;

  node.loading = false;
  node.expanded = true;

  // Collect IDs already in the tree to avoid duplicates
  const existingIds = new Set<string>();
  function collectIds(n: TreeNode) {
    existingIds.add(n.id);
    n.children.forEach(collectIds);
    n.spouses.forEach((s) => existingIds.add(s.id));
  }
  collectIds(clone);

  for (const rel of personData.relationships) {
    const cat = classifyForTree(rel.type);
    const id = rel.relatedPersonId ?? `unknown-${rel.type}-${rel.relatedPersonName}`;
    const name = rel.relatedPersonName ?? "Unknown";
    const hasId = rel.relatedPersonId != null;

    if (existingIds.has(id)) continue;
    existingIds.add(id);

    if (cat === "spouse") {
      node.spouses.push({ id, name, type: rel.type, uncertain: false });
    } else {
      node.children.push({
        id,
        name,
        relationship: rel.type,
        category: cat,
        uncertain: false,
        children: [],
        spouses: [],
        expanded: false,
        loading: false,
        hasRelatedPersonId: hasId,
      });
    }
  }

  return clone;
}

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const NODE_W = 140;
const NODE_H = 36;
const NODE_RX = 6;
const EXPAND_R = 9;
const VERTICAL_GAP = 70;
const HORIZONTAL_GAP = 20;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface FamilyTreeProps {
  person: Person;
}

export function FamilyTree({ person }: FamilyTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tree, setTree] = useState<TreeNode>(() => buildInitialTree(person));
  const [containerWidth, setContainerWidth] = useState(800);

  // Reset tree when person changes
  useEffect(() => {
    setTree(buildInitialTree(person));
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
    setTree((prev) => markLoading(prev, nodeId));
    const personData = await getPersonById(nodeId);
    if (!personData) {
      // If load fails, just mark as expanded with no children
      setTree((prev) => {
        const clone = cloneTree(prev);
        const node = findNode(clone, nodeId);
        if (node) {
          node.loading = false;
          node.expanded = true;
        }
        return clone;
      });
      return;
    }
    setTree((prev) => expandTreeNode(prev, nodeId, personData));
  }, []);

  // D3 rendering
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Convert our tree to d3 hierarchy
    const hierarchy = d3.hierarchy(tree, (d) => (d.children.length > 0 ? d.children : null));

    // Layout
    const treeLayout = d3
      .tree<TreeNode>()
      .nodeSize([NODE_W + HORIZONTAL_GAP, NODE_H + VERTICAL_GAP])
      .separation(() => 1);

    const root = treeLayout(hierarchy);

    // Compute bounds
    const nodes = root.descendants();
    const links = root.links();

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;
    for (const n of nodes) {
      if (n.x - NODE_W / 2 < minX) minX = n.x - NODE_W / 2;
      if (n.x + NODE_W / 2 > maxX) maxX = n.x + NODE_W / 2;
      if (n.y - NODE_H / 2 < minY) minY = n.y - NODE_H / 2;
      if (n.y + NODE_H / 2 > maxY) maxY = n.y + NODE_H / 2;
    }

    // Add padding for spouse labels and expand buttons
    const pad = 40;
    const treeW = maxX - minX + pad * 2;
    const treeH = maxY - minY + pad * 2;

    const svgW = Math.max(containerWidth, treeW);
    const svgH = Math.max(300, treeH);

    svg.attr("width", svgW).attr("height", svgH);

    // Center the tree
    const offsetX = svgW / 2 - (minX + maxX) / 2;
    const offsetY = pad - minY;

    const g = svg.append("g").attr("transform", `translate(${offsetX},${offsetY})`);

    // Add zoom
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);
    // Set initial transform
    svg.call(zoom.transform, d3.zoomIdentity.translate(offsetX, offsetY));

    // ---------------------------------------------------------------------------
    // Draw links (edges)
    // ---------------------------------------------------------------------------
    g.append("g")
      .selectAll("path")
      .data(links)
      .join("path")
      .attr("d", (d) => {
        const sx = d.source.x;
        const sy = d.source.y + NODE_H / 2;
        const tx = d.target.x;
        const ty = d.target.y - NODE_H / 2;
        const my = (sy + ty) / 2;
        return `M${sx},${sy} C${sx},${my} ${tx},${my} ${tx},${ty}`;
      })
      .attr("fill", "none")
      .attr("stroke", (d) => {
        const cat = d.target.data.category;
        if (cat === "other") return COLORS.edgeOther;
        return COLORS.edge;
      })
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", (d) => {
        if (d.target.data.uncertain) return "5,3";
        if (d.target.data.category === "other") return "3,3";
        return "";
      });

    // Edge labels on hover
    const edgeLabels = g
      .append("g")
      .selectAll("text")
      .data(links)
      .join("text")
      .attr("x", (d) => (d.source.x + d.target.x) / 2)
      .attr("y", (d) => (d.source.y + d.target.y) / 2)
      .attr("text-anchor", "middle")
      .attr("font-size", 9)
      .attr("fill", COLORS.textMuted)
      .attr("opacity", 0)
      .text((d) => d.target.data.relationship);

    // ---------------------------------------------------------------------------
    // Draw spouse connections
    // ---------------------------------------------------------------------------
    for (const node of nodes) {
      const d = node.data;
      if (d.spouses.length === 0) continue;

      const baseX = node.x + NODE_W / 2 + 4;
      const baseY = node.y;

      d.spouses.forEach((spouse, i) => {
        const spouseX = baseX + 10;
        const spouseY = baseY - (d.spouses.length - 1) * 10 + i * 20;

        // Double line for marriage
        g.append("line")
          .attr("x1", node.x + NODE_W / 2)
          .attr("y1", node.y)
          .attr("x2", spouseX)
          .attr("y2", spouseY)
          .attr("stroke", COLORS.edgeSpouse)
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", spouse.type === "divorced from" ? "3,3" : "");
        g.append("line")
          .attr("x1", node.x + NODE_W / 2)
          .attr("y1", node.y + 3)
          .attr("x2", spouseX)
          .attr("y2", spouseY + 3)
          .attr("stroke", COLORS.edgeSpouse)
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", spouse.type === "divorced from" ? "3,3" : "");

        // Spouse label
        const spouseGroup = g.append("g").attr("transform", `translate(${spouseX},${spouseY})`);

        const isNavigable = !spouse.id.startsWith("unknown-");

        spouseGroup
          .append("rect")
          .attr("x", 0)
          .attr("y", -NODE_H / 2 + 4)
          .attr("width", NODE_W - 20)
          .attr("height", NODE_H - 8)
          .attr("rx", NODE_RX)
          .attr("fill", "white")
          .attr("stroke", COLORS.spouse)
          .attr("stroke-width", 1)
          .style("cursor", isNavigable ? "pointer" : "default");

        spouseGroup
          .append("text")
          .attr("x", (NODE_W - 20) / 2)
          .attr("y", 4)
          .attr("text-anchor", "middle")
          .attr("font-size", 10)
          .attr("fill", COLORS.text)
          .style("cursor", isNavigable ? "pointer" : "default")
          .text(spouse.name.length > 18 ? spouse.name.slice(0, 16) + "..." : spouse.name);

        // Spouse type label
        spouseGroup
          .append("text")
          .attr("x", (NODE_W - 20) / 2)
          .attr("y", -NODE_H / 2 + 1)
          .attr("text-anchor", "middle")
          .attr("font-size", 8)
          .attr("fill", COLORS.textMuted)
          .text(spouse.type);
      });
    }

    // ---------------------------------------------------------------------------
    // Draw nodes
    // ---------------------------------------------------------------------------
    const nodeGroups = g
      .append("g")
      .selectAll<SVGGElement, d3.HierarchyPointNode<TreeNode>>("g")
      .data(nodes)
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
        if (d.data.category === "spouse") return COLORS.spouse;
        if (d.data.category === "other") return COLORS.other;
        return COLORS.family;
      })
      .attr("stroke-width", (d) => (d.data.id === person.id ? 2 : 1));

    // Node names
    nodeGroups
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 1)
      .attr("font-size", (d) => (d.data.id === person.id ? 12 : 11))
      .attr("font-weight", (d) => (d.data.id === person.id ? "600" : "400"))
      .attr("fill", COLORS.text)
      .text((d) => {
        const name = d.data.name;
        return name.length > 18 ? name.slice(0, 16) + "..." : name;
      });

    // Relationship label below name (for non-root)
    nodeGroups
      .filter((d) => d.data.id !== person.id && d.data.relationship !== "")
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 12)
      .attr("font-size", 8)
      .attr("fill", COLORS.textMuted)
      .text((d) => d.data.relationship);

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

    // Loading spinner (simple rotating circle)
    nodeGroups
      .filter((d) => d.data.loading)
      .append("circle")
      .attr("cx", 0)
      .attr("cy", NODE_H / 2 + 12)
      .attr("r", 4)
      .attr("fill", "none")
      .attr("stroke", COLORS.loadingSpinner)
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "6,6")
      .attr("class", "animate-spin-slow");

    // Expand button (+) for non-expanded nodes with a person ID
    const expandable = nodeGroups.filter(
      (d) => !d.data.expanded && !d.data.loading && d.data.hasRelatedPersonId,
    );

    expandable
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

    expandable
      .append("text")
      .attr("y", NODE_H / 2 + 14)
      .attr("text-anchor", "middle")
      .attr("dy", 4)
      .attr("font-size", 13)
      .attr("font-weight", "bold")
      .attr("fill", "white")
      .style("cursor", "pointer")
      .style("pointer-events", "none")
      .text("+");

    // ---------------------------------------------------------------------------
    // Hover: show edge label
    // ---------------------------------------------------------------------------
    nodeGroups
      .on("mouseenter", function (_event, d) {
        // Show edge labels for edges connected to this node
        edgeLabels.attr("opacity", (link) => (link.source === d || link.target === d ? 1 : 0));
        // Highlight stroke
        d3.select(this).select("rect").attr("stroke-width", 2.5);
      })
      .on("mouseleave", function (_event, d) {
        edgeLabels.attr("opacity", 0);
        d3.select(this)
          .select("rect")
          .attr("stroke-width", d.data.id === person.id ? 2 : 1);
      });
  }, [tree, containerWidth, person.id, expandNode]);

  // Count total nodes for height estimation
  function countNodes(n: TreeNode): number {
    let c = 1;
    for (const child of n.children) c += countNodes(child);
    return c;
  }
  const totalNodes = countNodes(tree);
  const estimatedHeight = Math.max(300, Math.min(600, totalNodes * 40 + 100));

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
            className="inline-block w-2.5 h-2.5 rounded-sm border"
            style={{ borderColor: COLORS.other }}
          />
          <svg width="20" height="2">
            <line
              x1="0"
              y1="1"
              x2="20"
              y2="1"
              stroke={COLORS.edgeOther}
              strokeWidth="1.5"
              strokeDasharray="3,3"
            />
          </svg>
          Other
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-3.5 h-3.5 rounded-full text-center leading-[14px] text-[9px] font-bold"
            style={{ backgroundColor: COLORS.expandBtn, color: "white" }}
          >
            +
          </span>
          Click to expand
        </span>
      </div>

      {/* Navigable node list (for accessibility) */}
      <div className="sr-only">
        {tree.children.map((child) => (
          <Link key={child.id} to="/persons/$personId" params={{ personId: child.id }}>
            {child.name} ({child.relationship})
          </Link>
        ))}
      </div>

      {/* Tree SVG */}
      <div
        ref={containerRef}
        className="relative overflow-auto rounded-lg border border-ink/10 bg-white/50"
        style={{ maxHeight: 500 }}
      >
        <svg ref={svgRef} width={containerWidth} height={estimatedHeight} className="block" />
      </div>
    </div>
  );
}
