import { Icon } from "./Icon";

/** Two bars. */
export function PauseIcon({ size }: { size?: number | undefined }) {
  return (
    <Icon viewBox="0 0 24 24" style="filled" size={size}>
      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
    </Icon>
  );
}
