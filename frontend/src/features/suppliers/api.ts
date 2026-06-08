/**
 * Suppliers API client + TanStack Query hooks (Phase 11C).
 *
 * All mutating endpoints attach CSRF via the shared client wrapper.
 * Suppliers belong to a single object; the list query is keyed by
 * object id + archived-filter flag.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { z } from "zod";
import { apiRequest } from "@/api/client";
import {
  supplierListItemSchema,
  supplierSchema,
  type Supplier,
  type SupplierCreate,
  type SupplierListItem,
  type SupplierUpdate,
} from "./types";

export async function fetchSuppliers(
  objectId: string,
  opts: { includeArchived?: boolean } = {},
): Promise<Supplier[]> {
  const qs = opts.includeArchived ? "?include_archived=true" : "";
  const raw = await apiRequest<unknown[]>(
    `/objects/${objectId}/suppliers${qs}`,
  );
  return raw.map((s) => supplierSchema.parse(s));
}

export async function fetchAllSuppliers(): Promise<SupplierListItem[]> {
  const raw = await apiRequest<unknown>(`/suppliers`);
  return z.array(supplierListItemSchema).parse(raw);
}

export function useAllSuppliers(): UseQueryResult<SupplierListItem[]> {
  return useQuery({
    queryKey: ["suppliers-all"],
    queryFn: fetchAllSuppliers,
  });
}

export async function fetchSupplier(supplierId: string): Promise<Supplier> {
  const raw = await apiRequest<unknown>(`/suppliers/${supplierId}`);
  return supplierSchema.parse(raw);
}

export async function createSupplier(
  objectId: string,
  payload: SupplierCreate,
): Promise<Supplier> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/suppliers`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return supplierSchema.parse(raw);
}

export async function updateSupplier(
  supplierId: string,
  payload: SupplierUpdate,
): Promise<Supplier> {
  const raw = await apiRequest<unknown>(`/suppliers/${supplierId}`, {
    method: "PATCH",
    json: payload,
    withCsrf: true,
  });
  return supplierSchema.parse(raw);
}

export async function archiveSupplier(supplierId: string): Promise<Supplier> {
  const raw = await apiRequest<unknown>(`/suppliers/${supplierId}/archive`, {
    method: "POST",
    withCsrf: true,
  });
  return supplierSchema.parse(raw);
}

export async function deleteSupplier(supplierId: string): Promise<void> {
  await apiRequest<void>(`/suppliers/${supplierId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

// --- hooks -----------------------------------------------------------------

export const suppliersKey = (objectId: string, includeArchived: boolean) =>
  ["suppliers", objectId, includeArchived] as const;

export function useSuppliers(
  objectId: string,
  opts: { includeArchived?: boolean } = {},
): UseQueryResult<Supplier[]> {
  const includeArchived = opts.includeArchived ?? false;
  return useQuery({
    queryKey: suppliersKey(objectId, includeArchived),
    queryFn: () => fetchSuppliers(objectId, { includeArchived }),
    enabled: Boolean(objectId),
  });
}

export function useSupplier(supplierId: string): UseQueryResult<Supplier> {
  return useQuery({
    queryKey: ["supplier", supplierId] as const,
    queryFn: () => fetchSupplier(supplierId),
    enabled: Boolean(supplierId),
  });
}

export function useCreateSupplier(
  objectId: string,
): UseMutationResult<Supplier, Error, SupplierCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupplierCreate) => createSupplier(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suppliers", objectId] });
    },
  });
}

export function useUpdateSupplier(
  supplierId: string,
): UseMutationResult<Supplier, Error, SupplierUpdate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupplierUpdate) =>
      updateSupplier(supplierId, payload),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["suppliers", data.object_id] });
      void qc.invalidateQueries({ queryKey: ["supplier", supplierId] });
    },
  });
}

export function useArchiveSupplier(
  supplierId: string,
): UseMutationResult<Supplier, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => archiveSupplier(supplierId),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["suppliers", data.object_id] });
      void qc.invalidateQueries({ queryKey: ["supplier", supplierId] });
    },
  });
}

export function useDeleteSupplier(
  supplierId: string,
  objectId: string,
): UseMutationResult<void, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deleteSupplier(supplierId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suppliers", objectId] });
    },
  });
}
