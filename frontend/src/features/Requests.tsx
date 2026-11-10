import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiAssetUrl } from "../services/api/client";
import {
  formatDate,
  message,
  type ExecutionEvent,
  type ProvisioningRequest,
} from "../types";
import { Empty, Status } from "../components/ui";

export function RequestTable({
  requests,
  onSelect,
}: {
  requests: ProvisioningRequest[];
  onSelect: (id: string) => void;
}) {
  if (!requests.length)
    return (
      <Empty title="Seu histórico começa aqui">
        Envie uma solicitação ou execute um fluxo validado para acompanhar seus
        resultados.
      </Empty>
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>SOLICITAÇÃO</th>
            <th>COLABORADOR / CONTEXTO</th>
            <th>DESTINOS</th>
            <th>ESTADO</th>
            <th>CRIADA EM</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((item) => (
            <tr key={item.id}>
              <td>
                <button
                  className="table-link"
                  onClick={() => onSelect(item.id)}
                >
                  #{item.id.slice(0, 8)} ↗
                </button>
              </td>
              <td>
                <b>{item.employee.name}</b>
                <small>{item.employee.department}</small>
              </td>
              <td>{item.executions.length} plataformas</td>
              <td>
                <Status value={item.status} />
              </td>
              <td>{formatDate(item.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function RequestDetail({
  id,
  onBack,
  onUpdate,
  isAdmin = false,
}: {
  id: string;
  onBack: () => void;
  onUpdate: () => void;
  isAdmin?: boolean;
}) {
  const [item, setItem] = useState<ProvisioningRequest | null>(null);
  const [events, setEvents] = useState<Record<string, ExecutionEvent[]>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const request = await apiGet<ProvisioningRequest>(
      `/provisioning-requests/${id}`,
    );
    const result = await Promise.all(
      request.executions.map(
        async (execution) =>
          [
            execution.id,
            await apiGet<ExecutionEvent[]>(
              `/executions/${execution.id}/events`,
            ),
          ] as const,
      ),
    );
    setItem(request);
    setEvents(Object.fromEntries(result));
  }, [id]);
  useEffect(() => {
    void load().catch((exception) => setError(message(exception)));
    const interval = window.setInterval(() => {
      void load().catch((exception) => setError(message(exception)));
    }, 2000);
    return () => window.clearInterval(interval);
  }, [load]);
  async function action(
    executionId: string,
    type: "retry" | "cancel" | "resume",
  ) {
    setBusy(true);
    setError("");
    try {
      await apiPost(`/executions/${executionId}/${type}`);
      await load();
      onUpdate();
    } catch (exception) {
      setError(message(exception));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <div className="actions">
        <button className="button ghost" onClick={onBack}>
          ← Voltar ao histórico
        </button>
        <span className="muted live-label">
          <i />
          Atualiza a cada 2 segundos
        </span>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {item ? (
        <>
          <section className="panel detail-summary">
            <div>
              <p className="eyebrow">SOLICITAÇÃO #{item.id.slice(0, 8)}</p>
              <h2>{item.employee.name}</h2>
              <p>
                {item.employee.email} · {item.employee.department}
              </p>
            </div>
            <Status value={item.status} />
          </section>
          {item.executions.map((execution) => (
            <section className="panel execution-card" key={execution.id}>
              <div className="panel-title">
                <div>
                  <h2>{execution.platform_name}</h2>
                  <p>
                    {execution.mode.replaceAll("_", " ")} · Tentativa{" "}
                    {execution.attempts} · {execution.id.slice(0, 8)}
                  </p>
                </div>
                <div className="actions">
                  <Status value={execution.status} />
                  {execution.awaiting_operator && (
                    <span className="status status-partially_succeeded">
                      Aguardando operador
                    </span>
                  )}
                  {execution.awaiting_operator &&
                    !execution.cancel_requested && (
                      <button
                        className="button small primary"
                        disabled={busy}
                        onClick={() => void action(execution.id, "resume")}
                      >
                        Confirmar e continuar
                      </button>
                    )}
                  {execution.can_retry && (
                    <button
                      disabled={busy}
                      className="button small primary"
                      onClick={() => void action(execution.id, "retry")}
                    >
                      Repetir falha
                    </button>
                  )}
                  {(execution.status === "queued" ||
                    (["running", "dispatching"].includes(execution.status) &&
                      execution.mode !== "power_automate")) && (
                    <button
                      disabled={busy || execution.cancel_requested}
                      className="button small ghost"
                      onClick={() => void action(execution.id, "cancel")}
                    >
                      {execution.cancel_requested
                        ? "Interrupção solicitada"
                        : "Cancelar"}
                    </button>
                  )}
                </div>
              </div>
              {execution.error_code && (
                <p className="warning">
                  Código: {execution.error_code}. Confira o evento abaixo para a
                  orientação.
                </p>
              )}
              {execution.result.failed_step && (
                <p className="warning">
                  Falha na etapa {execution.result.failed_step}
                  {execution.result.action
                    ? ` · ${execution.result.action}`
                    : ""}
                  . Revise o alvo e os dados dessa etapa.
                </p>
              )}
              {isAdmin && execution.result.artifact_id && (
                <figure>
                  <img
                    className="diagnostic-image"
                    src={apiAssetUrl(
                      `/artifacts/${execution.result.artifact_id}`,
                    )}
                    alt="Evidência esquemática da etapa, sem conteúdo da tela"
                  />
                  <figcaption>
                    Diagnóstico esquemático com retenção temporária. Não contém
                    pixels da tela nem valores digitados.
                  </figcaption>
                </figure>
              )}
              <ol className="timeline">
                {(events[execution.id] || []).map((event) => (
                  <li
                    className={event.level === "error" ? "event-error" : ""}
                    key={event.id}
                  >
                    <span className="timeline-dot" />
                    <div>
                      <p>{event.message}</p>
                      <small>
                        {formatDate(event.created_at)}
                        {event.step ? ` · Etapa ${event.step}` : ""}
                      </small>
                    </div>
                  </li>
                ))}
              </ol>
              {execution.result.code && (
                <div className="result-line">
                  Resultado:{" "}
                  <b>
                    {{
                      account_created: "Cadastro criado",
                      already_exists: "Cadastro já existente",
                      flow_completed: "Fluxo confirmado",
                      outcome_requires_review:
                        "Conferência do destino necessária",
                      destination_rejected: "Operação recusada pelo destino",
                      execution_error: "Falha no destino",
                      condition_matched:
                        "Condição reconhecida; fluxo encerrado com sucesso",
                    }[execution.result.code] || execution.result.code}
                  </b>
                </div>
              )}
            </section>
          ))}
        </>
      ) : (
        <p role="status" className="muted">
          Carregando execução...
        </p>
      )}
    </div>
  );
}
