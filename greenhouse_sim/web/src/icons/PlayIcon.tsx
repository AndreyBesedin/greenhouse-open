import { Icon } from "./Icon";

/** A triangle pointing right. */
export function PlayIcon({ size }: { size?: number | undefined }) {
  return (
    <Icon viewBox="0 0 24 24" style="filled" size={size}>
      <path d="M7 4l13 8-13 8z" />
    </Icon>
  );
}
