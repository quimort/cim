import { useState } from "react";
import { Anchor, Checkbox, Group, Stack, Table, Text, Title, Tooltip } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { Link } from "react-router-dom";
import { usePositions } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { QueryBoundary } from "../components/QueryBoundary";
import { toApiDate } from "../lib/dates";
import { formatMoney, formatQuantity, isNegative } from "../lib/money";

function PnlText({ value, currency }: { value: string | null | undefined; currency: string }) {
  if (value === null || value === undefined) return <Text size="sm">—</Text>;
  return (
    <Text size="sm" c={isNegative(value) ? "red" : "teal"}>
      {formatMoney(value, currency)}
    </Text>
  );
}

function MaybeMoney({ value, currency }: { value: string | null | undefined; currency: string }) {
  if (value === null || value === undefined) {
    return (
      <Tooltip label="No market price for this date, or the position is closed">
        <Text size="sm" c="dimmed">
          —
        </Text>
      </Tooltip>
    );
  }
  return <Text size="sm">{formatMoney(value, currency)}</Text>;
}

export function PositionsPage() {
  const [asOf, setAsOf] = useState<Date | null>(null);
  const [includeClosed, setIncludeClosed] = useState(false);

  const positions = usePositions({
    ...(asOf && { date: toApiDate(asOf) }),
    include_closed: includeClosed,
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Positions</Title>
        <Group>
          <DatePickerInput
            placeholder="As of today"
            clearable
            value={asOf}
            onChange={setAsOf}
            maxDate={new Date()}
          />
          <Checkbox
            label="Include closed"
            checked={includeClosed}
            onChange={(e) => setIncludeClosed(e.currentTarget.checked)}
          />
        </Group>
      </Group>
      <QueryBoundary query={positions}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState
              message="No positions — positions are derived from the ledger."
              action={
                <Anchor component={Link} to="/movements">
                  Register a purchase first
                </Anchor>
              }
            />
          ) : (
            <Table.ScrollContainer minWidth={900}>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Instrument</Table.Th>
                    <Table.Th ta="right">Quantity</Table.Th>
                    <Table.Th ta="right">Cost basis</Table.Th>
                    <Table.Th ta="right">Market value</Table.Th>
                    <Table.Th ta="right">Unrealized P&amp;L</Table.Th>
                    <Table.Th ta="right">Realized P&amp;L</Table.Th>
                    <Table.Th>Currency</Table.Th>
                    <Table.Th ta="right">Value (EUR)</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((position) => (
                    <Table.Tr key={position.instrument_id}>
                      <Table.Td>{position.instrument_name}</Table.Td>
                      <Table.Td ta="right">{formatQuantity(position.quantity)}</Table.Td>
                      <Table.Td ta="right">
                        {formatMoney(position.cost_basis, position.currency)}
                      </Table.Td>
                      <Table.Td ta="right">
                        <MaybeMoney value={position.market_value} currency={position.currency} />
                      </Table.Td>
                      <Table.Td ta="right">
                        <PnlText value={position.unrealized_pnl} currency={position.currency} />
                      </Table.Td>
                      <Table.Td ta="right">
                        <PnlText value={position.realized_pnl} currency={position.currency} />
                      </Table.Td>
                      <Table.Td>{position.currency}</Table.Td>
                      <Table.Td ta="right">
                        <MaybeMoney value={position.value_eur} currency="EUR" />
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )
        }
      </QueryBoundary>
    </Stack>
  );
}
