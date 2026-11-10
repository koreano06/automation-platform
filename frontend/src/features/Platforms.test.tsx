import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Platforms from "./Platforms";
import { apiRequest } from "../services/api/client";
import type { Platform } from "../types";

vi.mock("../services/api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiRequest: vi.fn(),
}));
const platform: Platform = {
  id: "platform-1",
  name: "Portal de Teste",
  description: "",
  active: true,
  mode: "simulation",
  fields: [],
  config: { simulate_failure: false },
};
afterEach(() => vi.restoreAllMocks());

describe("exclusão de plataformas", () => {
  it("exige confirmação e envia a exclusão para um administrador", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(apiRequest).mockResolvedValue(undefined);
    const onChange = vi.fn();
    render(<Platforms platforms={[platform]} onChange={onChange} isAdmin />);
    await userEvent.click(
      screen.getByRole("button", {
        name: "Excluir plataforma Portal de Teste",
      }),
    );
    await waitFor(() => expect(onChange).toHaveBeenCalledOnce());
    expect(apiRequest).toHaveBeenCalledWith("/platforms/platform-1", {
      method: "DELETE",
    });
    expect(screen.getByRole("status").textContent).toContain(
      "Plataforma excluída",
    );
  });

  it("não envia exclusão quando a confirmação é cancelada", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<Platforms platforms={[platform]} onChange={vi.fn()} isAdmin />);
    await userEvent.click(
      screen.getByRole("button", { name: /Excluir plataforma/ }),
    );
    expect(apiRequest).not.toHaveBeenCalled();
  });

  it("oculta a exclusão de quem não é administrador", () => {
    render(
      <Platforms platforms={[platform]} onChange={vi.fn()} isAdmin={false} />,
    );
    expect(
      screen.queryByRole("button", { name: /Excluir plataforma/ }),
    ).toBeNull();
  });

  it("mostra falha da API sem anunciar exclusão ou atualizar a lista", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(apiRequest).mockRejectedValue(
      new Error("Aguarde as execuções pendentes."),
    );
    const onChange = vi.fn();
    render(<Platforms platforms={[platform]} onChange={onChange} isAdmin />);
    await userEvent.click(
      screen.getByRole("button", { name: /Excluir plataforma/ }),
    );
    await screen.findByText("Aguarde as execuções pendentes.");
    expect(onChange).not.toHaveBeenCalled();
  });
});
