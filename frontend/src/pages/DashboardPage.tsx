import { useState } from "react";
import {
  Anchor,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import dayjs from "dayjs";
import type { Interval, NetWorthRead } from "../api/client";
import {
  useAccounts,
  useInstruments,
  useNetWorth,
  useNetWorthSeries,
  type SeriesParams,
} from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { QueryBoundary } from "../components/QueryBoundary";
import { formatDate, toApiDate } from "../lib/dates";
import { formatMoney, isNegative, toChartNumber } from "../lib/money";

// Chart chrome (dataviz reference palette, light mode).
const SERIES_COLOR = "#2a78d6";
const GRID_COLOR = "#e1e0d9";
const AXIS_INK = "#898781";

type RangePreset = "3m" | "1y" | "all";

// Axis ticks are scale machinery, not money data — compact notation is fine.
const tickFormatter = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

function SeriesTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { as_of: string; total_eur: string } }[];
}) {
  if (!active || !payload?.length) return null;
  const datum = payload[0].payload;
  return (
    <Paper withBorder shadow="sm" p="xs">
      <Text size="xs" c="dimmed">
        {formatDate(datum.as_of)}
      </Text>
      {/* Formatted from the original string — never from the plot float. */}
      <Text size="sm" fw={600}>
        {formatMoney(datum.total_eur, "EUR")}
      </Text>
    </Paper>
  );
}

function NetWorthChart() {
  const [interval, setInterval] = useState<Interval>("month");
  const [preset, setPreset] = useState<RangePreset>("1y");

  const params: SeriesParams = { interval };
  if (preset !== "all") {
    const months = preset === "3m" ? 3 : 12;
    params.from = toApiDate(dayjs().subtract(months, "month").toDate());
  }
  const series = useNetWorthSeries(params);

  return (
    <Paper withBorder p="md">
      <Stack>
        <Group justify="space-between">
          <Title order={4}>Evolution</Title>
          <Group>
            <SegmentedControl
              size="xs"
              value={preset}
              onChange={(v) => setPreset(v as RangePreset)}
              data={[
                { value: "3m", label: "3m" },
                { value: "1y", label: "1y" },
                { value: "all", label: "All" },
              ]}
            />
            <SegmentedControl
              size="xs"
              value={interval}
              onChange={(v) => setInterval(v as Interval)}
              data={["day", "week", "month"]}
            />
          </Group>
        </Group>
        <QueryBoundary query={series}>
          {(data) => (
            <>
              {/* ResponsiveContainer needs an explicit-height parent. */}
              <div style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={data.points.map((p) => ({ ...p, value: toChartNumber(p.total_eur) }))}
                    margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
                  >
                    <CartesianGrid stroke={GRID_COLOR} vertical={false} />
                    <XAxis
                      dataKey="as_of"
                      tick={{ fill: AXIS_INK, fontSize: 12 }}
                      tickLine={false}
                      axisLine={{ stroke: GRID_COLOR }}
                    />
                    <YAxis
                      tick={{ fill: AXIS_INK, fontSize: 12 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v: number) => tickFormatter.format(v)}
                      width={60}
                    />
                    <Tooltip content={<SeriesTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={SERIES_COLOR}
                      strokeWidth={2}
                      fill={SERIES_COLOR}
                      fillOpacity={0.12}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {data.points.length < 2 && (
                <Text size="xs" c="dimmed">
                  Not enough history yet — the chart fills in as movements accumulate.
                </Text>
              )}
            </>
          )}
        </QueryBoundary>
      </Stack>
    </Paper>
  );
}

function BreakdownTable({ netWorth }: { netWorth: NetWorthRead }) {
  const accounts = useAccounts(true);
  const instruments = useInstruments({ include_inactive: true });

  const accountName = (id: number | null) =>
    id === null ? "—" : (accounts.data?.find((a) => a.id === id)?.name ?? `account #${id}`);
  const instrumentName = (id: number | null) =>
    id === null ? null : (instruments.data?.find((i) => i.id === id)?.name ?? `instrument #${id}`);

  return (
    <Table.ScrollContainer minWidth={700}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Asset class</Table.Th>
            <Table.Th>Holding</Table.Th>
            <Table.Th ta="right">Native value</Table.Th>
            <Table.Th ta="right">Unrealized P&amp;L</Table.Th>
            <Table.Th ta="right">Value (EUR)</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {netWorth.items.map((item, index) => (
            <Table.Tr key={index}>
              <Table.Td>{item.asset_class}</Table.Td>
              <Table.Td>{instrumentName(item.instrument_id) ?? accountName(item.account_id)}</Table.Td>
              <Table.Td ta="right">
                {formatMoney(item.native_value, item.native_currency)}
              </Table.Td>
              <Table.Td ta="right">
                {item.unrealized_pnl === null || item.unrealized_pnl === undefined ? (
                  "—"
                ) : (
                  <Text size="sm" c={isNegative(item.unrealized_pnl) ? "red" : "teal"}>
                    {formatMoney(item.unrealized_pnl, item.native_currency)}
                  </Text>
                )}
              </Table.Td>
              <Table.Td ta="right">{formatMoney(item.value_eur, "EUR")}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

export function DashboardPage() {
  const [asOf, setAsOf] = useState<Date | null>(null);
  const netWorth = useNetWorth(asOf ? toApiDate(asOf) : undefined);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Dashboard</Title>
        <DatePickerInput
          placeholder="As of today"
          clearable
          value={asOf}
          onChange={setAsOf}
          maxDate={new Date()}
        />
      </Group>
      <QueryBoundary query={netWorth}>
        {(data) => (
          <Stack>
            <Paper withBorder p="md">
              <Text size="sm" c="dimmed">
                Net worth as of {formatDate(data.as_of)}
              </Text>
              <Text fz={40} fw={700}>
                {/* The endpoint is defined in EUR — but the code still reads it as a currency. */}
                {formatMoney(data.total_eur, "EUR")}
              </Text>
            </Paper>
            <NetWorthChart />
            {data.items.length === 0 ? (
              <EmptyState
                message="Nothing in the ledger yet."
                action={
                  <Anchor component={Link} to="/movements">
                    Register your first movement
                  </Anchor>
                }
              />
            ) : (
              <BreakdownTable netWorth={data} />
            )}
          </Stack>
        )}
      </QueryBoundary>
    </Stack>
  );
}
