import type { ReactNode } from "react";
import { Center, Loader } from "@mantine/core";
import type { UseQueryResult } from "@tanstack/react-query";
import { ErrorAlert } from "./ErrorAlert";

/**
 * Standard loading / error / data states for a query. Every page wraps its
 * queries in this so errors always render inline with a retry.
 */
export function QueryBoundary<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }
  if (query.isError) {
    return (
      <ErrorAlert
        message={query.error instanceof Error ? query.error.message : String(query.error)}
        onRetry={() => void query.refetch()}
      />
    );
  }
  return <>{children(query.data)}</>;
}
