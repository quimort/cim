import { useState } from "react";
import {
  Badge,
  Button,
  Checkbox,
  Group,
  Modal,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { useForm, type UseFormReturnType } from "@mantine/form";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import type {
  AssetClass,
  CategoryRead,
  InstrumentCreate,
  InstrumentRead,
  LoanStatus,
  PriceSource,
} from "../api/client";
import {
  useAssetClasses,
  useCategories,
  useCreateCategory,
  useCreateInstrument,
  useDeleteCategory,
  useInstruments,
  useUpdateCategory,
  useUpdateInstrument,
  type InstrumentFilters,
} from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { QueryBoundary } from "../components/QueryBoundary";
import { formatDate, toApiDate } from "../lib/dates";

const CURRENCY_RE = /^[A-Za-z]{3}$/;
const MONEY_RE = /^\d+(\.\d+)?$/;
const LOAN_STATUSES: LoanStatus[] = ["active", "repaid", "defaulted"];
const PRICE_SOURCES: PriceSource[] = ["yfinance", "coingecko"];

interface InstrumentFormValues {
  name: string;
  symbol: string;
  asset_class: AssetClass;
  currency: string;
  category_id: string | null;
  maturity_date: Date | null;
  expected_interest: string;
  status: LoanStatus | null;
  price_source: PriceSource | null;
  provider_ref: string;
  is_active: boolean;
}

type InstrumentForm = UseFormReturnType<InstrumentFormValues>;

/** Validators shared by the create and edit forms. */
const instrumentValidators = {
  name: (v: string) => (v.trim() ? null : "Name is required"),
  expected_interest: (v: string) =>
    v && !MONEY_RE.test(v) ? "Decimal amount, e.g. 150.00" : null,
  price_source: (v: PriceSource | null, values: InstrumentFormValues) =>
    values.asset_class === "tradable" && !!v !== !!values.provider_ref.trim()
      ? "price_source and provider_ref go together"
      : null,
};

/** Clear the fields the selected asset class forbids. */
function clearForbiddenFields(
  form: { setFieldValue: (field: string, value: unknown) => void },
  assetClass: AssetClass,
) {
  if (assetClass !== "loan") {
    form.setFieldValue("maturity_date", null);
    form.setFieldValue("expected_interest", "");
    form.setFieldValue("status", null);
  }
  if (assetClass !== "tradable") {
    form.setFieldValue("price_source", null);
    form.setFieldValue("provider_ref", "");
  }
}

function LoanFields({ form }: { form: InstrumentForm }) {
  return (
    <>
      <DatePickerInput
        label="Maturity date"
        clearable
        {...form.getInputProps("maturity_date")}
      />
      <TextInput
        label="Expected interest"
        placeholder="150.00"
        inputMode="decimal"
        {...form.getInputProps("expected_interest")}
      />
      <Select
        label="Status"
        data={LOAN_STATUSES}
        clearable
        placeholder="active (default)"
        {...form.getInputProps("status")}
      />
    </>
  );
}

function PricingFields({ form }: { form: InstrumentForm }) {
  return (
    <>
      <Select
        label="Price source"
        description="Provider the price batch script fetches quotes from"
        data={PRICE_SOURCES}
        clearable
        {...form.getInputProps("price_source")}
      />
      <TextInput
        label="Provider ref"
        description="yfinance ticker (VWCE.DE) or CoinGecko coin id (bitcoin)"
        {...form.getInputProps("provider_ref")}
      />
    </>
  );
}

function CategorySelect({
  categories,
  form,
}: {
  categories: CategoryRead[];
  form: InstrumentForm;
}) {
  return (
    <Select
      label="Category"
      description="How you want to see it grouped — never affects valuation"
      placeholder={categories.length === 0 ? "No categories yet (optional)" : "Uncategorized"}
      data={categories.map((c) => ({ value: String(c.id), label: c.name }))}
      clearable
      searchable
      {...form.getInputProps("category_id")}
    />
  );
}

function CreateInstrumentModal({
  opened,
  onClose,
  categories,
  assetClasses,
}: {
  opened: boolean;
  onClose: () => void;
  categories: CategoryRead[];
  assetClasses: { value: string; label: string }[];
}) {
  const create = useCreateInstrument();
  const form = useForm<InstrumentFormValues>({
    initialValues: {
      name: "",
      symbol: "",
      asset_class: "tradable",
      currency: "EUR",
      category_id: null,
      maturity_date: null,
      expected_interest: "",
      status: null,
      price_source: null,
      provider_ref: "",
      is_active: true,
    },
    validate: {
      ...instrumentValidators,
      currency: (v) => (CURRENCY_RE.test(v) ? null : "3-letter ISO code, e.g. EUR"),
    },
  });

  const submit = form.onSubmit((values) => {
    const body: InstrumentCreate = {
      name: values.name.trim(),
      symbol: values.symbol.trim() || null,
      asset_class: values.asset_class,
      currency: values.currency.toUpperCase(),
      category_id: values.category_id ? Number(values.category_id) : null,
    };
    if (values.asset_class === "loan") {
      body.maturity_date = values.maturity_date ? toApiDate(values.maturity_date) : null;
      body.expected_interest = values.expected_interest || null;
      body.status = values.status;
    }
    if (values.asset_class === "tradable" && values.price_source) {
      body.price_source = values.price_source;
      body.provider_ref = values.provider_ref.trim();
    }
    create.mutate(body, {
      onSuccess: (instrument) => {
        notifications.show({ color: "green", message: `Instrument "${instrument.name}" created` });
        form.reset();
        onClose();
      },
    });
  });

  return (
    <Modal opened={opened} onClose={onClose} title="New instrument">
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Name" withAsterisk {...form.getInputProps("name")} />
          <TextInput
            label="Symbol"
            placeholder="Ticker or ISIN (optional)"
            {...form.getInputProps("symbol")}
          />
          <Select
            label="Asset class"
            description="How it's valued. Fixed for the instrument's lifetime"
            withAsterisk
            data={assetClasses}
            allowDeselect={false}
            {...form.getInputProps("asset_class")}
            onChange={(value) => {
              if (!value) return;
              form.setFieldValue("asset_class", value as AssetClass);
              clearForbiddenFields(form, value as AssetClass);
            }}
          />
          <TextInput label="Currency" withAsterisk maxLength={3} {...form.getInputProps("currency")} />
          <CategorySelect categories={categories} form={form} />
          {form.values.asset_class === "loan" && <LoanFields form={form} />}
          {form.values.asset_class === "tradable" && <PricingFields form={form} />}
          <Button type="submit" loading={create.isPending}>
            Create
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

function EditInstrumentModal({
  instrument,
  onClose,
  categories,
}: {
  instrument: InstrumentRead;
  onClose: () => void;
  categories: CategoryRead[];
}) {
  const update = useUpdateInstrument();
  const form = useForm<InstrumentFormValues>({
    initialValues: {
      name: instrument.name,
      symbol: instrument.symbol ?? "",
      asset_class: instrument.asset_class,
      currency: instrument.currency,
      category_id: instrument.category_id ? String(instrument.category_id) : null,
      maturity_date: instrument.maturity_date ? new Date(instrument.maturity_date) : null,
      expected_interest: instrument.expected_interest ?? "",
      status: instrument.status,
      price_source: instrument.price_source,
      provider_ref: instrument.provider_ref ?? "",
      is_active: instrument.is_active,
    },
    validate: instrumentValidators,
  });

  const submit = form.onSubmit((values) => {
    update.mutate(
      {
        id: instrument.id,
        body: {
          name: values.name.trim(),
          symbol: values.symbol.trim() || null,
          category_id: values.category_id ? Number(values.category_id) : null,
          is_active: values.is_active,
          ...(instrument.asset_class === "loan" && {
            maturity_date: values.maturity_date ? toApiDate(values.maturity_date) : null,
            expected_interest: values.expected_interest || null,
            status: values.status,
          }),
          ...(instrument.asset_class === "tradable" && {
            price_source: values.price_source,
            provider_ref: values.price_source ? values.provider_ref.trim() : null,
          }),
        },
      },
      {
        onSuccess: (updated) => {
          notifications.show({ color: "green", message: `Instrument "${updated.name}" updated` });
          onClose();
        },
      },
    );
  });

  return (
    <Modal opened onClose={onClose} title={`Edit instrument — ${instrument.name}`}>
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Name" withAsterisk {...form.getInputProps("name")} />
          <TextInput label="Symbol" {...form.getInputProps("symbol")} />
          <TextInput label="Asset class" value={instrument.asset_class} disabled description="Immutable" />
          <TextInput label="Currency" value={instrument.currency} disabled description="Immutable" />
          <CategorySelect categories={categories} form={form} />
          {instrument.asset_class === "loan" && <LoanFields form={form} />}
          {instrument.asset_class === "tradable" && <PricingFields form={form} />}
          <Switch label="Active" {...form.getInputProps("is_active", { type: "checkbox" })} />
          <Button type="submit" loading={update.isPending}>
            Save
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

function InstrumentsTab() {
  const [assetClass, setAssetClass] = useState<string | null>(null);
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [editing, setEditing] = useState<InstrumentRead | null>(null);

  const filters: InstrumentFilters = {
    ...(assetClass && { asset_class: assetClass as AssetClass }),
    ...(categoryId && { category_id: Number(categoryId) }),
    include_inactive: includeInactive,
  };
  const instruments = useInstruments(filters);
  const assetClasses = useAssetClasses();
  const categories = useCategories();

  const assetClassOptions = (assetClasses.data ?? []).map((ac) => ({
    value: ac.code,
    label: ac.label,
  }));
  const categoryName = (id: number | null) =>
    id === null ? "—" : (categories.data?.find((c) => c.id === id)?.name ?? `#${id}`);

  return (
    <Stack>
      <Group justify="space-between">
        <Group>
          <Select
            placeholder="All asset classes"
            data={assetClassOptions}
            value={assetClass}
            onChange={setAssetClass}
            clearable
          />
          <Select
            placeholder="All categories"
            data={(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
            value={categoryId}
            onChange={setCategoryId}
            clearable
          />
          <Checkbox
            label="Include inactive"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.currentTarget.checked)}
          />
        </Group>
        <Button onClick={openCreate}>New instrument</Button>
      </Group>
      <QueryBoundary query={instruments}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState
              message="No instruments match — an instrument is anything you hold or lend."
              action={<Button onClick={openCreate}>Create an instrument</Button>}
            />
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Symbol</Table.Th>
                  <Table.Th>Asset class</Table.Th>
                  <Table.Th>Currency</Table.Th>
                  <Table.Th>Category</Table.Th>
                  <Table.Th>Priced by</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((instrument) => (
                  <Table.Tr key={instrument.id}>
                    <Table.Td>{instrument.name}</Table.Td>
                    <Table.Td>{instrument.symbol ?? "—"}</Table.Td>
                    <Table.Td>
                      <Badge variant="light">{instrument.asset_class}</Badge>
                    </Table.Td>
                    <Table.Td>{instrument.currency}</Table.Td>
                    <Table.Td>{categoryName(instrument.category_id)}</Table.Td>
                    <Table.Td>{instrument.price_source ?? "—"}</Table.Td>
                    <Table.Td>
                      <Badge color={instrument.is_active ? "green" : "gray"} variant="light">
                        {instrument.is_active ? "active" : "inactive"}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        onClick={() => setEditing(instrument)}
                      >
                        Edit
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )
        }
      </QueryBoundary>
      <CreateInstrumentModal
        opened={createOpened}
        onClose={closeCreate}
        categories={categories.data ?? []}
        assetClasses={assetClassOptions}
      />
      {editing && (
        <EditInstrumentModal
          instrument={editing}
          onClose={() => setEditing(null)}
          categories={categories.data ?? []}
        />
      )}
    </Stack>
  );
}

function CategoryModal({
  category,
  opened,
  onClose,
}: {
  category: CategoryRead | null;
  opened: boolean;
  onClose: () => void;
}) {
  const create = useCreateCategory();
  const update = useUpdateCategory();
  const form = useForm({
    initialValues: {
      name: category?.name ?? "",
      description: category?.description ?? "",
      is_active: category?.is_active ?? true,
    },
    validate: { name: (v) => (v.trim() ? null : "Name is required") },
  });

  const submit = form.onSubmit((values) => {
    const done = (name: string, verb: string) => {
      notifications.show({ color: "green", message: `Category "${name}" ${verb}` });
      form.reset();
      onClose();
    };
    if (category) {
      update.mutate(
        {
          id: category.id,
          body: {
            name: values.name.trim(),
            description: values.description.trim() || null,
            is_active: values.is_active,
          },
        },
        { onSuccess: (c) => done(c.name, "updated") },
      );
    } else {
      create.mutate(
        { name: values.name.trim(), description: values.description.trim() || null },
        { onSuccess: (c) => done(c.name, "created") },
      );
    }
  });

  return (
    <Modal opened={opened} onClose={onClose} title={category ? `Edit category — ${category.name}` : "New category"}>
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Name" withAsterisk placeholder="ETF / crypto / real estate" {...form.getInputProps("name")} />
          <TextInput label="Description" {...form.getInputProps("description")} />
          {category && (
            <Switch label="Active" {...form.getInputProps("is_active", { type: "checkbox" })} />
          )}
          <Button type="submit" loading={create.isPending || update.isPending}>
            {category ? "Save" : "Create"}
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

function CategoriesTab() {
  const [includeInactive, setIncludeInactive] = useState(false);
  const categories = useCategories(includeInactive);
  const deleteCategory = useDeleteCategory();
  const [modalState, setModalState] = useState<{ opened: boolean; category: CategoryRead | null }>({
    opened: false,
    category: null,
  });
  const [deleting, setDeleting] = useState<CategoryRead | null>(null);

  return (
    <Stack>
      <Group justify="space-between">
        <Checkbox
          label="Include inactive"
          checked={includeInactive}
          onChange={(e) => setIncludeInactive(e.currentTarget.checked)}
        />
        <Button onClick={() => setModalState({ opened: true, category: null })}>New category</Button>
      </Group>
      <QueryBoundary query={categories}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState message="No categories yet — categories group instruments for allocation views (ETF, crypto, real estate...)." />
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Description</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((category) => (
                  <Table.Tr key={category.id}>
                    <Table.Td>{category.name}</Table.Td>
                    <Table.Td>{category.description ?? "—"}</Table.Td>
                    <Table.Td>
                      <Badge color={category.is_active ? "green" : "gray"} variant="light">
                        {category.is_active ? "active" : "inactive"}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{formatDate(category.created_at)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" justify="flex-end">
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          onClick={() => setModalState({ opened: true, category })}
                        >
                          Edit
                        </Button>
                        {category.is_active && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="red"
                            onClick={() => setDeleting(category)}
                          >
                            Deactivate
                          </Button>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )
        }
      </QueryBoundary>
      {modalState.opened && (
        <CategoryModal
          key={modalState.category?.id ?? "new"}
          category={modalState.category}
          opened
          onClose={() => setModalState({ opened: false, category: null })}
        />
      )}
      <Modal
        opened={deleting !== null}
        onClose={() => setDeleting(null)}
        title="Deactivate category"
      >
        <Stack>
          <Text size="sm">
            Categories are soft-deleted: instruments keep pointing at "{deleting?.name}" and
            historical allocation reports still resolve it.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <Button
              color="red"
              loading={deleteCategory.isPending}
              onClick={() => {
                if (!deleting) return;
                deleteCategory.mutate(deleting.id, {
                  onSuccess: () => {
                    notifications.show({ color: "green", message: `Category "${deleting.name}" deactivated` });
                    setDeleting(null);
                  },
                });
              }}
            >
              Deactivate
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

export function InstrumentsPage() {
  return (
    <Stack>
      <Title order={2}>Instruments</Title>
      <Tabs defaultValue="instruments" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="instruments">Instruments</Tabs.Tab>
          <Tabs.Tab value="categories">Categories</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="instruments" pt="md">
          <InstrumentsTab />
        </Tabs.Panel>
        <Tabs.Panel value="categories" pt="md">
          <CategoriesTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
