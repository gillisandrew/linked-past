import { useEffect, useId, useRef, useState } from "react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";

let mermaidPromise: Promise<typeof import("mermaid")["default"]> | null = null;

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((m) => {
      m.default.initialize({
        startOnLoad: false,
        theme: "default",
        securityLevel: "strict",
      });
      return m.default;
    });
  }
  return mermaidPromise;
}

/** Strip mermaid's inline max-width style so the SVG can scale freely in the lightbox. */
function stripMaxWidth(svg: string): string {
  return svg.replace(/style="[^"]*max-width:[^;"]*;?/g, (match) =>
    match.replace(/max-width:[^;"]*;?/, ""),
  );
}

export function MermaidBlock({ chart }: { chart: string }) {
  const id = useId().replace(/:/g, "_");
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [svgHtml, setSvgHtml] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMermaid().then(async (mermaid) => {
      if (cancelled || !containerRef.current) return;
      try {
        const { svg } = await mermaid.render(`mermaid-${id}`, chart);
        if (!cancelled) {
          setSvgHtml(svg);
          if (containerRef.current) {
            containerRef.current.innerHTML = svg;
          }
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  if (error) {
    return (
      <pre className="p-2 rounded bg-muted text-xs text-red-500 overflow-x-auto">
        {error}
      </pre>
    );
  }

  return (
    <>
      <div
        ref={containerRef}
        className="my-2 overflow-x-auto cursor-zoom-in"
        onClick={() => setLightbox(true)}
        title="Click to enlarge"
      />
      {lightbox && svgHtml && (
        <div
          className="fixed inset-0 z-[200] bg-black/80 flex flex-col"
          onClick={() => setLightbox(false)}
        >
          <div className="flex items-center justify-between px-4 py-2 text-white text-sm">
            <span className="text-white/60">Scroll to zoom, drag to pan</span>
            <button
              onClick={() => setLightbox(false)}
              className="text-white text-xl cursor-pointer hover:opacity-80 px-2"
            >
              ✕
            </button>
          </div>
          <div
            className="flex-1 flex items-center justify-center overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <TransformWrapper
              initialScale={1}
              minScale={0.2}
              maxScale={10}
              centerOnInit
              wheel={{ step: 0.1 }}
            >
              <TransformComponent
                wrapperStyle={{ width: "100%", height: "100%" }}
              >
                <div
                  className="bg-white rounded-lg p-8 [&_svg]:max-w-none [&_svg]:h-auto [&_svg]:max-h-none"
                  dangerouslySetInnerHTML={{ __html: stripMaxWidth(svgHtml) }}
                />
              </TransformComponent>
            </TransformWrapper>
          </div>
        </div>
      )}
    </>
  );
}
