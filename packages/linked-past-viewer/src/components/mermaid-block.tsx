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
              minScale={0.5}
              maxScale={5}
              centerOnInit
            >
              <TransformComponent
                wrapperStyle={{ width: "100%", height: "100%" }}
                contentStyle={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                <div
                  className="bg-white rounded-lg p-8 [&_svg]:max-w-none [&_svg]:w-auto [&_svg]:h-auto"
                  dangerouslySetInnerHTML={{ __html: svgHtml }}
                />
              </TransformComponent>
            </TransformWrapper>
          </div>
        </div>
      )}
    </>
  );
}
