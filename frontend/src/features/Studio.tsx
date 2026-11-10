import { useRef, useState } from "react";
import { apiGet, apiPost } from "../services/api/client";
import {
  message,
  type Employee,
  type Platform,
  type ProvisioningRequest,
} from "../types";
import { Empty } from "../components/ui";
import { AutomationEditor } from "./Platforms";
import { DynamicFields, EmployeeFields } from "./RequestForm";
import ServiceStatus from "./ServiceStatus";

export default function Studio({
  platforms,
  onChange,
  onCreated,
  onConfigure,
}: {
  platforms: Platform[];
  onChange: () => void;
  onCreated: (item: ProvisioningRequest) => void;
  onConfigure: () => void;
}) {
  const [selected, setSelected] = useState("");
  const [fields, setFields] = useState<Record<string, string | number>>({});
  const [withEmployee, setWithEmployee] = useState(false);
  const [employee, setEmployee] = useState<Employee>({
    name: "",
    email: "",
    department: "",
    employee_id: "",
  });
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const submission = useRef({ body: "", key: "" });
  const platform = platforms.find((item) => item.id === selected);
  return (
    <div className="stack">
      <ServiceStatus compact />
      <section className="panel studio-select">
        <label>
          Plataforma de destino
          <select
            value={selected}
            onChange={(event) => {
              setSelected(event.target.value);
              setFields({});
              setFeedback("");
            }}
          >
            <option value="">Escolha uma plataforma</option>
            {platforms.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.mode.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <button className="button ghost" onClick={onConfigure}>
          ＋ Configurar plataforma
        </button>
      </section>
      {platform ? (
        <>
          <AutomationEditor
            key={platform.id}
            platform={platform}
            onChange={onChange}
          />
          <section className="panel">
            <div className="panel-title">
              <div>
                <h2>Executar versão validada</h2>
                <p>
                  O envio entra na fila; acompanhe o progresso no histórico.
                </p>
              </div>
              <span className="chip">
                {platform.mode === "simulation"
                  ? "SEM AÇÕES REAIS"
                  : "EXECUÇÃO REAL"}
              </span>
            </div>
            {feedback && (
              <p className="alert" role="alert">
                {feedback}
              </p>
            )}
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setFeedback("");
                try {
                  const versions = await apiGet<
                    { id: string; status: string }[]
                  >(`/platforms/${platform.id}/automations`);
                  const version = versions.find(
                    (item) => item.status === "validated",
                  );
                  if (!version)
                    throw new Error(
                      "Salve e valide uma versão antes de executar.",
                    );
                  const payload = {
                    fields,
                    ...(withEmployee ? { employee } : {}),
                  };
                  const body = JSON.stringify({ version: version.id, payload });
                  if (submission.current.body !== body)
                    submission.current = { body, key: crypto.randomUUID() };
                  onCreated(
                    await apiPost<ProvisioningRequest>(
                      `/automations/${version.id}/runs`,
                      payload,
                      { "Idempotency-Key": submission.current.key },
                    ),
                  );
                } catch (error) {
                  setFeedback(message(error));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <DynamicFields
                platform={platform}
                value={fields}
                onChange={setFields}
              />
              <label className="check">
                <input
                  type="checkbox"
                  checked={withEmployee}
                  onChange={(event) => setWithEmployee(event.target.checked)}
                />{" "}
                Este fluxo usa dados de colaborador (employee.*)
              </label>
              {withEmployee && (
                <EmployeeFields value={employee} onChange={setEmployee} />
              )}
              <div className="actions end">
                <button
                  className="button primary"
                  disabled={busy || !platform.active}
                >
                  {busy ? "Enfileirando..." : "▶ Enfileirar execução"}
                </button>
              </div>
            </form>
          </section>
        </>
      ) : (
        <section className="panel">
          <Empty title="Escolha o destino do seu próximo fluxo">
            Use imagens de botões, nomes acessíveis ou seletores. As automações
            ficam organizadas por plataforma e versão.
          </Empty>
        </section>
      )}
    </div>
  );
}
