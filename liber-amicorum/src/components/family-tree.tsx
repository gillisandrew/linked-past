import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  ReactFlow,
  Handle,
  Position,
  BaseEdge,
  getBezierPath,
  ReactFlowProvider,
  useReactFlow,
  type Node as RFNode,
  type Edge as RFEdge,
  type NodeProps,
  type EdgeProps,
  type NodeTypes,
  type EdgeTypes,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
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

/** Format relationship as "son of Name" → leads with the relationship */
function formatRelLabel(relationType: string, relatedName: string): string {
  const t = relationType.toLowerCase();
  // Invert the direction label so it reads naturally from the node's perspective
  // e.g., on a child node, "father of" means this person IS the father → show "father"
  // on a parent node, "son of" means the root is son of this person → show "parent"
  return `${t} ${relatedName}`;
}

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const COLORS = {
  root: "#6b7c6e",
  family: "#a0785a",
  spouse: "#b07080",
  edge: "rgba(37, 36, 54, 0.35)",
  edgeSpouse: "rgba(159, 90, 90, 0.5)",
  genBandEven: "rgba(37, 36, 54, 0.03)",
  genBandOdd: "rgba(37, 36, 54, 0.07)",
};

// ---------------------------------------------------------------------------
// Family node type
// ---------------------------------------------------------------------------

interface FamilyNode {
  id: string;
  name: string;
  generation: number;
  relationType: string;
  /** Name of the person this relationship is relative to */
  relatedToName: string;
  direction: RelDirection;
  uncertain: boolean;
  expanded: boolean;
  loading: boolean;
  hasPersonId: boolean;
  parentNodeId: string | null;
  spouses: { id: string; name: string; type: string; hasPersonId: boolean }[];
}

interface FamilyGraph {
  nodes: Map<string, FamilyNode>;
  rootId: string;
  rootName: string;
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
    relatedToName: "",
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
        relatedToName: person.name,
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
        relatedToName: person.name,
        direction: "descendant",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: person.id,
        spouses: [],
      });
    }
  }

  return { nodes, rootId: person.id, rootName: person.name };
}

// ---------------------------------------------------------------------------
// Graph manipulation helpers
// ---------------------------------------------------------------------------

function cloneGraph(graph: FamilyGraph): FamilyGraph {
  const nodes = new Map<string, FamilyNode>();
  for (const [id, node] of graph.nodes) {
    nodes.set(id, { ...node, spouses: [...node.spouses] });
  }
  return { nodes, rootId: graph.rootId, rootName: graph.rootName };
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
      clone.nodes.set(id, {
        id,
        name,
        generation: node.generation - 1,
        relationType: rel.type,
        relatedToName: node.name,
        direction: "ancestor",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: nodeId,
        spouses: [],
      });
    } else if (dir === "descendant" && node.direction === "descendant") {
      clone.nodes.set(id, {
        id,
        name,
        generation: node.generation + 1,
        relationType: rel.type,
        relatedToName: node.name,
        direction: "descendant",
        uncertain: false,
        expanded: false,
        loading: false,
        hasPersonId: hasId,
        parentNodeId: nodeId,
        spouses: [],
      });
    }
  }

  return clone;
}

// ---------------------------------------------------------------------------
// React Flow data types
// ---------------------------------------------------------------------------

interface PersonNodeData extends Record<string, unknown> {
  name: string;
  relLabel: string;
  direction: RelDirection;
  generation: number;
  isRoot: boolean;
  expanded: boolean;
  loading: boolean;
  hasPersonId: boolean;
  canExpandUp: boolean;
  canExpandDown: boolean;
  onExpand: (nodeId: string) => void;
}

type PersonNode = RFNode<PersonNodeData, "person">;

interface RelEdgeData extends Record<string, unknown> {
  relationType: string;
  isSpouse: boolean;
  isDivorced: boolean;
}

type RelEdge = RFEdge<RelEdgeData, "relationship">;

// ---------------------------------------------------------------------------
// Generation label helper
// ---------------------------------------------------------------------------

function generationLabel(gen: number): string {
  if (gen === 0) return "";
  if (gen === -1) return "Parents";
  if (gen === -2) return "Grandparents";
  if (gen < -2) return `${Math.abs(gen)}× Great-grandparents`;
  if (gen === 1) return "Children";
  if (gen === 2) return "Grandchildren";
  return `${gen - 1}× Great-grandchildren`;
}

// ---------------------------------------------------------------------------
// Custom Person Node
// ---------------------------------------------------------------------------

function PersonNodeComponent({ data, id }: NodeProps<PersonNode>) {
  const borderColor = data.isRoot
    ? COLORS.root
    : data.direction === "spouse"
      ? COLORS.spouse
      : COLORS.family;

  return (
    <div className="relative">
      {/* Top handle — for connections coming from above */}
      <Handle type="target" position={Position.Top} className="!bg-ink/30 !w-2 !h-2" />

      {/* Expand ancestors button */}
      {data.canExpandUp && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onExpand(id);
          }}
          className="absolute -top-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-white z-10"
          style={{ backgroundColor: COLORS.root }}
          title="Expand ancestors"
        >
          <ChevronUp className="w-3 h-3" />
        </button>
      )}

      {/* Node body */}
      <div
        className="rounded-md px-3 py-1.5 text-center bg-white min-w-[160px] max-w-[200px]"
        style={{ border: `${data.isRoot ? 2.5 : 1}px solid ${borderColor}` }}
      >
        {/* Relationship label first — "son of Marcus" */}
        {!data.isRoot && data.relLabel && (
          <p className="text-[9px] uppercase tracking-wide text-ink-muted mb-0.5">{data.relLabel}</p>
        )}
        {/* Person name */}
        <p className="text-[11px] font-medium text-ink truncate">{data.name}</p>
        {/* Generation indicator */}
        {data.isRoot && (
          <p className="text-[8px] text-ink-muted mt-0.5">root</p>
        )}
        {data.loading && <p className="text-[10px] text-ink-muted animate-pulse mt-0.5">loading...</p>}
      </div>

      {/* Expand descendants button */}
      {data.canExpandDown && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onExpand(id);
          }}
          className="absolute -bottom-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-white z-10"
          style={{ backgroundColor: COLORS.family }}
          title="Expand descendants"
        >
          <ChevronDown className="w-3 h-3" />
        </button>
      )}

      {/* Bottom handle — for connections going down */}
      <Handle type="source" position={Position.Bottom} className="!bg-ink/30 !w-2 !h-2" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom Relationship Edge
// ---------------------------------------------------------------------------

function RelationshipEdge(props: EdgeProps<RelEdge>) {
  const { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition, data } = props;
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isSpouse = data?.isSpouse ?? false;
  const isDivorced = data?.isDivorced ?? false;

  return (
    <BaseEdge
      path={path}
      labelX={labelX}
      labelY={labelY}
      style={{
        stroke: isSpouse ? COLORS.edgeSpouse : COLORS.edge,
        strokeDasharray: isDivorced ? "4,3" : isSpouse ? "2,0" : undefined,
        strokeWidth: isSpouse ? 1 : 1.5,
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Type registrations
// ---------------------------------------------------------------------------

const nodeTypes: NodeTypes = { person: PersonNodeComponent };
const edgeTypes: EdgeTypes = { relationship: RelationshipEdge };

// ---------------------------------------------------------------------------
// Dagre layout
// ---------------------------------------------------------------------------

const NODE_W = 180;
const NODE_H = 55;

function layoutTree(
  nodes: PersonNode[],
  edges: RelEdge[],
): { nodes: PersonNode[]; edges: RelEdge[] } {
  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 90, nodesep: 40 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_W, height: NODE_H });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
    };
  });

  return { nodes: layoutedNodes, edges };
}

// ---------------------------------------------------------------------------
// Convert FamilyGraph → React Flow nodes/edges
// All edges flow top→bottom (source=parent, target=child)
// ---------------------------------------------------------------------------

function graphToReactFlow(
  graph: FamilyGraph,
  onExpand: (nodeId: string) => void,
): { nodes: PersonNode[]; edges: RelEdge[] } {
  const rfNodes: PersonNode[] = [];
  const rfEdges: RelEdge[] = [];

  // Collect all node IDs including spouses
  const allNodeIds = new Set<string>();
  for (const node of graph.nodes.values()) {
    allNodeIds.add(node.id);
    for (const sp of node.spouses) allNodeIds.add(sp.id);
  }

  // Add main nodes
  for (const node of graph.nodes.values()) {
    const isRoot = node.id === graph.rootId;
    const isAncestor = node.direction === "ancestor";
    const isDescendant = node.direction === "descendant";

    rfNodes.push({
      id: node.id,
      type: "person",
      position: { x: 0, y: 0 },
      data: {
        name: node.name,
        relLabel: isRoot ? "" : formatRelLabel(node.relationType, node.relatedToName),
        direction: node.direction,
        generation: node.generation,
        isRoot,
        expanded: node.expanded,
        loading: node.loading,
        hasPersonId: node.hasPersonId,
        canExpandUp: isAncestor && !node.expanded && !node.loading && node.hasPersonId,
        canExpandDown: isDescendant && !isRoot && !node.expanded && !node.loading && node.hasPersonId,
        onExpand,
      },
    });

    // Add spouse nodes
    for (const sp of node.spouses) {
      if (!graph.nodes.has(sp.id)) {
        rfNodes.push({
          id: sp.id,
          type: "person",
          position: { x: 0, y: 0 },
          data: {
            name: sp.name,
            relLabel: sp.type,
            direction: "spouse",
            generation: node.generation,
            isRoot: false,
            expanded: false,
            loading: false,
            hasPersonId: sp.hasPersonId,
            canExpandUp: false,
            canExpandDown: false,
            onExpand,
          },
        });
      }
    }
  }

  // Add edges — ALWAYS source=parent (above), target=child (below)
  for (const node of graph.nodes.values()) {
    if (node.parentNodeId && allNodeIds.has(node.parentNodeId)) {
      if (node.direction === "ancestor") {
        // This node is an ancestor (above). parentNodeId is the child (below).
        // Edge: source=this ancestor, target=parentNodeId (child)
        rfEdges.push({
          id: `e-${node.id}-${node.parentNodeId}`,
          source: node.id,
          target: node.parentNodeId,
          type: "relationship",
          data: { relationType: node.relationType, isSpouse: false, isDivorced: false },
        });
      } else {
        // This node is a descendant (below). parentNodeId is the parent (above).
        // Edge: source=parentNodeId (parent), target=this descendant
        rfEdges.push({
          id: `e-${node.parentNodeId}-${node.id}`,
          source: node.parentNodeId,
          target: node.id,
          type: "relationship",
          data: { relationType: node.relationType, isSpouse: false, isDivorced: false },
        });
      }
    }

    // Spouse edges
    for (const sp of node.spouses) {
      rfEdges.push({
        id: `e-spouse-${node.id}-${sp.id}`,
        source: node.id,
        target: sp.id,
        type: "relationship",
        data: { relationType: sp.type, isSpouse: true, isDivorced: sp.type === "divorced from" },
      });
    }
  }

  // Deduplicate nodes
  const seen = new Set<string>();
  const uniqueNodes = rfNodes.filter((n) => {
    if (seen.has(n.id)) return false;
    seen.add(n.id);
    return true;
  });

  return layoutTree(uniqueNodes, rfEdges);
}

// ---------------------------------------------------------------------------
// Generation background bands (rendered behind the React Flow canvas)
// ---------------------------------------------------------------------------

function GenerationBands({ nodes }: { nodes: PersonNode[] }) {
  if (nodes.length === 0) return null;

  // Group nodes by generation and find Y bounds per generation
  const genBounds = new Map<number, { minY: number; maxY: number }>();
  for (const node of nodes) {
    const gen = node.data.generation;
    const y = node.position.y;
    const existing = genBounds.get(gen);
    if (existing) {
      existing.minY = Math.min(existing.minY, y);
      existing.maxY = Math.max(existing.maxY, y + NODE_H);
    } else {
      genBounds.set(gen, { minY: y, maxY: y + NODE_H });
    }
  }

  const bands = Array.from(genBounds.entries()).sort((a, b) => a[0] - b[0]);

  return (
    <svg className="pointer-events-none absolute inset-0 w-full h-full overflow-visible">
      {bands.map(([gen, bounds]) => {
        const padding = 20;
        const label = generationLabel(gen);
        const isEven = Math.abs(gen) % 2 === 0;
        return (
          <g key={gen}>
            <rect
              x={-5000}
              y={bounds.minY - padding}
              width={10000}
              height={bounds.maxY - bounds.minY + padding * 2}
              fill={isEven ? COLORS.genBandEven : COLORS.genBandOdd}
            />
            {label && (
              <text
                x={-4980}
                y={bounds.minY - padding + 14}
                className="text-[10px]"
                fill="rgba(37, 36, 54, 0.3)"
                fontStyle="italic"
              >
                {label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Inner component
// ---------------------------------------------------------------------------

function FamilyTreeInner({ person }: { person: Person }) {
  const [graph, setGraph] = useState<FamilyGraph>(() => buildInitialGraph(person));
  const { fitView } = useReactFlow();
  const navigate = useNavigate();

  useEffect(() => {
    setGraph(buildInitialGraph(person));
  }, [person]);

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

  const { nodes, edges } = useMemo(() => graphToReactFlow(graph, expandNode), [graph, expandNode]);

  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50);
    return () => clearTimeout(t);
  }, [nodes, edges, fitView]);

  return (
    <div className="w-full space-y-2">
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm border" style={{ borderColor: COLORS.family }} />
          Family
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm border" style={{ borderColor: COLORS.spouse }} />
          Marriage
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full flex items-center justify-center" style={{ backgroundColor: COLORS.root }}>
            <ChevronUp className="w-2.5 h-2.5 text-white" />
          </span>
          Expand ancestors
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full flex items-center justify-center" style={{ backgroundColor: COLORS.family }}>
            <ChevronDown className="w-2.5 h-2.5 text-white" />
          </span>
          Expand descendants
        </span>
        <span className="text-[10px] italic">Double-click a node to navigate</span>
      </div>

      {/* Tree */}
      <div className="rounded-lg border border-ink/10 bg-white/50 relative" style={{ height: 500 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.2}
          maxZoom={3}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          onNodeDoubleClick={(_event, node) => {
            if (node.id !== person.id && node.data.hasPersonId) {
              navigate({ to: "/persons/$personId", params: { personId: node.id } });
            }
          }}
        >
          <GenerationBands nodes={nodes} />
        </ReactFlow>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported component
// ---------------------------------------------------------------------------

interface FamilyTreeProps {
  person: Person;
}

export function FamilyTree({ person }: FamilyTreeProps) {
  return (
    <ReactFlowProvider>
      <FamilyTreeInner person={person} />
    </ReactFlowProvider>
  );
}
