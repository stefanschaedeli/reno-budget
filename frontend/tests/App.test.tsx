import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "@/app/App";
import "@/i18n/i18n";

describe("App", () => {
  it("renders the app title in German", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /Reno-Budget/i })).toBeInTheDocument();
    expect(screen.getByText(/Renovations- und Unterhaltskosten/i)).toBeInTheDocument();
  });
});
