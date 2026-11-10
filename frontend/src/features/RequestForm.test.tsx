import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RequestForm from "./RequestForm";
import { apiPost } from "../services/api/client";
import type { Platform } from "../types";

vi.mock("../services/api/client", () => ({ apiPost: vi.fn() }));
const platforms: Platform[] = [
  {
    id: "one",
    name: "Portal",
    active: true,
    description: "",
    mode: "simulation",
    config: { simulate_failure: false },
    fields: [
      {
        key: "profile",
        label: "Perfil do portal",
        field_type: "select",
        required: true,
        options: ["Colaborador", "Gestor"],
      },
    ],
  },
  {
    id: "two",
    name: "Diretório",
    active: true,
    description: "",
    mode: "simulation",
    config: { simulate_failure: false },
    fields: [
      {
        key: "cost_center",
        label: "Centro de custo",
        field_type: "integer",
        required: true,
        options: [],
      },
    ],
  },
];

describe("solicitação multi-plataforma", () => {
  it("carrega campos de cada destino, revisa e envia resultados separados", async () => {
    const user = userEvent.setup();
    const created = vi.fn();
    vi.mocked(apiPost).mockResolvedValue({ id: "request-created" });
    const { container } = render(
      <RequestForm platforms={platforms} onCreated={created} />,
    );
    await user.type(screen.getByLabelText("Nome completo"), "Pessoa de Teste");
    await user.type(
      screen.getByLabelText("E-mail corporativo"),
      "pessoa@example.invalid",
    );
    await user.type(screen.getByLabelText("Departamento"), "Qualidade");
    await user.type(screen.getByLabelText("Matrícula"), "T01");
    expect(screen.queryByLabelText("Perfil do portal *")).toBeNull();
    await user.click(screen.getByRole("checkbox", { name: /Portal/ }));
    await user.click(screen.getByRole("checkbox", { name: /Diretório/ }));
    await user.selectOptions(
      screen.getByLabelText("Perfil do portal *"),
      "Gestor",
    );
    await user.type(screen.getByLabelText("Centro de custo *"), "42");
    fireEvent.submit(container.querySelector("form")!);
    expect(screen.getByText("Revise a solicitação")).toBeTruthy();
    expect(apiPost).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Confirmar solicitação" }),
    );
    await waitFor(() => expect(created).toHaveBeenCalled());
    const [, body, headers] = vi.mocked(apiPost).mock.calls[0];
    expect(body).toMatchObject({
      targets: [
        { platform_id: "one", fields: { profile: "Gestor" } },
        { platform_id: "two", fields: { cost_center: 42 } },
      ],
    });
    expect(headers).toHaveProperty("Idempotency-Key");
  });
  it("não envia sem destino selecionado", () => {
    const { container } = render(
      <RequestForm platforms={platforms} onCreated={vi.fn()} />,
    );
    fireEvent.submit(container.querySelector("form")!);
    expect(screen.getByRole("alert").textContent).toContain(
      "Selecione pelo menos uma plataforma",
    );
    expect(apiPost).not.toHaveBeenCalled();
  });
});
