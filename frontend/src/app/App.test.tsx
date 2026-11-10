import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { apiGet, apiPost } from "../services/api/client";

vi.mock("../services/api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiRequest: vi.fn(),
  setCsrfToken: vi.fn(),
  ApiError: class extends Error {
    status = 401;
  },
}));
vi.mock("../services/api/health", () => ({
  getHealth: vi.fn().mockResolvedValue({ status: "ok", version: "0.2.0" }),
}));

describe("acesso ao workspace", () => {
  it("apresenta login e abre o construtor visual para o administrador", async () => {
    vi.mocked(apiGet).mockImplementation(async (path) => {
      if (path === "/auth/me") throw new Error("unauthorized");
      return [];
    });
    vi.mocked(apiPost).mockResolvedValue({
      user: { id: "admin", username: "admin", role: "admin", active: true },
      csrf_token: "test-token",
    });
    render(<App />);
    await screen.findByText("Acesse sua conta");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Usuário"), "admin");
    await user.type(screen.getByLabelText("Senha"), "test-password");
    await user.click(
      screen.getByRole("button", { name: /Entrar no workspace/ }),
    );
    await screen.findByRole("heading", { name: "Construtor visual", level: 1 });
    expect(
      screen.queryByText("Uma sequência. Muitas possibilidades."),
    ).toBeNull();
    expect(screen.getByLabelText("Plataforma de destino")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Equipe e acessos" }),
    ).toBeTruthy();
  });
  it("limita a navegação do operador às solicitações e acompanhamento", async () => {
    vi.mocked(apiGet).mockImplementation(async (path) =>
      path === "/auth/me"
        ? {
            user: {
              id: "operator",
              username: "operador",
              role: "operator",
              active: true,
            },
            csrf_token: "test-token",
          }
        : [],
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Visão geral", level: 1 });
    expect(
      screen.queryByRole("button", { name: "Construtor visual" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Equipe e acessos" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Plataformas" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Excluir plataforma/ }),
    ).toBeNull();
    await waitFor(() =>
      expect(apiGet).toHaveBeenCalledWith("/provisioning-requests"),
    );
  });
});
