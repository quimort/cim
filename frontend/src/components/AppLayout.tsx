import { AppShell, Burger, Group, NavLink, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { NavLink as RouterNavLink, Outlet, useLocation } from "react-router-dom";

const LINKS = [
  { to: "/", label: "Dashboard" },
  { to: "/movements", label: "Movements" },
  { to: "/positions", label: "Positions" },
  { to: "/allocation", label: "Allocation" },
  { to: "/accounts", label: "Accounts" },
  { to: "/instruments", label: "Instruments" },
];

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure();
  const location = useLocation();

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
          <Title order={4}>Capital &amp; Investments</Title>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            component={RouterNavLink}
            to={link.to}
            label={link.label}
            active={location.pathname === link.to}
            onClick={close}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
