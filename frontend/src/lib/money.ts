/**
 * Money display helpers.
 *
 * Amounts travel through the API as decimal strings (CLAUDE.md: no floats
 * for money), and the frontend performs NO arithmetic on them — every
 * derived figure arrives server-computed. These helpers only format.
 *
 * `Intl.NumberFormat.format` accepts a decimal string and formats it exactly
 * (ES2023), with no float round-trip. TypeScript's lib still types the
 * argument as `number | bigint`, so the cast below is confined here.
 *
 * The single sanctioned string→float conversion is `toChartNumber`, used
 * only to hand pixel coordinates to Recharts (visualization, not
 * accounting). Chart labels and tooltips must format from the original
 * string kept in the datum.
 */

const moneyFormatters = new Map<string, Intl.NumberFormat>();

function moneyFormatter(currency: string): Intl.NumberFormat {
  let formatter = moneyFormatters.get(currency);
  if (!formatter) {
    formatter = new Intl.NumberFormat(undefined, { style: "currency", currency });
    moneyFormatters.set(currency, formatter);
  }
  return formatter;
}

/** Format a decimal string in its native currency. Never assumes EUR. */
export function formatMoney(value: string, currency: string): string {
  return moneyFormatter(currency).format(value as unknown as number);
}

const quantityFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 10,
});

/** Format a quantity string (up to 10 decimals — crypto needs ≥8). */
export function formatQuantity(value: string): string {
  return quantityFormatter.format(value as unknown as number);
}

const percentFormatter = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 1,
});

/** Format a 0–1 weight string as a percentage. */
export function formatPercent(weight: string): string {
  return percentFormatter.format(weight as unknown as number);
}

/** Sign check without parsing — for red/green P&L coloring. */
export function isNegative(value: string): boolean {
  return value.startsWith("-") && /[1-9]/.test(value);
}

/**
 * The ONLY place a money string may become a float: chart coordinates.
 * Plot positions are inherently floats; anything user-readable must format
 * from the original string instead.
 */
export function toChartNumber(value: string): number {
  return Number(value);
}
