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
// Family node type (flat graph with generation levels)
// ---------------------------------------------------------------------------

interface FamilyNode {
  id: string;
  name: string;
  generation: number;
  relationType: string;
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
// React Flow node/edge data types
// ---------------------------------------------------------------------------

interface PersonNodeData extends Record<string, unknown> {
  name: string;
  relationType: string;
  direction: RelDirection;
  isRoot: boolean;
  expanded: boolean;
  loading: boolean;
  hasPersonId: boolean;
  canExpand: boolean;
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
// Custom Person Node
// ---------------------------------------------------------------------------

function PersonNodeComponent({ data, id }: NodeProps<PersonNode>) {
  const isAncestor = data.direction === "ancestor";
  const isDescendant = data.direction === "descendant" || data.direction === "spouse";
  const canExpandUp = isAncestor && !data.expanded && !data.loading && data.hasPersonId;
  const canExpandDown =
    data.direction === "descendant" &&
    !data.isRoot &&
    !data.expanded &&
    !data.loading &&
    data.hasPersonId;

  const borderColor = data.isRoot
    ? COLORS.root
    : data.direction === "spouse"
      ? COLORS.spouse
      : COLORS.family;

  return (
    <div className="relative">
      {/* Target handle (top) */}
      {(isDescendant || data.isRoot) && (
        <Handle type="target" position={Position.Top} className="!bg-ink/30 !w-2 !h-2" />
      )}
      {isAncestor && (
        <Handle type="source" position={Position.Top} className="!bg-ink/30 !w-2 !h-2" />
      )}

      {/* Expand up button */}
      {canExpandUp && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onExpand(id);
          }}
          className="absolute -top-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-white z-10"
          style={{ backgroundColor: COLORS.root }}
        >
          <ChevronUp className="w-3 h-3" />
        </button>
      )}

      {/* Node body */}
      <div
        className="rounded-md px-3 py-1.5 text-center bg-white min-w-[150px]"
        style={{
          border: `${data.isRoot ? 2.5 : 1}px solid ${borderColor}`,
        }}
      >
        <p className="text-[11px] font-medium text-ink truncate max-w-[140px]">
          {data.name.length > 20 ? data.name.slice(0, 18) + "\u2026" : data.name}
        </p>
        {!data.isRoot && data.relationType && (
          <p className="text-[8px] text-ink-muted">{data.relationType}</p>
        )}
        {data.loading && <p className="text-[10px] text-ink-muted animate-pulse">loading...</p>}
      </div>

      {/* Expand down button */}
      {canExpandDown && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onExpand(id);
          }}
          className="absolute -bottom-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center text-white z-10"
          style={{ backgroundColor: COLORS.family }}
        >
          <ChevronDown className="w-3 h-3" />
        </button>
      )}

      {/* Source handle (bottom) */}
      {(isDescendant || data.isRoot) && (
        <Handle type="source" position={Position.Bottom} className="!bg-ink/30 !w-2 !h-2" />
      )}
      {isAncestor && (
        <Handle type="target" position={Position.Bottom} className="!bg-ink/30 !w-2 !h-2" />
      )}
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
// Node/edge type registrations
// ---------------------------------------------------------------------------

const nodeTypes: NodeTypes = { person: PersonNodeComponent };
const edgeTypes: EdgeTypes = { relationship: RelationshipEdge };

// ---------------------------------------------------------------------------
// Dagre layout
// ---------------------------------------------------------------------------

const NODE_W = 170;
const NODE_H = 50;

function layoutTree(
  nodes: PersonNode[],
  edges: RelEdge[],
): { nodes: PersonNode[]; edges: RelEdge[] } {
  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 80, nodesep: 40 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_W, height: NODE_H });
  }

  for (const edge of edges) {
    // For ancestor edges, the source is the child and target is the parent
    // but dagre should lay out parent above child, so we reverse
    if (edge.data?.isSpouse) {
      // Spouse edges: don't add to dagre for rank calc, just position them
      // Actually we still add them so dagre puts them close
      g.setEdge(edge.source, edge.target);
    } else {
      g.setEdge(edge.source, edge.target);
    }
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
// Convert FamilyGraph to React Flow nodes/edges
// ---------------------------------------------------------------------------

function graphToReactFlow(
  graph: FamilyGraph,
  onExpand: (nodeId: string) => void,
): { nodes: PersonNode[]; edges: RelEdge[] } {
  const rfNodes: PersonNode[] = [];
  const rfEdges: RelEdge[] = [];
  const allNodeIds = new Set<string>();

  // First, collect all nodes including spouses
  for (const node of graph.nodes.values()) {
    allNodeIds.add(node.id);
    for (const sp of node.spouses) {
      allNodeIds.add(sp.id);
    }
  }

  // Add main nodes
  for (const node of graph.nodes.values()) {
    rfNodes.push({
      id: node.id,
      type: "person",
      position: { x: 0, y: 0 },
      data: {
        name: node.name,
        relationType: node.relationType,
        direction: node.direction,
        isRoot: node.id === graph.rootId,
        expanded: node.expanded,
        loading: node.loading,
        hasPersonId: node.hasPersonId,
        canExpand: node.hasPersonId && !node.expanded,
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
            relationType: sp.type,
            direction: "spouse",
            isRoot: false,
            expanded: false,
            loading: false,
            hasPersonId: sp.hasPersonId,
            canExpand: false,
            onExpand,
          },
        });
      }
    }
  }

  // Add parent-child edges
  for (const node of graph.nodes.values()) {
    if (node.parentNodeId && allNodeIds.has(node.parentNodeId)) {
      if (node.direction === "ancestor") {
        // Ancestor: parent (this node) is above the parentNodeId (which is the root/child)
        // Edge goes from ancestor down to child
        rfEdges.push({
          id: `e-${node.id}-${node.parentNodeId}`,
          source: node.id,
          target: node.parentNodeId,
          type: "relationship",
          data: {
            relationType: node.relationType,
            isSpouse: false,
            isDivorced: false,
          },
        });
      } else {
        // Descendant: parentNodeId is above, this node is below
        rfEdges.push({
          id: `e-${node.parentNodeId}-${node.id}`,
          source: node.parentNodeId,
          target: node.id,
          type: "relationship",
          data: {
            relationType: node.relationType,
            isSpouse: false,
            isDivorced: false,
          },
        });
      }
    }

    // Add spouse edges
    for (const sp of node.spouses) {
      rfEdges.push({
        id: `e-spouse-${node.id}-${sp.id}`,
        source: node.id,
        target: sp.id,
        type: "relationship",
        data: {
          relationType: sp.type,
          isSpouse: true,
          isDivorced: sp.type === "divorced from",
        },
      });
    }
  }

  // Deduplicate nodes by id
  const seen = new Set<string>();
  const uniqueNodes = rfNodes.filter((n) => {
    if (seen.has(n.id)) return false;
    seen.add(n.id);
    return true;
  });

  return layoutTree(uniqueNodes, rfEdges);
}

// ---------------------------------------------------------------------------
// Inner component (needs ReactFlowProvider above it)
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

  // Fit view after nodes change
  useEffect(() => {
    // Small delay to let React Flow measure nodes
    const t = setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50);
    return () => clearTimeout(t);
  }, [nodes, edges, fitView]);

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
            style={{ backgroundColor: COLORS.root }}
          >
            <ChevronUp className="w-2.5 h-2.5 text-white" />
          </span>
          Expand ancestors
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-full flex items-center justify-center"
            style={{ backgroundColor: COLORS.family }}
          >
            <ChevronDown className="w-2.5 h-2.5 text-white" />
          </span>
          Expand descendants
        </span>
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
          elementsSelectable={false}
          onNodeDoubleClick={(_event, node) => {
            if (node.id !== person.id && node.data.hasPersonId) {
              navigate({ to: "/persons/$personId", params: { personId: node.id } });
            }
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported component (wraps with ReactFlowProvider)
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
