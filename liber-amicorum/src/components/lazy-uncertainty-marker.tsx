import { useCallback, useRef, useState } from "react";
import { getPersonById } from "#/lib/data";
import { UncertaintyMarker } from "#/components/uncertainty-marker";

interface LazyUncertaintyMarkerProps {
  uncertain: boolean;
  children: React.ReactNode;
  /** Person ID to fetch notes from */
  personId: string;
  /** Office ID to match the post assertion */
  officeId?: string;
  /** Date to match the post assertion */
  dateStart?: number | null;
}

/**
 * UncertaintyMarker that lazy-loads assertion notes from a person's
 * full JSON on first hover. Used in holders tables where the notes
 * aren't available in the lightweight holder data.
 */
export function LazyUncertaintyMarker({
  uncertain,
  children,
  personId,
  officeId,
  dateStart,
}: LazyUncertaintyMarkerProps) {
  const [notes, setNotes] = useState<string[] | undefined>(undefined);
  const fetchedRef = useRef(false);

  const handleHover = useCallback(async () => {
    if (fetchedRef.current || !uncertain) return;
    fetchedRef.current = true;

    const person = await getPersonById(personId);
    if (!person) return;

    // Find the matching post assertion
    const match = person.postAssertions.find(
      (pa) =>
        (!officeId || pa.officeId === officeId) &&
        (dateStart == null || pa.dateStart === dateStart),
    );

    if (match && match.notes.length > 0) {
      setNotes(match.notes);
    }
  }, [uncertain, personId, officeId, dateStart]);

  return (
    <span onMouseEnter={handleHover}>
      <UncertaintyMarker uncertain={uncertain} notes={notes}>
        {children}
      </UncertaintyMarker>
    </span>
  );
}
