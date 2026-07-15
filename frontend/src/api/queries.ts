/**
 * TanStack Query hooks — the only place the app talks to the API.
 *
 * Queries render errors inline (see QueryBoundary); mutations surface the
 * backend's `detail` in a notification by default. Every ledger write
 * invalidates all derived views: that is the payoff of deriving everything
 * from the immutable ledger instead of storing state.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { notifications } from "@mantine/notifications";
import {
  client,
  unwrap,
  type AccountCreate,
  type AccountUpdate,
  type CategoryCreate,
  type CategoryUpdate,
  type Dimension,
  type InstrumentCreate,
  type InstrumentUpdate,
  type MovementCreate,
  type TransferCreate,
} from "./client";
import type { paths } from "./schema";

export type InstrumentFilters = NonNullable<
  paths["/api/instruments"]["get"]["parameters"]["query"]
>;
export type MovementFilters = NonNullable<
  paths["/api/movements"]["get"]["parameters"]["query"]
>;
export type PositionParams = NonNullable<
  paths["/api/positions"]["get"]["parameters"]["query"]
>;
export type SeriesParams = NonNullable<
  paths["/api/net-worth/series"]["get"]["parameters"]["query"]
>;

export function notifyApiError(error: unknown): void {
  notifications.show({
    color: "red",
    title: "Request failed",
    message: error instanceof Error ? error.message : String(error),
  });
}

/** Everything computed from the ledger. Call after any movement write. */
export function invalidateLedgerDerived(queryClient: QueryClient): void {
  for (const key of ["movements", "positions", "net-worth", "net-worth-series", "allocation"]) {
    void queryClient.invalidateQueries({ queryKey: [key] });
  }
}

// ---------------------------------------------------------------- queries

export function useAccounts(includeInactive = false) {
  return useQuery({
    queryKey: ["accounts", { includeInactive }],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/accounts", {
          params: { query: { include_inactive: includeInactive } },
        }),
      ),
  });
}

export function useInstruments(filters: InstrumentFilters = {}) {
  return useQuery({
    queryKey: ["instruments", filters],
    queryFn: async () =>
      unwrap(await client.GET("/api/instruments", { params: { query: filters } })),
  });
}

export function useCategories(includeInactive = false) {
  return useQuery({
    queryKey: ["categories", { includeInactive }],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/categories", {
          params: { query: { include_inactive: includeInactive } },
        }),
      ),
  });
}

export function useAssetClasses() {
  return useQuery({
    queryKey: ["asset-classes"],
    // Seeded reference data — changes only via a migration, never at runtime.
    staleTime: Infinity,
    queryFn: async () => unwrap(await client.GET("/api/asset-classes")),
  });
}

export function useMovements(filters: MovementFilters = {}) {
  return useQuery({
    queryKey: ["movements", filters],
    queryFn: async () =>
      unwrap(await client.GET("/api/movements", { params: { query: filters } })),
  });
}

export function usePositions(params: PositionParams = {}) {
  return useQuery({
    queryKey: ["positions", params],
    queryFn: async () =>
      unwrap(await client.GET("/api/positions", { params: { query: params } })),
  });
}

export function useNetWorth(date?: string) {
  return useQuery({
    queryKey: ["net-worth", date ?? null],
    queryFn: async () =>
      unwrap(await client.GET("/api/net-worth", { params: { query: { date } } })),
  });
}

export function useNetWorthSeries(params: SeriesParams = {}) {
  return useQuery({
    queryKey: ["net-worth-series", params],
    queryFn: async () =>
      unwrap(await client.GET("/api/net-worth/series", { params: { query: params } })),
  });
}

export function useAllocation(by: Dimension, date?: string) {
  return useQuery({
    queryKey: ["allocation", by, date ?? null],
    queryFn: async () =>
      unwrap(await client.GET("/api/allocation", { params: { query: { by, date } } })),
  });
}

// -------------------------------------------------------------- mutations

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AccountCreate) =>
      unwrap(await client.POST("/api/accounts", { body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["accounts"] }),
    onError: notifyApiError,
  });
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: AccountUpdate }) =>
      unwrap(
        await client.PATCH("/api/accounts/{account_id}", {
          params: { path: { account_id: id } },
          body,
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["accounts"] }),
    onError: notifyApiError,
  });
}

export function useCreateInstrument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: InstrumentCreate) =>
      unwrap(await client.POST("/api/instruments", { body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["instruments"] }),
    onError: notifyApiError,
  });
}

export function useUpdateInstrument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: InstrumentUpdate }) =>
      unwrap(
        await client.PATCH("/api/instruments/{instrument_id}", {
          params: { path: { instrument_id: id } },
          body,
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["instruments"] });
      // Renames show up in positions/net-worth breakdowns.
      invalidateLedgerDerived(queryClient);
    },
    onError: notifyApiError,
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CategoryCreate) =>
      unwrap(await client.POST("/api/categories", { body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["categories"] }),
    onError: notifyApiError,
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: CategoryUpdate }) =>
      unwrap(
        await client.PATCH("/api/categories/{category_id}", {
          params: { path: { category_id: id } },
          body,
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["categories"] });
      void queryClient.invalidateQueries({ queryKey: ["instruments"] });
      void queryClient.invalidateQueries({ queryKey: ["allocation"] });
    },
    onError: notifyApiError,
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/categories/{category_id}", {
          params: { path: { category_id: id } },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["categories"] });
      void queryClient.invalidateQueries({ queryKey: ["instruments"] });
      void queryClient.invalidateQueries({ queryKey: ["allocation"] });
    },
    onError: notifyApiError,
  });
}

export function useCreateMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: MovementCreate) =>
      unwrap(await client.POST("/api/movements", { body })),
    onSuccess: () => invalidateLedgerDerived(queryClient),
    onError: notifyApiError,
  });
}

export function useCreateTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: TransferCreate) =>
      unwrap(await client.POST("/api/movements/transfer", { body })),
    onSuccess: () => invalidateLedgerDerived(queryClient),
    onError: notifyApiError,
  });
}

/** The only "edit" the ledger allows: annulment. Correct = void + re-enter. */
export function useVoidMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/movements/{movement_id}", {
          params: { path: { movement_id: id } },
        }),
      ),
    onSuccess: () => invalidateLedgerDerived(queryClient),
    onError: notifyApiError,
  });
}
