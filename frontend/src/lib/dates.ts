/**
 * Date helpers for the two serialization shapes the API uses:
 *
 * - `occurred_at` and the movement range filters are timezone-aware
 *   datetimes → always ISO with `Z` via `toISOString()`.
 * - `?date=`, `from`, `to` are calendar dates → LOCAL `YYYY-MM-DD` via
 *   dayjs. Never `toISOString().slice(0, 10)`: that shifts the day across
 *   midnight in non-UTC timezones.
 */
import dayjs from "dayjs";

export function toApiDateTime(d: Date): string {
  return d.toISOString();
}

export function toApiDate(d: Date): string {
  return dayjs(d).format("YYYY-MM-DD");
}

/** Inclusive day-start bound for datetime range filters. */
export function dayStartIso(d: Date): string {
  return dayjs(d).startOf("day").toISOString();
}

/** Inclusive day-end bound for datetime range filters. */
export function dayEndIso(d: Date): string {
  return dayjs(d).endOf("day").toISOString();
}

/** Display an API datetime in local time. */
export function formatDateTime(iso: string): string {
  return dayjs(iso).format("YYYY-MM-DD HH:mm");
}

/** Display an API date. */
export function formatDate(iso: string): string {
  return dayjs(iso).format("YYYY-MM-DD");
}
