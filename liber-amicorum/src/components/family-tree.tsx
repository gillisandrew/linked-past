import { useState, useEffect, useCallback, useMemo, createContext, useContext } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  ReactFlow,
  Handle,
  Position,
  BaseEdge,
  getSmoothStepPath,
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
  "son of", "daughter of", "adopted son of", "adopted daughter of",
  "grandson of", "granddaughter of", "great-grandson of",
]);
const DESCENDANT_TYPES = new Set([
  "father of", "mother of", "grandfather of", "grandmother of", "great-grandfather of",
]);

function classifyRelationship(type: string): RelDirection {
  const t = type.toLowerCase();
  if (ANCESTOR_TYPES.has(t)) return "ancestor";
  if (DESCENDANT_TYPES.has(t)) return "descendant";
  if (SPOUSE_TYPES.has(t)) return "spouse";
  return "other";
}

function formatRelLabel(relationType: string, relatedName: string | null | undefined): string {
  if (!relationType) return "";
  const t = relationType.toLowerCase();
  if (!relatedName) return t;
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
};

// ---------------------------------------------------------------------------
// Context for expand callback (so custom nodes can trigger expansion)
// ---------------------------------------------------------------------------

const ExpandContext = createContext<(nodeId: string) => void>(() => {});

// ---------------------------------------------------------------------------
// Family graph data
// ---------------------------------------------------------------------------

interface FamilyNode {
  id: string;
  name: string;
  generation: number;
  relationType: string;
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
// Build / clone / expand graph
// ---------------------------------------------------------------------------

function buildInitialGraph(person: Person): FamilyGraph {
  const nodes = new Map<string, FamilyNode>();
  const rootNode: FamilyNode = {
    id: person.id, name: person.name, generation: 0,
    relationType: "", relatedToName: "",
    direction: "descendant", uncertain: false, expanded: true,
    loading: false, hasPersonId: true, parentNodeId: null, spouses: [],
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
        id, name, generation: -1, relationType: rel.type,
        relatedToName: person.name ?? "", direction: "ancestor",
        uncertain: false, expanded: false, loading: false,
        hasPersonId: hasId, parentNodeId: person.id, spouses: [],
      });
    } else if (dir === "descendant") {
      nodes.set(id, {
        id, name, generation: 1, relationType: rel.type,
        relatedToName: person.name ?? "", direction: "descendant",
        uncertain: false, expanded: false, loading: false,
        hasPersonId: hasId, parentNodeId: person.id, spouses: [],
      });
    }
  }
  return { nodes, rootId: person.id, rootName: person.name };
}

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
        id, name, generation: node.generation - 1, relationType: rel.type,
        relatedToName: node.name ?? "", direction: "ancestor",
        uncertain: false, expanded: false, loading: false,
        hasPersonId: hasId, parentNodeId: nodeId, spouses: [],
      });
    } else if (dir === "descendant" && node.direction === "descendant") {
      clone.nodes.set(id, {
        id, name, generation: node.generation + 1, relationType: rel.type,
        relatedToName: node.name ?? "", direction: "descendant",
        uncertain: false, expanded: false, loading: false,
        hasPersonId: hasId, parentNodeId: nodeId, spouses: [],
      });
    }
  }
  return clone;
}

// ---------------------------------------------------------------------------
// React Flow node/edge data
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
  nodeId: string;
}

type PersonNode = RFNode<PersonNodeData, "person">;

interface GenBandData extends Record<string, unknown> {
  label: string;
  bandWidth: number;
  bandHeight: number;
  isEven: boolean;
}

type GenBandNode = RFNode<GenBandData, "genBand">;

interface RelEdgeData extends Record<string, unknown> {
  relationType: string;
  isSpouse: boolean;
  isDivorced: boolean;
}

type RelEdge = RFEdge<RelEdgeData, "relationship">;

// ---------------------------------------------------------------------------
// Generation label
// ---------------------------------------------------------------------------

function generationLabel(gen: number): string {
  if (gen === 0) return "Root";
  if (gen === -1) return "Parents";
  if (gen === -2) return "Grandparents";
  if (gen < -2) return `Great-grandparents`;
  if (gen === 1) return "Children";
  if (gen === 2) return "Grandchildren";
  return "Great-grandchildren";
}

// ---------------------------------------------------------------------------
// Custom Person Node — receives expand callback via context
// ---------------------------------------------------------------------------

function PersonNodeComponent({ data, id }: NodeProps<PersonNode>) {
  const borderColor = data.isRoot ? COLORS.root
    : data.direction === "spouse" ? COLORS.spouse
    : COLORS.family;

  const expandNode = useContext(ExpandContext);

  return (
    <div className="relative">
      <Handle type="target" position={Position.Top} className="!bg-ink/30 !w-2 !h-2" />

      {/* Expand ancestors button */}
      {data.canExpandUp && (
        <button
          className="nodrag absolute -top-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-white z-10 cursor-pointer hover:scale-110 transition-transform"
          style={{ backgroundColor: COLORS.root }}
          title="Expand ancestors"
          onClick={() => expandNode(id)}
        >
          <ChevronUp className="w-3 h-3" />
        </button>
      )}

      <div
        className="rounded-md px-3 py-1.5 text-center bg-white min-w-[160px] max-w-[200px]"
        style={{ border: `${data.isRoot ? 2.5 : 1}px solid ${borderColor}` }}
      >
        {!data.isRoot && data.relLabel && (
          <p className="text-[9px] uppercase tracking-wide text-ink-muted mb-0.5">{data.relLabel}</p>
        )}
        <p className="text-[11px] font-medium text-ink truncate">{data.name}</p>
        {data.isRoot && <p className="text-[8px] text-ink-muted mt-0.5">root</p>}
        {data.loading && <p className="text-[10px] text-ink-muted animate-pulse mt-0.5">loading...</p>}
      </div>

      {/* Expand descendants button */}
      {data.canExpandDown && (
        <button
          className="nodrag absolute -bottom-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-white z-10 cursor-pointer hover:scale-110 transition-transform"
          style={{ backgroundColor: COLORS.family }}
          title="Expand descendants"
          onClick={() => expandNode(id)}
        >
          <ChevronDown className="w-3 h-3" />
        </button>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-ink/30 !w-2 !h-2" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generation band node — background rectangle
// ---------------------------------------------------------------------------

function GenBandComponent({ data }: NodeProps<GenBandNode>) {
  return (
    <div
      className="pointer-events-none"
      style={{
        width: data.bandWidth,
        height: data.bandHeight,
        backgroundColor: data.isEven ? "rgba(37, 36, 54, 0.03)" : "rgba(37, 36, 54, 0.07)",
        borderRadius: 4,
      }}
    >
      {data.label && (
        <span className="absolute left-3 top-1 text-[10px] italic" style={{ color: "rgba(37, 36, 54, 0.3)" }}>
          {data.label}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom edge
// ---------------------------------------------------------------------------

function RelationshipEdge(props: EdgeProps<RelEdge>) {
  const { sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition, data } = props;
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition,
    borderRadius: 8,
  });
  const isSpouse = data?.isSpouse ?? false;
  const isDivorced = data?.isDivorced ?? false;

  return (
    <BaseEdge
      path={path} labelX={labelX} labelY={labelY}
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

const nodeTypes: NodeTypes = {
  person: PersonNodeComponent,
  genBand: GenBandComponent,
};
const edgeTypes: EdgeTypes = { relationship: RelationshipEdge };

// ---------------------------------------------------------------------------
// Dagre layout
// ---------------------------------------------------------------------------

const NODE_W = 180;
const NODE_H = 55;
const BAND_PADDING = 30;

function layoutTree(
  nodes: PersonNode[],
  edges: RelEdge[],
): { nodes: (PersonNode | GenBandNode)[]; edges: RelEdge[] } {
  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 90, nodesep: 40 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_W, height: NODE_H });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }
  dagre.layout(g);

  const layoutedNodes: PersonNode[] = nodes.map((node) => {
    const pos = g.node(node.id);
    return { ...node, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } };
  });

  // Build generation band nodes from layouted positions
  const genBounds = new Map<number, { minX: number; maxX: number; minY: number; maxY: number }>();
  for (const node of layoutedNodes) {
    const gen = node.data.generation;
    const x = node.position.x;
    const y = node.position.y;
    const existing = genBounds.get(gen);
    if (existing) {
      existing.minX = Math.min(existing.minX, x);
      existing.maxX = Math.max(existing.maxX, x + NODE_W);
      existing.minY = Math.min(existing.minY, y);
      existing.maxY = Math.max(existing.maxY, y + NODE_H);
    } else {
      genBounds.set(gen, { minX: x, maxX: x + NODE_W, minY: y, maxY: y + NODE_H });
    }
  }

  // Find global X bounds for band width
  let globalMinX = Infinity;
  let globalMaxX = -Infinity;
  for (const b of genBounds.values()) {
    globalMinX = Math.min(globalMinX, b.minX);
    globalMaxX = Math.max(globalMaxX, b.maxX);
  }
  const bandWidth = globalMaxX - globalMinX + BAND_PADDING * 4;

  const bandNodes: GenBandNode[] = [];
  for (const [gen, bounds] of genBounds) {
    const bandHeight = bounds.maxY - bounds.minY + BAND_PADDING * 2;
    bandNodes.push({
      id: `gen-band-${gen}`,
      type: "genBand",
      position: { x: globalMinX - BAND_PADDING * 2, y: bounds.minY - BAND_PADDING },
      draggable: false,
      selectable: false,
      data: {
        label: generationLabel(gen),
        bandWidth,
        bandHeight,
        isEven: Math.abs(gen) % 2 === 0,
      },
      style: { zIndex: -1 },
    });
  }

  return { nodes: [...bandNodes, ...layoutedNodes], edges };
}

// ---------------------------------------------------------------------------
// Convert FamilyGraph → React Flow
// ---------------------------------------------------------------------------

function graphToReactFlow(
  graph: FamilyGraph,
): { nodes: (PersonNode | GenBandNode)[]; edges: RelEdge[] } {
  const rfNodes: PersonNode[] = [];
  const rfEdges: RelEdge[] = [];

  const allNodeIds = new Set<string>();
  for (const node of graph.nodes.values()) {
    allNodeIds.add(node.id);
    for (const sp of node.spouses) allNodeIds.add(sp.id);
  }

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
        nodeId: node.id,
      },
    });

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
            nodeId: sp.id,
          },
        });
      }
    }
  }

  for (const node of graph.nodes.values()) {
    if (node.parentNodeId && allNodeIds.has(node.parentNodeId)) {
      if (node.direction === "ancestor") {
        rfEdges.push({
          id: `e-${node.id}-${node.parentNodeId}`,
          source: node.id, target: node.parentNodeId,
          type: "relationship",
          data: { relationType: node.relationType, isSpouse: false, isDivorced: false },
        });
      } else {
        rfEdges.push({
          id: `e-${node.parentNodeId}-${node.id}`,
          source: node.parentNodeId, target: node.id,
          type: "relationship",
          data: { relationType: node.relationType, isSpouse: false, isDivorced: false },
        });
      }
    }
    for (const sp of node.spouses) {
      rfEdges.push({
        id: `e-spouse-${node.id}-${sp.id}`,
        source: node.id, target: sp.id,
        type: "relationship",
        data: { relationType: sp.type, isSpouse: true, isDivorced: sp.type === "divorced from" },
      });
    }
  }

  const seen = new Set<string>();
  const uniqueNodes = rfNodes.filter((n) => {
    if (seen.has(n.id)) return false;
    seen.add(n.id);
    return true;
  });

  return layoutTree(uniqueNodes, rfEdges);
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
        if (node) { node.loading = false; node.expanded = true; }
        return clone;
      });
      return;
    }
    setGraph((prev) => expandGraphNode(prev, nodeId, personData));
  }, []);

  const { nodes, edges } = useMemo(() => graphToReactFlow(graph), [graph]);

  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50);
    return () => clearTimeout(t);
  }, [nodes, edges, fitView]);

  const onNodeDoubleClick = useCallback((_event: React.MouseEvent, node: RFNode) => {
    if (node.type !== "person") return;
    const data = node.data as PersonNodeData;
    if (data.nodeId !== person.id && data.hasPersonId) {
      navigate({ to: "/persons/$personId", params: { personId: data.nodeId } });
    }
  }, [navigate, person.id]);

  return (
    <ExpandContext.Provider value={expandNode}>
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
        <span className="text-[10px] italic">Click to expand · Double-click to navigate</span>
      </div>

      {/* Tree */}
      <div className="rounded-lg border border-ink/10 bg-white/50" style={{ height: 500 }}>
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
          onNodeDoubleClick={onNodeDoubleClick}
        />
      </div>
    </div>
    </ExpandContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Exported component
// ---------------------------------------------------------------------------

export function FamilyTree({ person }: { person: Person }) {
  return (
    <ReactFlowProvider>
      <FamilyTreeInner person={person} />
    </ReactFlowProvider>
  );
}
