/**
 * Typed API client on top of the generated OpenAPI types.
 *
 * The generated `paths` keys already include the `/api` prefix, so with an
 * empty baseUrl the same relative URLs work in dev (Vite proxy) and prod
 * (Caddy). The backend has no CORS middleware — never point this client at
 * another origin.
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const client = createClient<paths>({ baseUrl: "" });

/** Convenience aliases for the generated component schemas. */
export type Schemas = components["schemas"];
export type AccountRead = Schemas["AccountRead"];
export type AccountCreate = Schemas["AccountCreate"];
export type AccountUpdate = Schemas["AccountUpdate"];
export type InstrumentRead = Schemas["InstrumentRead"];
export type InstrumentCreate = Schemas["InstrumentCreate"];
export type InstrumentUpdate = Schemas["InstrumentUpdate"];
export type CategoryRead = Schemas["CategoryRead"];
export type CategoryCreate = Schemas["CategoryCreate"];
export type CategoryUpdate = Schemas["CategoryUpdate"];
export type AssetClassRead = Schemas["AssetClassRead"];
export type AssetClass = Schemas["AssetClass"];
export type LoanStatus = Schemas["LoanStatus"];
export type PriceSource = Schemas["PriceSource"];
export type MovementRead = Schemas["MovementRead"];
export type MovementCreate = Schemas["MovementCreate"];
export type MovementType = Schemas["MovementType"];
export type TransferCreate = Schemas["TransferCreate"];
export type TransferRead = Schemas["TransferRead"];
export type PositionRead = Schemas["PositionRead"];
export type NetWorthRead = Schemas["NetWorthRead"];
export type NetWorthSeriesRead = Schemas["NetWorthSeriesRead"];
export type AllocationRead = Schemas["AllocationRead"];
export type Interval = Schemas["Interval"];
export type Dimension = Schemas["Dimension"];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Extract a human-readable message from an error body. Domain errors are
 * `{"detail": string}`; FastAPI request-validation errors carry a structured
 * `detail` array whose items have a `msg`.
 */
function detailMessage(error: unknown, status: number): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown; loc?: unknown };
      if (typeof first.msg === "string") {
        const loc = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
        return loc ? `${loc}: ${first.msg}` : first.msg;
      }
    }
  }
  return `Request failed with status ${status}`;
}

/**
 * Turn an openapi-fetch result into data-or-throw so TanStack Query sees
 * real errors. Every query/mutation function goes through this.
 */
export function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (result.error !== undefined) {
    throw new ApiError(result.response.status, detailMessage(result.error, result.response.status));
  }
  return result.data as T;
}
