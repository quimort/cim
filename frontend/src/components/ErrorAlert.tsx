import { Alert, Button, Stack, Text } from "@mantine/core";

export function ErrorAlert({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Alert color="red" title="Something went wrong">
      <Stack gap="xs" align="flex-start">
        <Text size="sm">{message}</Text>
        {onRetry && (
          <Button variant="light" color="red" size="xs" onClick={onRetry}>
            Retry
          </Button>
        )}
      </Stack>
    </Alert>
  );
}
