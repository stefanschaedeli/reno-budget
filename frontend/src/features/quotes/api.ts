/**
 * Quotes API client + TanStack Query hooks (Phase 11C).
 *
 * Quotes are scoped to a Lot; listing happens via ``/lots/{id}/quotes``.
 * The transactional award flow uses a dedicated POST endpoint that
 * atomically marks the quote as awarded and points the lot at it.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import {
  quoteSchema,
  type Quote,
  type QuoteCreate,
  type QuoteUpdate,
} from "./types";

export async function fetchLotQuotes(lotId: string): Promise<Quote[]> {
  const raw = await apiRequest<unknown[]>(`/lots/${lotId}/quotes`);
  return raw.map((q) => quoteSchema.parse(q));
}

export async function fetchQuote(quoteId: string): Promise<Quote> {
  const raw = await apiRequest<unknown>(`/quotes/${quoteId}`);
  return quoteSchema.parse(raw);
}

export async function createQuote(
  lotId: string,
  payload: QuoteCreate,
): Promise<Quote> {
  const raw = await apiRequest<unknown>(`/lots/${lotId}/quotes`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return quoteSchema.parse(raw);
}

export async function updateQuote(
  quoteId: string,
  payload: QuoteUpdate,
): Promise<Quote> {
  const raw = await apiRequest<unknown>(`/quotes/${quoteId}`, {
    method: "PATCH",
    json: payload,
    withCsrf: true,
  });
  return quoteSchema.parse(raw);
}

export async function deleteQuote(quoteId: string): Promise<void> {
  await apiRequest<void>(`/quotes/${quoteId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

export async function awardQuote(
  lotId: string,
  quoteId: string,
): Promise<Quote> {
  const raw = await apiRequest<unknown>(
    `/lots/${lotId}/quotes/${quoteId}/award`,
    {
      method: "POST",
      withCsrf: true,
    },
  );
  return quoteSchema.parse(raw);
}

// --- hooks -----------------------------------------------------------------

export function useLotQuotes(lotId: string): UseQueryResult<Quote[]> {
  return useQuery({
    queryKey: ["lot-quotes", lotId] as const,
    queryFn: () => fetchLotQuotes(lotId),
    enabled: Boolean(lotId),
  });
}

export function useCreateQuote(
  lotId: string,
): UseMutationResult<Quote, Error, QuoteCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuoteCreate) => createQuote(lotId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lot-quotes", lotId] });
    },
  });
}

export function useUpdateQuote(
  quoteId: string,
  lotId: string,
): UseMutationResult<Quote, Error, QuoteUpdate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuoteUpdate) => updateQuote(quoteId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lot-quotes", lotId] });
    },
  });
}

export function useDeleteQuote(
  quoteId: string,
  lotId: string,
): UseMutationResult<void, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deleteQuote(quoteId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lot-quotes", lotId] });
    },
  });
}

export function useAwardQuote(
  lotId: string,
): UseMutationResult<Quote, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (quoteId: string) => awardQuote(lotId, quoteId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lot-quotes", lotId] });
      void qc.invalidateQueries({ queryKey: ["lot", lotId] });
    },
  });
}
