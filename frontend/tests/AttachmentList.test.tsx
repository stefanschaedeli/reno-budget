import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@/i18n/i18n";

// ---- Mocks --------------------------------------------------------------- //
// We stub the API and the auth context so the component can render in
// isolation; the underlying XHR is exercised by the integration tests
// against the real backend.

const mockListAttachments = vi.fn();
const mockUploadAttachment = vi.fn();
const mockDeleteAttachment = vi.fn();

vi.mock("@/features/attachments/api", () => ({
  listAttachments: (...a: unknown[]): unknown => mockListAttachments(...a) as unknown,
  uploadAttachment: (...a: unknown[]): unknown => mockUploadAttachment(...a) as unknown,
  deleteAttachment: (...a: unknown[]): unknown => mockDeleteAttachment(...a) as unknown,
  downloadUrl: (id: string): string => `/api/v1/attachments/${id}/download`,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    accessToken: "test-token",
    user: { id: "user-1", email: "u@example.ch", display_name: "U" },
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => children,
}));

import { AttachmentList } from "@/features/attachments/AttachmentList";
import { formatBytes } from "@/features/attachments/types";

describe("AttachmentList", () => {
  beforeEach(() => {
    mockListAttachments.mockReset();
    mockUploadAttachment.mockReset();
    mockDeleteAttachment.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders an empty state when there are no attachments", async () => {
    mockListAttachments.mockResolvedValueOnce([]);
    render(
      <AttachmentList targetType="cost_item" targetId="abc" canEdit={true} />,
    );
    await waitFor(() => {
      expect(screen.getByText(/Noch keine Anhänge/i)).toBeInTheDocument();
    });
  });

  it("rejects oversize files client-side before uploading", async () => {
    mockListAttachments.mockResolvedValueOnce([]);
    render(
      <AttachmentList
        targetType="object"
        targetId="o1"
        canEdit={true}
        maxBytes={10}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/Noch keine Anhänge/i)).toBeInTheDocument();
    });

    const input = screen.getByTestId("attachment-file-input");
    const big = new File(["this is too big"], "big.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [big] } });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/big\.pdf/);
    });
    expect(mockUploadAttachment).not.toHaveBeenCalled();
  });

  it("uploads via the file picker and refreshes the list", async () => {
    // First load → empty; second load (post-upload) → one row.
    mockListAttachments.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        id: "att-1",
        target_type: "cost_item",
        target_id: "abc",
        sha256: "a".repeat(64),
        filename: "offer.pdf",
        mime: "application/pdf",
        size_bytes: 1024,
        uploaded_by: "user-1",
        created_at: new Date().toISOString(),
      },
    ]);
    mockUploadAttachment.mockResolvedValueOnce({});

    render(
      <AttachmentList targetType="cost_item" targetId="abc" canEdit={true} />,
    );
    await waitFor(() => screen.getByText(/Noch keine Anhänge/i));

    const input = screen.getByTestId("attachment-file-input");
    const file = new File(["%PDF"], "offer.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockUploadAttachment).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByText("offer.pdf")).toBeInTheDocument();
    });
  });

  it("requires confirmation before deleting", async () => {
    mockListAttachments.mockResolvedValue([
      {
        id: "att-1",
        target_type: "cost_item",
        target_id: "abc",
        sha256: "a".repeat(64),
        filename: "offer.pdf",
        mime: "application/pdf",
        size_bytes: 1024,
        uploaded_by: "user-1",
        created_at: new Date().toISOString(),
      },
    ]);
    mockDeleteAttachment.mockResolvedValueOnce(undefined);

    render(
      <AttachmentList targetType="cost_item" targetId="abc" canEdit={true} />,
    );
    await waitFor(() => screen.getByText("offer.pdf"));

    // First click reveals the confirmation row; delete not yet called.
    fireEvent.click(screen.getByTestId("attachment-delete-att-1"));
    expect(mockDeleteAttachment).not.toHaveBeenCalled();
    expect(screen.getByText(/Wirklich löschen/)).toBeInTheDocument();

    // Confirm → call goes through.
    fireEvent.click(screen.getByTestId("attachment-delete-confirm-att-1"));
    await waitFor(() => {
      expect(mockDeleteAttachment).toHaveBeenCalledWith("att-1");
    });
  });

  it("hides the dropzone for read-only viewers", async () => {
    mockListAttachments.mockResolvedValueOnce([]);
    render(
      <AttachmentList targetType="object" targetId="o1" canEdit={false} />,
    );
    await waitFor(() => screen.getByText(/Noch keine Anhänge/i));
    expect(screen.queryByTestId("attachment-dropzone")).not.toBeInTheDocument();
  });
});

describe("formatBytes", () => {
  it("formats bytes/KB/MB with German thousands grouping", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toMatch(/KB/);
    expect(formatBytes(5 * 1024 * 1024)).toMatch(/MB/);
  });
});
