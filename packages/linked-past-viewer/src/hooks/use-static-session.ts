import { useState, useCallback } from "react";
import { parseSessionJsonl } from "@/lib/parse-session";
import type { ParseError, ParseResult } from "@/lib/parse-session";
import type { ViewerMessage } from "@/lib/schemas";

export type StaticSession = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  loadFromText: (text: string) => void;
  loadFromFile: (file: File) => void;
  loadFromParseResult: (result: ParseResult) => void;
  clear: () => void;
  isLoaded: boolean;
};

export function useStaticSession(): StaticSession {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [errors, setErrors] = useState<ParseError[]>([]);
  const [formatVersion, setFormatVersion] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  const applyResult = useCallback((result: ParseResult) => {
    setMessages(result.messages);
    setErrors(result.errors);
    setFormatVersion(result.formatVersion);
    setIsLoaded(true);
  }, []);

  const loadFromText = useCallback(
    (text: string) => applyResult(parseSessionJsonl(text)),
    [applyResult],
  );

  const loadFromFile = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result;
        if (typeof text === "string") applyResult(parseSessionJsonl(text));
      };
      reader.readAsText(file);
    },
    [applyResult],
  );

  const loadFromParseResult = applyResult;

  const clear = useCallback(() => {
    setMessages([]);
    setErrors([]);
    setFormatVersion(null);
    setIsLoaded(false);
  }, []);

  return {
    messages,
    errors,
    formatVersion,
    loadFromText,
    loadFromFile,
    loadFromParseResult,
    clear,
    isLoaded,
  };
}
