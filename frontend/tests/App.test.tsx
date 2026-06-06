import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { App } from "@/app/App";
import "@/i18n/i18n";

describe("App", () => {
  beforeEach(() => {
    // The bootstrap effect calls /api/v1/auth/refresh; default to 401.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, { status: 401, headers: { "content-type": "application/json" } }),
      ),
    );
    window.history.pushState({}, "", "/anmelden");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the login page when unauthenticated", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Anmelden/i })).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/E-Mail/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Passwort/i)).toBeInTheDocument();
  });

  it("shows the reset-password request page on its route", async () => {
    window.history.pushState({}, "", "/passwort-zuruecksetzen");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Passwort zurücksetzen/i })).toBeInTheDocument();
    });
  });
});
