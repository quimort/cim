import { useState } from "react";
import {
  Badge,
  Button,
  Checkbox,
  Group,
  Modal,
  Stack,
  Switch,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import type { AccountRead } from "../api/client";
import { useAccounts, useCreateAccount, useUpdateAccount } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { QueryBoundary } from "../components/QueryBoundary";
import { formatDate } from "../lib/dates";

const CURRENCY_RE = /^[A-Za-z]{3}$/;

function CreateAccountModal({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) {
  const create = useCreateAccount();
  const form = useForm({
    initialValues: { name: "", type: "", currency: "EUR" },
    validate: {
      name: (v) => (v.trim() ? null : "Name is required"),
      type: (v) => (v.trim() ? null : "Type is required"),
      currency: (v) => (CURRENCY_RE.test(v) ? null : "3-letter ISO code, e.g. EUR"),
    },
  });

  const submit = form.onSubmit((values) => {
    create.mutate(
      {
        name: values.name.trim(),
        type: values.type.trim(),
        currency: values.currency.toUpperCase(),
      },
      {
        onSuccess: (account) => {
          notifications.show({ color: "green", message: `Account "${account.name}" created` });
          form.reset();
          onClose();
        },
      },
    );
  });

  return (
    <Modal opened={opened} onClose={onClose} title="New account">
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Name" withAsterisk {...form.getInputProps("name")} />
          <TextInput
            label="Type"
            withAsterisk
            placeholder="broker / bank / exchange"
            {...form.getInputProps("type")}
          />
          <TextInput
            label="Currency"
            withAsterisk
            maxLength={3}
            description="Fixed for the account's lifetime"
            {...form.getInputProps("currency")}
          />
          <Button type="submit" loading={create.isPending}>
            Create
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

function EditAccountModal({
  account,
  onClose,
}: {
  account: AccountRead;
  onClose: () => void;
}) {
  const update = useUpdateAccount();
  const form = useForm({
    initialValues: { name: account.name, type: account.type, is_active: account.is_active },
    validate: {
      name: (v) => (v.trim() ? null : "Name is required"),
      type: (v) => (v.trim() ? null : "Type is required"),
    },
  });

  const submit = form.onSubmit((values) => {
    update.mutate(
      {
        id: account.id,
        body: { name: values.name.trim(), type: values.type.trim(), is_active: values.is_active },
      },
      {
        onSuccess: (updated) => {
          notifications.show({ color: "green", message: `Account "${updated.name}" updated` });
          onClose();
        },
      },
    );
  });

  return (
    <Modal opened onClose={onClose} title={`Edit account — ${account.name}`}>
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Name" withAsterisk {...form.getInputProps("name")} />
          <TextInput label="Type" withAsterisk {...form.getInputProps("type")} />
          <TextInput label="Currency" value={account.currency} disabled description="Immutable" />
          <Switch
            label="Active"
            description="Deactivating hides the account from forms; its history stays"
            {...form.getInputProps("is_active", { type: "checkbox" })}
          />
          <Button type="submit" loading={update.isPending}>
            Save
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

export function AccountsPage() {
  const [includeInactive, setIncludeInactive] = useState(false);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [editing, setEditing] = useState<AccountRead | null>(null);
  const accounts = useAccounts(includeInactive);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Accounts</Title>
        <Button onClick={openCreate}>New account</Button>
      </Group>
      <Checkbox
        label="Include inactive"
        checked={includeInactive}
        onChange={(e) => setIncludeInactive(e.currentTarget.checked)}
      />
      <QueryBoundary query={accounts}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState
              message="No accounts yet — an account is where money or assets live."
              action={<Button onClick={openCreate}>Create your first account</Button>}
            />
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Currency</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((account) => (
                  <Table.Tr key={account.id}>
                    <Table.Td>{account.name}</Table.Td>
                    <Table.Td>{account.type}</Table.Td>
                    <Table.Td>{account.currency}</Table.Td>
                    <Table.Td>
                      <Badge color={account.is_active ? "green" : "gray"} variant="light">
                        {account.is_active ? "active" : "inactive"}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{formatDate(account.created_at)}</Table.Td>
                    <Table.Td>
                      <Button size="compact-xs" variant="subtle" onClick={() => setEditing(account)}>
                        Edit
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )
        }
      </QueryBoundary>
      <CreateAccountModal opened={createOpened} onClose={closeCreate} />
      {editing && <EditAccountModal account={editing} onClose={() => setEditing(null)} />}
    </Stack>
  );
}
