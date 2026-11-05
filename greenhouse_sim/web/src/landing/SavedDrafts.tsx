import { DRAFTS_URL, loadDrafts } from "../builder/api";
import { useLoad } from "../useLoad";
import { draftAddress } from "./paths";
import { dayText } from "./storedRuns";

/** How many of the latest drafts the start page lists: the builder lists them all. */
const LISTED = 3;

/**
 * The drafts saved, the latest first, each opening in the builder (P17.5), so
 * that one can be picked up from the start page. Nothing while there is none, or
 * none can be listed, which the builder says.
 */
export function SavedDrafts() {
  const drafts = useLoad(DRAFTS_URL, (_url, fetchFn) => loadDrafts(fetchFn));
  if (drafts.status !== "loaded" || drafts.value.length === 0) {
    return null;
  }
  const latest = [...drafts.value]
    .sort((one, other) => Date.parse(other.saved_at) - Date.parse(one.saved_at))
    .slice(0, LISTED);
  const count = drafts.value.length;
  return (
    <nav className="landing-drafts" aria-label="Saved drafts">
      <p>Saved drafts{count > LISTED ? `, the latest ${LISTED} of ${count}` : ""}</p>
      {latest.map((draft) => (
        <p key={draft.draft_id}>
          <a href={draftAddress(draft.draft_id)} title={draft.name}>
            {draft.name}
          </a>
          <span>
            revision {draft.revision} · saved {dayText(draft.saved_at)}
          </span>
        </p>
      ))}
    </nav>
  );
}
