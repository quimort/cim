import { useState } from "react";
import {
  ColorSwatch,
  Grid,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Dimension } from "../api/client";
import { useAllocation } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { QueryBoundary } from "../components/QueryBoundary";
import { formatDate, toApiDate } from "../lib/dates";
import { formatMoney, formatPercent, toChartNumber } from "../lib/money";

// Fixed-order categorical palette (dataviz reference, light mode) — hues are
// assigned by bucket position, never cycled. Sub-3:1 slots (aqua, yellow,
// magenta) are relieved by the side table, which doubles as the legend.
const CATEGORICAL = [
  "#2a78d6", // blue
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
  "#e87ba4", // magenta
  "#eb6834", // orange
];
const OTHER_COLOR = "#898781";
const MAX_SLICES = CATEGORICAL.length;

const DIMENSIONS: { value: Dimension; label: string }[] = [
  { value: "asset_class", label: "Asset class" },
  { value: "category", label: "Category" },
  { value: "currency", label: "Currency" },
  { value: "account", label: "Account" },
];

interface Slice {
  label: string;
  value: number;
  color: string;
  /** Original API string; null for the synthetic "Other" slice. */
  value_eur: string | null;
  weight: string | null;
  folded: number;
}

function DonutTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Slice }[];
}) {
  if (!active || !payload?.length) return null;
  const slice = payload[0].payload;
  return (
    <Paper withBorder shadow="sm" p="xs">
      <Text size="sm" fw={600}>
        {slice.label}
      </Text>
      {slice.value_eur !== null ? (
        <Text size="sm">
          {formatMoney(slice.value_eur, "EUR")}
          {slice.weight !== null && ` · ${formatPercent(slice.weight)}`}
        </Text>
      ) : (
        <Text size="sm" c="dimmed">
          {slice.folded} smaller buckets — see the table
        </Text>
      )}
    </Paper>
  );
}

export function AllocationPage() {
  const [dimension, setDimension] = useState<Dimension>("asset_class");
  const [asOf, setAsOf] = useState<Date | null>(null);
  const allocation = useAllocation(dimension, asOf ? toApiDate(asOf) : undefined);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Allocation</Title>
        <Group>
          <SegmentedControl
            value={dimension}
            onChange={(v) => setDimension(v as Dimension)}
            data={DIMENSIONS}
          />
          <DatePickerInput
            placeholder="As of today"
            clearable
            value={asOf}
            onChange={setAsOf}
            maxDate={new Date()}
          />
        </Group>
      </Group>
      <QueryBoundary query={allocation}>
        {(data) => {
          if (data.buckets.length === 0) {
            return <EmptyState message="Nothing to allocate — the ledger is empty for this date." />;
          }

          // Hues follow bucket position in the API's order; buckets beyond
          // the palette fold into a gray "Other" (never a 9th hue). The fold
          // sums plot coordinates only — exact figures stay in the table.
          const named = data.buckets.map((bucket, index) => ({
            label: bucket.key === null ? "Uncategorized" : bucket.label,
            value: toChartNumber(bucket.value_eur),
            color: CATEGORICAL[index] ?? OTHER_COLOR,
            value_eur: bucket.value_eur,
            weight: bucket.weight ?? null,
            folded: 0,
          }));
          const slices: Slice[] =
            named.length <= MAX_SLICES
              ? named
              : [
                  ...named.slice(0, MAX_SLICES - 1),
                  {
                    label: "Other",
                    value: named
                      .slice(MAX_SLICES - 1)
                      .reduce((sum, slice) => sum + slice.value, 0),
                    color: OTHER_COLOR,
                    value_eur: null,
                    weight: null,
                    folded: named.length - (MAX_SLICES - 1),
                  },
                ];

          return (
            <Grid>
              <Grid.Col span={{ base: 12, md: 5 }}>
                <Paper withBorder p="md">
                  <Stack gap={4}>
                    <Text size="sm" c="dimmed">
                      Total as of {formatDate(data.as_of)}
                    </Text>
                    <Text fz={28} fw={700}>
                      {formatMoney(data.total_eur, "EUR")}
                    </Text>
                    <div style={{ height: 280 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={slices}
                            dataKey="value"
                            nameKey="label"
                            innerRadius="55%"
                            outerRadius="85%"
                            stroke="var(--mantine-color-body)"
                            strokeWidth={2}
                            isAnimationActive={false}
                          >
                            {slices.map((slice) => (
                              <Cell key={slice.label} fill={slice.color} />
                            ))}
                          </Pie>
                          <Tooltip content={<DonutTooltip />} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </Stack>
                </Paper>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 7 }}>
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Bucket</Table.Th>
                      <Table.Th ta="right">Value (EUR)</Table.Th>
                      <Table.Th ta="right">Weight</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {data.buckets.map((bucket, index) => (
                      <Table.Tr key={bucket.key ?? "__uncategorized"}>
                        <Table.Td>
                          <Group gap="xs" wrap="nowrap">
                            <ColorSwatch
                              size={12}
                              color={
                                index < MAX_SLICES - 1 || data.buckets.length <= MAX_SLICES
                                  ? (CATEGORICAL[index] ?? OTHER_COLOR)
                                  : OTHER_COLOR
                              }
                            />
                            <Text size="sm">
                              {bucket.key === null ? "Uncategorized" : bucket.label}
                            </Text>
                          </Group>
                        </Table.Td>
                        <Table.Td ta="right">{formatMoney(bucket.value_eur, "EUR")}</Table.Td>
                        <Table.Td ta="right">
                          {bucket.weight === null || bucket.weight === undefined
                            ? "—"
                            : formatPercent(bucket.weight)}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Grid.Col>
            </Grid>
          );
        }}
      </QueryBoundary>
    </Stack>
  );
}
