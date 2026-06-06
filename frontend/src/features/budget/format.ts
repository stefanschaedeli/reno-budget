const CHF_FMT = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
  maximumFractionDigits: 0,
});

const CHF_FMT_PRECISE = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
});

const PERCENT_FMT = new Intl.NumberFormat("de-CH", {
  style: "decimal",
  maximumFractionDigits: 2,
});

export function formatChfRounded(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return CHF_FMT.format(n);
}

export function formatChfPrecise(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return CHF_FMT_PRECISE.format(n);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${PERCENT_FMT.format(value)} %`;
}

export function toNumber(value: string | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const n = Number(value);
  return Number.isNaN(n) ? 0 : n;
}
