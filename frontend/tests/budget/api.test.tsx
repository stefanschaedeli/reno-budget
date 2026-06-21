import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useBudgetTimeline,
  useFinancesOverview,
} from "@/features/budget/api";
import { get, mockFetchByRoute } from "./helpers";

function wrapper(): (props: { children: React.ReactNode }) => JSX.Element {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("budget API hooks", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("useBudgetTimeline surfaces a 403 as an ApiError-bearing query error", async () => {
    mockFetchByRoute([
      {
        match: get("/budget/timeline"),
        respond: () => ({ status: 403, body: { detail: "forbidden" } }),
      },
    ]);
    const { result } = renderHook(
      () => useBudgetTimeline("obj-1", { inflated: true }),
      { wrapper: wrapper() },
    );
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeTruthy();
  });

  it("useFinancesOverview returns parsed rows on success", async () => {
    mockFetchByRoute([
      {
        match: get("/finances"),
        respond: () => ({
          body: {
            rows: [
              {
                object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                name: "X",
                role: "owner",
                is_scoped: false,
                total_planned_inflated_chf: "100",
                total_actual_chf: "10",
                required_per_year_chf: "5",
              },
            ],
          },
        }),
      },
    ]);
    const { result } = renderHook(() => useFinancesOverview(), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.rows).toHaveLength(1);
    expect(result.current.data?.rows[0]?.name).toBe("X");
  });

  it("useBudgetTimeline reports loading state initially", () => {
    mockFetchByRoute([
      {
        match: get("/budget/timeline"),
        respond: () => ({
          body: {
            object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            scope_pro_rated: false,
            rows: [],
          },
        }),
      },
    ]);
    const { result } = renderHook(
      () => useBudgetTimeline("obj-1", { inflated: true }),
      { wrapper: wrapper() },
    );
    expect(result.current.isLoading).toBe(true);
  });
});
