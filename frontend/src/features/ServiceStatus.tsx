import { useEffect, useState } from "react";
import { apiGet } from "../services/api/client";
import { formatDate, message } from "../types";

type Diagnostics = {
  api_version: string;
  build_id: string;
  schema: { current: string | null; expected: string; up_to_date: boolean };
  database: { kind: string; connected: boolean };
  worker: {
    status: string;
    active_count: number;
    busy_count: number;
    last_seen: string | null;
  };
  queued_count: number;
  step_test_queue: number;
  runner_enabled: boolean;
  allowed_hosts: string[];
  integration_configured: boolean;
};
export default function ServiceStatus({
  compact = false,
}: {
  compact?: boolean;
}) {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [error, setError] = useState("");
  const [legacy, setLegacy] = useState(false);
  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const result = await apiGet<Diagnostics>("/system");
        if (!alive) return;
        if (!result?.schema || !result?.worker) {
          setLegacy(true);
          return;
        }
        setLegacy(false);
        setData(result);
        setError("");
      } catch (exception) {
        if (alive) setError(message(exception));
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);
  if (legacy)
    return (
      <p className="warning" role="status">
        A API ainda usa uma versão anterior. Atualize os serviços com
        Restart-Dev.ps1 para disponibilizar diagnóstico e teste de etapas.
      </p>
    );
  if (error)
    return (
      <p className="alert" role="alert">
        Diagnóstico indisponível: {error}
      </p>
    );
  if (!data)
    return (
      <p className="muted" role="status">
        Consultando API, banco e executor...
      </p>
    );
  const states = (
    <div className="service-badges">
      <span className="status status-succeeded">API v{data.api_version}</span>
      <span
        className={`status ${data.schema.up_to_date ? "status-succeeded" : "status-failed"}`}
      >
        Banco {data.schema.up_to_date ? "atualizado" : "pendente"}
      </span>
      <span
        className={`status ${data.worker.status === "online" ? "status-succeeded" : "status-failed"}`}
      >
        Executor{" "}
        {data.worker.status === "online"
          ? "conectado"
          : data.worker.status === "outdated"
            ? "desatualizado"
            : "desconectado"}
      </span>
      <span className="muted">
        Fila: {data.queued_count} execuções · {data.step_test_queue} testes
      </span>
    </div>
  );
  if (compact)
    return (
      <div className="service-strip">
        {states}
        {data.worker.status !== "online" && (
          <small>
            Os trabalhos aguardarão um executor conectado. Consulte Diagnóstico
            para configurar.
          </small>
        )}
      </div>
    );
  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>Diagnóstico dos serviços</h2>
          <p>Estado consultado a cada 4 segundos.</p>
        </div>
        <span className="chip">{data.build_id}</span>
      </div>
      {states}
      <dl className="review-data">
        <div>
          <dt>Schema aplicado / esperado</dt>
          <dd>
            {data.schema.current || "Sem migração"} / {data.schema.expected}
          </dd>
        </div>
        <div>
          <dt>Banco</dt>
          <dd>
            {data.database.kind} ·{" "}
            {data.database.connected ? "Conectado" : "Indisponível"}
          </dd>
        </div>
        <div>
          <dt>Executores ativos / ocupados</dt>
          <dd>
            {data.worker.active_count} / {data.worker.busy_count}
          </dd>
        </div>
        <div>
          <dt>Último sinal do executor</dt>
          <dd>
            {data.worker.last_seen
              ? formatDate(data.worker.last_seen)
              : "Sem sinal recente"}
          </dd>
        </div>
        <div>
          <dt>Ações locais reais</dt>
          <dd>
            {data.runner_enabled
              ? "Habilitadas"
              : "Desabilitadas; simulação disponível"}
          </dd>
        </div>
        <div>
          <dt>Domínios autorizados</dt>
          <dd>{data.allowed_hosts.join(", ") || "Nenhum"}</dd>
        </div>
        <div>
          <dt>Power Automate</dt>
          <dd>
            {data.integration_configured ? "Configurado" : "Não configurado"}
          </dd>
        </div>
      </dl>
      <p className="notice">
        Se a API, o schema ou o executor estiverem desatualizados, use o script
        Restart-Dev.ps1 no terminal que iniciou o projeto. Os trabalhos
        permanecem registrados na fila.
      </p>
    </section>
  );
}
