import { useEffect, useId, useRef, useState } from "react";

let mermaidPromise: Promise<typeof import("mermaid")["default"]> | null = null;

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((m) => {
      m.default.initialize({
        startOnLoad: false,
        theme: "default",
        securityLevel: "loose",
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
  const [lightbox, setLightbox] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMermaid().then(async (mermaid) => {
      if (cancelled || !containerRef.current) return;
      try {
        const { svg } = await mermaid.render(`mermaid-${id}`, chart);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
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
      {lightbox && (
        <div
          className="fixed inset-0 z-[200] bg-black/70 flex items-center justify-center cursor-zoom-out"
          onClick={() => setLightbox(false)}
        >
          <div
            className="bg-background rounded-lg p-6 max-w-[90vw] max-h-[90vh] overflow-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            dangerouslySetInnerHTML={{ __html: containerRef.current?.innerHTML ?? "" }}
          />
          <button
            onClick={() => setLightbox(false)}
            className="absolute top-4 right-4 text-white text-2xl cursor-pointer hover:opacity-80"
          >
            ✕
          </button>
        </div>
      )}
    </>
  );
}
