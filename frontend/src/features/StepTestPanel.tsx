import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiAssetUrl, apiGet, apiPost } from "../services/api/client";
import {
  message,
  type Employee,
  type Platform,
  type Step,
  type StepTest,
} from "../types";
import { DynamicFields, EmployeeFields } from "./RequestForm";
import { Status } from "../components/ui";

export default function StepTestPanel({
  platform,
  step,
  position,
  initialUrl,
  onClose,
}: {
  platform: Platform;
  step: Step;
  position: number;
  initialUrl: string;
  onClose: () => void;
}) {
  const [startUrl, setStartUrl] = useState(initialUrl);
  const [preview, setPreview] = useState(true);
  const [fields, setFields] = useState<Record<string, string | number>>({});
  const [employee, setEmployee] = useState<Employee>({
    name: "Pessoa de Teste",
    email: "teste@example.invalid",
    department: "Teste",
    employee_id: "TESTE-001",
  });
  const [job, setJob] = useState<StepTest | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  }, []);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let alive = true;
    const timer = window.setInterval(() => {
      apiGet<StepTest>(`/step-tests/${job.id}`)
        .then((result) => {
          if (alive) setJob(result);
        })
        .catch((exception) => {
          if (alive) setError(message(exception));
        });
    }, 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (
      !preview &&
      platform.mode !== "simulation" &&
      !window.confirm(
        "Executar esta ação real na plataforma? Confira o alvo e os dados antes de continuar.",
      )
    )
      return;
    setBusy(true);
    try {
      setJob(
        await apiPost<StepTest>(`/platforms/${platform.id}/step-tests`, {
          step,
          start_url: startUrl,
          preview_only: preview,
          fields,
          employee: step.data_ref.startsWith("employee.") ? employee : null,
        }),
      );
    } catch (exception) {
      setError(message(exception));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="step-test-panel" ref={panel}>
      <div className="panel-title">
        <div>
          <h3>
            Teste da etapa {position} · {step.action}
          </h3>
          <p>
            O teste abre uma sessão isolada. Etapas anteriores de clique ou
            preenchimento não são repetidas.
          </p>
        </div>
        <button type="button" className="button small ghost" onClick={onClose}>
          Fechar teste
        </button>
      </div>
      <form onSubmit={(event) => void submit(event)}>
        {platform.mode === "local_browser" && step.action !== "open_page" && (
          <label>
            URL inicial do teste
            <input
              type="url"
              required
              value={startUrl}
              onChange={(event) => setStartUrl(event.target.value)}
            />
          </label>
        )}
        <label className="check">
          <input
            type="checkbox"
            checked={preview}
            onChange={(event) => setPreview(event.target.checked)}
          />
          Somente reconhecer o alvo, sem clicar nem preencher
        </label>
        {!preview && (
          <>
            <DynamicFields
              platform={platform}
              value={fields}
              onChange={setFields}
            />
            {step.data_ref.startsWith("employee.") && (
              <EmployeeFields value={employee} onChange={setEmployee} />
            )}
          </>
        )}
        <button
          className="button primary"
          disabled={
            busy || (!!job && ["queued", "running"].includes(job.status))
          }
        >
          {busy
            ? "Enviando..."
            : preview
              ? "Reconhecer alvo"
              : "Executar etapa"}
        </button>
      </form>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {job && (
        <div className="test-result">
          <Status value={job.status} />
          {["queued", "running"].includes(job.status) && (
            <p className="muted">
              Aguardando o worker. O diagnóstico mostra se há um executor
              conectado.
            </p>
          )}
          {job.result.simulated && (
            <p className="notice">
              Resultado simulado; o alvo ainda precisa ser reconhecido na
              plataforma real.
            </p>
          )}
          {job.result.message && (
            <p className="warning">{job.result.message}</p>
          )}
          {job.result.target && (
            <p className="muted">
              Alvo: X {Math.round(job.result.target.x)}, Y{" "}
              {Math.round(job.result.target.y)} ·{" "}
              {Math.round(job.result.target.width)} ×{" "}
              {Math.round(job.result.target.height)} px
            </p>
          )}
          {job.result.artifact_id && (
            <figure>
              <img
                className="diagnostic-image"
                src={apiAssetUrl(`/artifacts/${job.result.artifact_id}`)}
                alt="Prévia esquemática do alvo reconhecido, sem conteúdo da tela"
              />
              <figcaption>
                Prévia esquemática: conteúdo da tela e valores digitados não são
                armazenados. Disponível temporariamente.
              </figcaption>
            </figure>
          )}
        </div>
      )}
    </section>
  );
}
