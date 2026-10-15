import { fmtBytes, fmtPeriod, fmtRelative, parseUtc } from "@/lib/format";
import { qs } from "@/lib/api";

describe("formato", () => {
  it("interpreta las fechas de la API como UTC", () => {
    expect(parseUtc("2026-10-15T08:00:00")?.toISOString()).toBe("2026-10-15T08:00:00.000Z");
    expect(parseUtc(null)).toBeNull();
    expect(parseUtc("no-fecha")).toBeNull();
  });

  it("formatea tamaños", () => {
    expect(fmtBytes(16 * 1024 ** 3, true)).toBe("16 GB");
    expect(fmtBytes(512_000_000_000)).toBe("512 GB");
    expect(fmtBytes(null)).toBe("—");
  });

  it("formatea tiempos relativos y periodos", () => {
    const now = new Date("2026-10-15T10:00:00Z");
    expect(fmtRelative("2026-10-15T09:30:00", now)).toBe("hace 30 min");
    expect(fmtRelative(null, now)).toBe("nunca");
    expect(fmtPeriod("2026-10")).toBe("Octubre de 2026");
  });

  it("omite parámetros vacíos en la query", () => {
    expect(qs({ a: 1, b: "", c: null, d: undefined, e: false })).toBe("?a=1&e=false");
  });
});
