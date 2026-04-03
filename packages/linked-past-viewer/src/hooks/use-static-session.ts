import { useState, useCallback } from "react";
import { parseSessionJsonl } from "@/lib/parse-session";
import type { ParseError } from "@/lib/parse-session";
import type { ViewerMessage } from "@/lib/schemas";

export type StaticSession = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  loadFromText: (text: string) => void;
  loadFromFile: (file: File) => void;
  clear: () => void;
  isLoaded: boolean;
};

export function useStaticSession(): StaticSession {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [errors, setErrors] = useState<ParseError[]>([]);
  const [formatVersion, setFormatVersion] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  const load = useCallback((text: string) => {
    const result = parseSessionJsonl(text);
    setMessages(result.messages);
    setErrors(result.errors);
    setFormatVersion(result.formatVersion);
    setIsLoaded(true);
  }, []);

  const loadFromText = useCallback(
    (text: string) => load(text),
    [load],
  );

  const loadFromFile = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result;
        if (typeof text === "string") load(text);
      };
      reader.readAsText(file);
    },
    [load],
  );

  const clear = useCallback(() => {
    setMessages([]);
    setErrors([]);
    setFormatVersion(null);
    setIsLoaded(false);
  }, []);

  return { messages, errors, formatVersion, loadFromText, loadFromFile, clear, isLoaded };
}
