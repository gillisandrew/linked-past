import { useEffect, useId, useState } from "react";
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

/** Convert an SVG string to a data URI for use in <img> tags. */
function svgToDataUri(svg: string): string {
  return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`;
}

/** Strip mermaid's inline max-width so the SVG renders at natural size. */
function stripMaxWidth(svg: string): string {
  return svg.replace(/style="[^"]*max-width:[^;"]*;?/g, (match) =>
    match.replace(/max-width:[^;"]*;?/, ""),
  );
}

/**
 * Ensure the SVG has explicit width/height attributes (required for <img> rendering).
 * Falls back to viewBox dimensions if width/height are missing or percentage-based.
 */
function ensureSvgDimensions(svg: string): string {
  const viewBoxMatch = svg.match(/viewBox=["'](\d+[\s,]+\d+[\s,]+(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?))["']/);
  if (!viewBoxMatch) return svg;

  const vbWidth = viewBoxMatch[2];
  const vbHeight = viewBoxMatch[3];

  // Replace percentage or missing width/height with viewBox values
  let result = svg;
  const hasValidWidth = /\bwidth=["']\d/.test(svg);
  const hasValidHeight = /\bheight=["']\d/.test(svg);

  if (!hasValidWidth) {
    result = result.replace(/<svg/, `<svg width="${vbWidth}"`);
  }
  if (!hasValidHeight) {
    result = result.replace(/<svg/, `<svg height="${vbHeight}"`);
  }
  // Replace percentage widths (e.g. width="100%")
  result = result.replace(/(<svg[^>]*)\bwidth=["']\d*%["']/, `$1 width="${vbWidth}"`);
  result = result.replace(/(<svg[^>]*)\bheight=["']\d*%["']/, `$1 height="${vbHeight}"`);

  return result;
}

export function MermaidBlock({ chart }: { chart: string }) {
  const id = useId().replace(/:/g, "_");
  const [error, setError] = useState<string | null>(null);
  const [svgHtml, setSvgHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMermaid().then(async (mermaid) => {
      if (cancelled) return;
      try {
        const { svg } = await mermaid.render(`mermaid-${id}`, chart);
        if (!cancelled) setSvgHtml(svg);
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

  if (!svgHtml) return null;

  const previewUri = svgToDataUri(svgHtml);
  const lightboxUri = svgToDataUri(ensureSvgDimensions(stripMaxWidth(svgHtml)));

  return <DiagramImage previewUri={previewUri} lightboxUri={lightboxUri} />;
}

function DiagramImage({ previewUri, lightboxUri }: { previewUri: string; lightboxUri: string }) {
  const [lightbox, setLightbox] = useState(false);

  return (
    <>
      <img
        src={previewUri}
        alt="Diagram"
        className="my-2 max-w-full h-auto cursor-zoom-in"
        onClick={() => setLightbox(true)}
        title="Click to enlarge"
      />
      {lightbox && (
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
                <img
                  src={lightboxUri}
                  alt="Diagram (enlarged)"
                  className="bg-white rounded-lg p-8"
                />
              </TransformComponent>
            </TransformWrapper>
          </div>
        </div>
      )}
    </>
  );
}
