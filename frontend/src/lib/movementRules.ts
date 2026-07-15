/**
 * Client-side mirror of the backend's per-movement-type field rules
 * (`_TYPE_RULES` in backend/app/schemas/movement.py), so the form can show
 * or hide fields instead of letting the user run into 422s.
 *
 * Keying by `CreatableMovementType` (derived from the generated enum) makes
 * a newly added backend movement type a COMPILE error after `npm run
 * gen:api`. A changed rule value still needs a manual sync — the backend
 * re-validates everything, so the worst drift outcome is a 422 notification,
 * never bad data.
 */
import type { components } from "../api/schema";

type MovementType = components["schemas"]["MovementType"];

/** Transfer legs are never created directly — POST /movements/transfer. */
export type CreatableMovementType = Exclude<MovementType, "transfer_out" | "transfer_in">;

export type FieldRule = "required" | "optional" | "forbidden";

export interface MovementTypeRules {
  instrument_id: FieldRule;
  price: FieldRule;
  fee: FieldRule;
}

export const MOVEMENT_RULES: Record<CreatableMovementType, MovementTypeRules> = {
  purchase: { instrument_id: "required", price: "required", fee: "optional" },
  sale: { instrument_id: "required", price: "required", fee: "optional" },
  dividend: { instrument_id: "required", price: "forbidden", fee: "optional" },
  interest: { instrument_id: "optional", price: "forbidden", fee: "optional" },
  // The quantity IS the fee, so a separate fee field would be ambiguous.
  fee: { instrument_id: "optional", price: "forbidden", fee: "forbidden" },
  deposit: { instrument_id: "forbidden", price: "forbidden", fee: "optional" },
  withdrawal: { instrument_id: "forbidden", price: "forbidden", fee: "optional" },
  principal_repayment: { instrument_id: "required", price: "forbidden", fee: "optional" },
};

export const CREATABLE_MOVEMENT_TYPES = Object.keys(MOVEMENT_RULES) as CreatableMovementType[];
