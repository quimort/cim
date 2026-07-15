import { Button, Select, Stack, Text, TextInput } from "@mantine/core";
import { DateTimePicker } from "@mantine/dates";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import type { AccountRead, InstrumentRead, MovementCreate } from "../../api/client";
import { useCreateMovement } from "../../api/queries";
import { toApiDateTime } from "../../lib/dates";
import {
  CREATABLE_MOVEMENT_TYPES,
  MOVEMENT_RULES,
  type CreatableMovementType,
} from "../../lib/movementRules";

const CURRENCY_RE = /^[A-Za-z]{3}$/;
const AMOUNT_RE = /^\d+(\.\d+)?$/;

interface MovementFormValues {
  type: CreatableMovementType;
  occurred_at: Date | null;
  account_id: string | null;
  instrument_id: string | null;
  quantity: string;
  price: string;
  fee: string;
  currency: string;
}

function positiveAmount(value: string): string | null {
  if (!AMOUNT_RE.test(value)) return "Decimal amount, e.g. 1234.56";
  if (!/[1-9]/.test(value)) return "Must be greater than zero";
  return null;
}

export function MovementForm({
  accounts,
  instruments,
}: {
  accounts: AccountRead[];
  instruments: InstrumentRead[];
}) {
  const create = useCreateMovement();
  const form = useForm<MovementFormValues>({
    initialValues: {
      type: "purchase",
      occurred_at: new Date(),
      account_id: null,
      instrument_id: null,
      quantity: "",
      price: "",
      fee: "",
      currency: "EUR",
    },
    validate: {
      occurred_at: (v) => (v ? null : "When did it happen?"),
      account_id: (v) => (v ? null : "Account is required"),
      instrument_id: (v, values) =>
        MOVEMENT_RULES[values.type].instrument_id === "required" && !v
          ? "Instrument is required for this type"
          : null,
      quantity: positiveAmount,
      price: (v, values) => {
        const rule = MOVEMENT_RULES[values.type].price;
        if (rule === "required" && !v) return "Price is required for this type";
        if (rule !== "forbidden" && v) return positiveAmount(v);
        return null;
      },
      fee: (v, values) =>
        MOVEMENT_RULES[values.type].fee !== "forbidden" && v && !AMOUNT_RE.test(v)
          ? "Decimal amount, e.g. 1.50"
          : null,
      currency: (v) => (CURRENCY_RE.test(v) ? null : "3-letter ISO code, e.g. EUR"),
    },
  });

  const rules = MOVEMENT_RULES[form.values.type];

  const submit = form.onSubmit((values) => {
    const body: MovementCreate = {
      type: values.type,
      occurred_at: toApiDateTime(values.occurred_at!),
      account_id: Number(values.account_id),
      // Amount strings go to the API verbatim — the backend rejects JSON
      // numbers for money, so no parsing may happen here.
      quantity: values.quantity,
      currency: values.currency.toUpperCase(),
    };
    if (rules.instrument_id !== "forbidden" && values.instrument_id) {
      body.instrument_id = Number(values.instrument_id);
    }
    if (rules.price !== "forbidden" && values.price) body.price = values.price;
    if (rules.fee !== "forbidden" && values.fee) body.fee = values.fee;

    create.mutate(body, {
      onSuccess: () => {
        notifications.show({ color: "green", message: `${values.type} registered` });
        // Keep type/account/date for rapid batch entry; clear the amounts.
        form.setFieldValue("quantity", "");
        form.setFieldValue("price", "");
        form.setFieldValue("fee", "");
      },
    });
  });

  return (
    <form onSubmit={submit}>
      <Stack>
        <Select
          label="Type"
          withAsterisk
          data={CREATABLE_MOVEMENT_TYPES}
          allowDeselect={false}
          {...form.getInputProps("type")}
          onChange={(value) => {
            if (!value) return;
            const type = value as CreatableMovementType;
            form.setFieldValue("type", type);
            // Clear whatever the new type forbids.
            if (MOVEMENT_RULES[type].instrument_id === "forbidden") {
              form.setFieldValue("instrument_id", null);
            }
            if (MOVEMENT_RULES[type].price === "forbidden") form.setFieldValue("price", "");
            if (MOVEMENT_RULES[type].fee === "forbidden") form.setFieldValue("fee", "");
          }}
        />
        <DateTimePicker label="Occurred at" withAsterisk {...form.getInputProps("occurred_at")} />
        <Select
          label="Account"
          withAsterisk
          searchable
          data={accounts.map((a) => ({ value: String(a.id), label: `${a.name} (${a.currency})` }))}
          {...form.getInputProps("account_id")}
          onChange={(value) => {
            form.setFieldValue("account_id", value);
            const account = accounts.find((a) => String(a.id) === value);
            if (account) form.setFieldValue("currency", account.currency);
          }}
        />
        {rules.instrument_id !== "forbidden" && (
          <Select
            label={rules.instrument_id === "required" ? "Instrument" : "Instrument (optional)"}
            withAsterisk={rules.instrument_id === "required"}
            searchable
            clearable={rules.instrument_id === "optional"}
            data={instruments.map((i) => ({ value: String(i.id), label: i.name }))}
            {...form.getInputProps("instrument_id")}
          />
        )}
        <TextInput
          label={form.values.type === "fee" ? "Amount" : "Quantity"}
          withAsterisk
          inputMode="decimal"
          placeholder="0.00"
          description={
            form.values.type === "fee"
              ? "For a fee movement, the quantity is the fee amount."
              : undefined
          }
          {...form.getInputProps("quantity")}
        />
        {rules.price !== "forbidden" && (
          <TextInput
            label="Unit price"
            withAsterisk={rules.price === "required"}
            inputMode="decimal"
            placeholder="0.00"
            {...form.getInputProps("price")}
          />
        )}
        {rules.fee !== "forbidden" && (
          <TextInput
            label="Fee (optional)"
            inputMode="decimal"
            placeholder="0.00"
            {...form.getInputProps("fee")}
          />
        )}
        <TextInput
          label="Currency"
          withAsterisk
          maxLength={3}
          description="This movement's native currency — not necessarily the account's"
          {...form.getInputProps("currency")}
        />
        <Button type="submit" loading={create.isPending}>
          Register movement
        </Button>
        <Text size="xs" c="dimmed">
          The ledger is append-only: to correct a mistake, annul the movement and re-enter it.
        </Text>
      </Stack>
    </form>
  );
}
