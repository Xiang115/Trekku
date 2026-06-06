export type IconName =
  | "search"
  | "plane"
  | "bed"
  | "map"
  | "users"
  | "wallet"
  | "check"
  | "lock"
  | "user"
  | "star"
  | "swap";

type IconProps = {
  name: IconName;
} & React.SVGProps<SVGSVGElement>;

/** Thin wrapper around the inline sprite: <Icon name="plane" />. */
export default function Icon({ name, ...rest }: IconProps) {
  return (
    <svg {...rest}>
      <use href={`#icon-${name}`} />
    </svg>
  );
}
