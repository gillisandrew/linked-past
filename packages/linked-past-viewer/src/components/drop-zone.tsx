import { useState, useRef, useCallback, type DragEvent } from "react";
import { Upload } from "lucide-react";

export function DropZone({
  onLoadText,
  onLoadFile,
}: {
  onLoadText: (text: string) => void;
  onLoadFile: (file: File) => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [showPaste, setShowPaste] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onLoadFile(file);
    },
    [onLoadFile],
  );

  const handleFileSelect = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onLoadFile(file);
    },
    [onLoadFile],
  );

  const handlePasteLoad = useCallback(() => {
    if (pasteText.trim()) onLoadText(pasteText);
  }, [pasteText, onLoadText]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 px-4">
      <div
        className={`w-full max-w-md border border-dashed rounded-lg p-16 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-foreground text-foreground"
            : "border-border text-muted-foreground hover:border-muted-foreground"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleFileSelect}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".jsonl"
          className="hidden"
          onChange={handleFileChange}
        />
        <div className="flex flex-col items-center gap-3">
          <Upload className="w-4 h-4" />
          <p className="text-sm">
            {isDragging ? "Drop to load" : "Drop a session file or click to browse"}
          </p>
        </div>
      </div>

      <button
        onClick={() => setShowPaste(!showPaste)}
        className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
      >
        {showPaste ? "Hide paste area" : "Or paste JSONL content"}
      </button>

      {showPaste && (
        <div className="w-full max-w-md space-y-3">
          <textarea
            className="w-full h-32 border border-border rounded-lg bg-transparent px-3 py-2 text-xs font-mono resize-y focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder='{"session_id":"...","seq":1,"type":"query",...}'
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <button
            onClick={handlePasteLoad}
            disabled={!pasteText.trim()}
            className="w-full py-2 text-xs font-medium border border-border rounded-lg hover:bg-muted disabled:opacity-40 cursor-pointer transition-colors"
          >
            Load session
          </button>
        </div>
      )}
    </div>
  );
}
