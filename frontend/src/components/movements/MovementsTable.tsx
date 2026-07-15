import { useState } from "react";
import {
  Badge,
  Button,
  Checkbox,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import type { AccountRead, InstrumentRead, MovementRead, MovementType } from "../../api/client";
import { useMovements, useVoidMovement } from "../../api/queries";
import { EmptyState } from "../../components/EmptyState";
import { QueryBoundary } from "../../components/QueryBoundary";
import { dayEndIso, dayStartIso, formatDateTime } from "../../lib/dates";
import { formatMoney, formatQuantity } from "../../lib/money";
import { CREATABLE_MOVEMENT_TYPES } from "../../lib/movementRules";

const PAGE_SIZE = 100;

const TYPE_FILTER_OPTIONS: MovementType[] = [
  ...CREATABLE_MOVEMENT_TYPES,
  "transfer_out",
  "transfer_in",
];

export function MovementsTable({
  accounts,
  instruments,
}: {
  accounts: AccountRead[];
  instruments: InstrumentRead[];
}) {
  const [accountId, setAccountId] = useState<string | null>(null);
  const [instrumentId, setInstrumentId] = useState<string | null>(null);
  const [type, setType] = useState<string | null>(null);
  const [range, setRange] = useState<[Date | null, Date | null]>([null, null]);
  const [includeVoided, setIncludeVoided] = useState(false);
  const [offset, setOffset] = useState(0);
  const [voiding, setVoiding] = useState<MovementRead | null>(null);
  const voidMovement = useVoidMovement();

  const movements = useMovements({
    ...(accountId && { account_id: Number(accountId) }),
    ...(instrumentId && { instrument_id: Number(instrumentId) }),
    ...(type && { type: type as MovementType }),
    ...(range[0] && { occurred_from: dayStartIso(range[0]) }),
    ...(range[1] && { occurred_to: dayEndIso(range[1]) }),
    include_voided: includeVoided,
    limit: PAGE_SIZE,
    offset,
  });

  const accountName = (id: number) =>
    accounts.find((a) => a.id === id)?.name ?? `account #${id}`;
  const instrumentName = (id: number | null) =>
    id === null ? "—" : (instruments.find((i) => i.id === id)?.name ?? `instrument #${id}`);

  const resetPaging = () => setOffset(0);

  return (
    <Stack>
      <Group>
        <Select
          placeholder="All accounts"
          searchable
          clearable
          data={accounts.map((a) => ({ value: String(a.id), label: a.name }))}
          value={accountId}
          onChange={(v) => (setAccountId(v), resetPaging())}
        />
        <Select
          placeholder="All instruments"
          searchable
          clearable
          data={instruments.map((i) => ({ value: String(i.id), label: i.name }))}
          value={instrumentId}
          onChange={(v) => (setInstrumentId(v), resetPaging())}
        />
        <Select
          placeholder="All types"
          clearable
          data={TYPE_FILTER_OPTIONS}
          value={type}
          onChange={(v) => (setType(v), resetPaging())}
        />
        <DatePickerInput
          type="range"
          placeholder="Date range"
          clearable
          value={range}
          onChange={(v) => (setRange(v), resetPaging())}
        />
        <Checkbox
          label="Include annulled"
          checked={includeVoided}
          onChange={(e) => (setIncludeVoided(e.currentTarget.checked), resetPaging())}
        />
      </Group>
      <QueryBoundary query={movements}>
        {(rows) =>
          rows.length === 0 && offset === 0 ? (
            <EmptyState message="No movements match. Register the first one with the form above." />
          ) : (
            <>
              <Table.ScrollContainer minWidth={900}>
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Occurred</Table.Th>
                      <Table.Th>Type</Table.Th>
                      <Table.Th>Account</Table.Th>
                      <Table.Th>Instrument</Table.Th>
                      <Table.Th ta="right">Quantity</Table.Th>
                      <Table.Th ta="right">Price</Table.Th>
                      <Table.Th ta="right">Fee</Table.Th>
                      <Table.Th>Currency</Table.Th>
                      <Table.Th />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {rows.map((movement) => {
                      const voided = movement.voided_at !== null;
                      const dim = voided
                        ? { c: "dimmed" as const, td: "line-through" as const }
                        : {};
                      return (
                        <Table.Tr key={movement.id} opacity={voided ? 0.6 : 1}>
                          <Table.Td>
                            <Text size="sm" {...dim}>
                              {formatDateTime(movement.occurred_at)}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Group gap={4} wrap="nowrap">
                              <Badge variant="light">{movement.type}</Badge>
                              {movement.transfer_id && (
                                <Badge variant="outline" color="grape" title={movement.transfer_id}>
                                  linked
                                </Badge>
                              )}
                              {voided && (
                                <Badge variant="outline" color="gray">
                                  annulled
                                </Badge>
                              )}
                            </Group>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" {...dim}>
                              {accountName(movement.account_id)}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" {...dim}>
                              {instrumentName(movement.instrument_id)}
                            </Text>
                          </Table.Td>
                          <Table.Td ta="right">
                            <Text size="sm" {...dim}>
                              {formatQuantity(movement.quantity)}
                            </Text>
                          </Table.Td>
                          <Table.Td ta="right">
                            <Text size="sm" {...dim}>
                              {movement.price ? formatMoney(movement.price, movement.currency) : "—"}
                            </Text>
                          </Table.Td>
                          <Table.Td ta="right">
                            <Text size="sm" {...dim}>
                              {movement.fee ? formatMoney(movement.fee, movement.currency) : "—"}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" {...dim}>
                              {movement.currency}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            {!voided && (
                              <Button
                                size="compact-xs"
                                variant="subtle"
                                color="red"
                                onClick={() => setVoiding(movement)}
                              >
                                Annul
                              </Button>
                            )}
                          </Table.Td>
                        </Table.Tr>
                      );
                    })}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
              <Group justify="flex-end">
                <Button
                  variant="default"
                  size="xs"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="default"
                  size="xs"
                  disabled={rows.length < PAGE_SIZE}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </Group>
            </>
          )
        }
      </QueryBoundary>
      <Modal opened={voiding !== null} onClose={() => setVoiding(null)} title="Annul movement">
        <Stack>
          <Text size="sm">
            The ledger is immutable: annulling voids this movement without deleting it. To correct
            a mistake, annul and re-enter.
            {voiding?.transfer_id && " This is a transfer leg — annulling it voids both legs."}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setVoiding(null)}>
              Cancel
            </Button>
            <Button
              color="red"
              loading={voidMovement.isPending}
              onClick={() => {
                if (!voiding) return;
                voidMovement.mutate(voiding.id, {
                  onSuccess: () => {
                    notifications.show({ color: "green", message: "Movement annulled" });
                    setVoiding(null);
                  },
                });
              }}
            >
              Annul
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
