import { Button, Select, Stack, Text, TextInput } from "@mantine/core";
import { DateTimePicker } from "@mantine/dates";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import type { AccountRead, InstrumentRead, TransferCreate } from "../../api/client";
import { useCreateTransfer } from "../../api/queries";
import { toApiDateTime } from "../../lib/dates";

const CURRENCY_RE = /^[A-Za-z]{3}$/;
const AMOUNT_RE = /^\d+(\.\d+)?$/;

interface TransferFormValues {
  occurred_at: Date | null;
  from_account_id: string | null;
  to_account_id: string | null;
  instrument_id: string | null;
  quantity: string;
  currency: string;
}

export function TransferForm({
  accounts,
  instruments,
}: {
  accounts: AccountRead[];
  instruments: InstrumentRead[];
}) {
  const create = useCreateTransfer();
  const form = useForm<TransferFormValues>({
    initialValues: {
      occurred_at: new Date(),
      from_account_id: null,
      to_account_id: null,
      instrument_id: null,
      quantity: "",
      currency: "EUR",
    },
    validate: {
      occurred_at: (v) => (v ? null : "When did it happen?"),
      from_account_id: (v) => (v ? null : "Origin account is required"),
      to_account_id: (v, values) => {
        if (!v) return "Destination account is required";
        if (v === values.from_account_id) return "Destination must differ from origin";
        return null;
      },
      quantity: (v) => {
        if (!AMOUNT_RE.test(v)) return "Decimal amount, e.g. 1234.56";
        if (!/[1-9]/.test(v)) return "Must be greater than zero";
        return null;
      },
      currency: (v) => (CURRENCY_RE.test(v) ? null : "3-letter ISO code, e.g. EUR"),
    },
  });

  const accountOptions = accounts.map((a) => ({
    value: String(a.id),
    label: `${a.name} (${a.currency})`,
  }));

  const submit = form.onSubmit((values) => {
    const body: TransferCreate = {
      occurred_at: toApiDateTime(values.occurred_at!),
      from_account_id: Number(values.from_account_id),
      to_account_id: Number(values.to_account_id),
      quantity: values.quantity,
      currency: values.currency.toUpperCase(),
    };
    if (values.instrument_id) body.instrument_id = Number(values.instrument_id);

    create.mutate(body, {
      onSuccess: () => {
        notifications.show({ color: "green", message: "Transfer registered (two linked movements)" });
        form.setFieldValue("quantity", "");
      },
    });
  });

  return (
    <form onSubmit={submit}>
      <Stack>
        <DateTimePicker label="Occurred at" withAsterisk {...form.getInputProps("occurred_at")} />
        <Select
          label="From account"
          withAsterisk
          searchable
          data={accountOptions}
          {...form.getInputProps("from_account_id")}
          onChange={(value) => {
            form.setFieldValue("from_account_id", value);
            const account = accounts.find((a) => String(a.id) === value);
            if (account) form.setFieldValue("currency", account.currency);
          }}
        />
        <Select
          label="To account"
          withAsterisk
          searchable
          data={accountOptions}
          {...form.getInputProps("to_account_id")}
        />
        <Select
          label="Instrument (optional)"
          description="Leave empty for a cash transfer"
          searchable
          clearable
          data={instruments.map((i) => ({ value: String(i.id), label: i.name }))}
          {...form.getInputProps("instrument_id")}
        />
        <TextInput
          label="Quantity"
          withAsterisk
          inputMode="decimal"
          placeholder="0.00"
          {...form.getInputProps("quantity")}
        />
        <TextInput
          label="Currency"
          withAsterisk
          maxLength={3}
          {...form.getInputProps("currency")}
        />
        <Button type="submit" loading={create.isPending}>
          Register transfer
        </Button>
        <Text size="xs" c="dimmed">
          A transfer writes two linked movements (out + in) sharing a transfer id. A wire fee is
          a separate fee movement.
        </Text>
      </Stack>
    </form>
  );
}
