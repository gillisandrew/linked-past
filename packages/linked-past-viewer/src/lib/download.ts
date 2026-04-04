/**
 * Download a session as JSONL from the viewer API.
 */
export async function downloadSessionJsonl(sessionId: string): Promise<void> {
  const res = await fetch(`/viewer/api/sessions/${sessionId}?format=jsonl`);
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `linked-past-${sessionId}.jsonl`;
  a.click();
  URL.revokeObjectURL(url);
}
