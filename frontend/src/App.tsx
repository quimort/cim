import { MantineProvider, Text } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { AccountsPage } from "./pages/AccountsPage";
import { AllocationPage } from "./pages/AllocationPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InstrumentsPage } from "./pages/InstrumentsPage";
import { MovementsPage } from "./pages/MovementsPage";
import { PositionsPage } from "./pages/PositionsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/movements", element: <MovementsPage /> },
      { path: "/positions", element: <PositionsPage /> },
      { path: "/allocation", element: <AllocationPage /> },
      { path: "/accounts", element: <AccountsPage /> },
      { path: "/instruments", element: <InstrumentsPage /> },
      { path: "*", element: <Text>Page not found.</Text> },
    ],
  },
]);

export default function App() {
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </MantineProvider>
  );
}
