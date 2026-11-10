import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AutomationEditor } from "./Platforms";
import { apiGet, apiPost } from "../services/api/client";
import type { Platform } from "../types";

vi.mock("../services/api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiRequest: vi.fn(),
  apiAssetUrl: (path: string) => path,
}));
const platform: Platform = {
  id: "pilot",
  name: "Pilot",
  active: true,
  mode: "simulation",
  description: "",
  fields: [],
  config: { simulate_failure: false },
};

describe("ferramentas do editor", () => {
  it("duplica etapas com campos independentes", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);
    render(<AutomationEditor platform={platform} onChange={vi.fn()} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Duplicar etapa 1" }),
    );
    const urls = screen.getAllByLabelText(
      "URL de destino",
    ) as HTMLInputElement[];
    expect(urls).toHaveLength(2);
    await userEvent.clear(urls[1]);
    await userEvent.type(urls[1], "https://different.example.invalid");
    expect(urls[0].value).toBe("https://pilot.invalid/users/new");
    expect(urls[1].value).toBe("https://different.example.invalid");
  });

  it("enfileira reconhecimento de uma etapa sem executar ações por padrão", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);
    vi.mocked(apiPost).mockResolvedValue({
      id: "test-1",
      status: "queued",
      mode: "simulation",
      preview_only: true,
      result: {},
      error_code: null,
    });
    render(<AutomationEditor platform={platform} onChange={vi.fn()} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Testar etapa 2" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Reconhecer alvo" }),
    );
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith(
        "/platforms/pilot/step-tests",
        expect.objectContaining({
          preview_only: true,
          step: expect.objectContaining({
            action: "fill",
            data_ref: "employee.name",
          }),
        }),
      ),
    );
    expect(screen.getByText("Na fila")).toBeTruthy();
  });
});
