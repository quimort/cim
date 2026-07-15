import { useState } from "react";
import { Grid, Paper, SegmentedControl, Stack, Title } from "@mantine/core";
import { useAccounts, useInstruments } from "../api/queries";
import { MovementForm } from "../components/movements/MovementForm";
import { MovementsTable } from "../components/movements/MovementsTable";
import { TransferForm } from "../components/movements/TransferForm";
import { QueryBoundary } from "../components/QueryBoundary";

export function MovementsPage() {
  const [mode, setMode] = useState<"movement" | "transfer">("movement");
  // Forms offer only active accounts/instruments; the table resolves names
  // for inactive ones too, so it loads everything.
  const activeAccounts = useAccounts(false);
  const activeInstruments = useInstruments({});
  const allAccounts = useAccounts(true);
  const allInstruments = useInstruments({ include_inactive: true });

  return (
    <Stack>
      <Title order={2}>Movements</Title>
      <Grid>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper withBorder p="md">
            <Stack>
              <SegmentedControl
                fullWidth
                value={mode}
                onChange={(value) => setMode(value as "movement" | "transfer")}
                data={[
                  { value: "movement", label: "Movement" },
                  { value: "transfer", label: "Transfer" },
                ]}
              />
              <QueryBoundary query={activeAccounts}>
                {(accounts) => (
                  <QueryBoundary query={activeInstruments}>
                    {(instruments) =>
                      mode === "movement" ? (
                        <MovementForm accounts={accounts} instruments={instruments} />
                      ) : (
                        <TransferForm accounts={accounts} instruments={instruments} />
                      )
                    }
                  </QueryBoundary>
                )}
              </QueryBoundary>
            </Stack>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <MovementsTable
            accounts={allAccounts.data ?? []}
            instruments={allInstruments.data ?? []}
          />
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
