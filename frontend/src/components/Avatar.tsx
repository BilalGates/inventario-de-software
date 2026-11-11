/** Foto de perfil de Microsoft 365 (en caché en el servidor) o, si no hay, las iniciales. */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cx } from "./ui";

/** {upn en minúsculas: data URI}. Una sola petición para toda la app; se refresca cada hora. */
export const usePhotos = () =>
  useQuery({ queryKey: ["user-photos"], queryFn: () => api.get<Record<string, string>>("/users/photos"),
    staleTime: 60 * 60_000, gcTime: 2 * 60 * 60_000, retry: false });

export function initials(name: string) {
  return name.split(/[\s.@_-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("") || "?";
}

const SIZE = { sm: "size-7 text-2xs", md: "size-8 text-xs", lg: "size-10 text-sm" };

export function Avatar({ upn, name, size = "sm", className, inverted }: { upn?: string | null; name: string; size?: keyof typeof SIZE;
  className?: string; inverted?: boolean }) {
  const photo = usePhotos().data?.[(upn ?? "").toLowerCase()];
  const base = cx("inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full", SIZE[size], className);
  if (photo) return <img src={photo} alt="" aria-hidden className={cx(base, "object-cover")} />;
  return (
    <span aria-hidden className={cx(base, "font-semibold tracking-normal", inverted ? "bg-fg text-bg" : "bg-subtle text-fg-2")}>
      {initials(name)}
    </span>
  );
}
