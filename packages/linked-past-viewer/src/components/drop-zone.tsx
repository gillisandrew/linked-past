import { useState, useRef, useCallback, type DragEvent } from "react";
import { Upload, ClipboardPaste, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

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
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          linked-past session viewer
        </h1>
        <p className="text-muted-foreground">
          Drop a session <code className="text-xs bg-muted px-1.5 py-0.5 rounded">.jsonl</code> file or paste its contents to browse
        </p>
      </div>

      <div
        className={`w-full max-w-lg border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50"
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
          {isDragging ? (
            <FileText className="w-10 h-10 text-primary" />
          ) : (
            <Upload className="w-10 h-10 text-muted-foreground" />
          )}
          <p className="text-sm text-muted-foreground">
            {isDragging ? "Drop to load" : "Drag & drop or click to browse"}
          </p>
        </div>
      </div>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowPaste(!showPaste)}
        className="text-muted-foreground"
      >
        <ClipboardPaste className="w-4 h-4 mr-2" />
        {showPaste ? "Hide paste area" : "Or paste JSONL content"}
      </Button>

      {showPaste && (
        <div className="w-full max-w-lg space-y-3">
          <textarea
            className="w-full h-40 rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder='{"session_id":"...","seq":1,"type":"query",...}'
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <Button
            onClick={handlePasteLoad}
            disabled={!pasteText.trim()}
            className="w-full"
          >
            Load session
          </Button>
        </div>
      )}
    </div>
  );
}
