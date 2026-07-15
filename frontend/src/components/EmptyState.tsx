import type { ReactNode } from "react";
import { Center, Stack, Text } from "@mantine/core";

export function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: ReactNode;
}) {
  return (
    <Center py="xl">
      <Stack align="center" gap="sm">
        <Text c="dimmed">{message}</Text>
        {action}
      </Stack>
    </Center>
  );
}
