import { useEffect, useState, type FormEvent } from "react";
import {
  apiGet,
  apiPost,
  apiPut,
  apiRequest,
  apiAssetUrl,
} from "../services/api/client";
import {
  message,
  type FlowAction,
  type Automation,
  type Platform,
  type PlatformField,
  type Step,
} from "../types";
import { Empty, Status } from "../components/ui";
import VisualCapture from "../components/VisualCapture";
import StepTestPanel from "./StepTestPanel";

const actions: Record<FlowAction, string> = {
  open_page: "Abrir página",
  locate: "Localizar elemento",
  fill: "Preencher campo",
  click: "Clicar por seletor",
  click_point: "Click point",
  click_image: "Reconhecer botão (imagem)",
  click_button: "Botão por nome (web)",
  assert: "Confirmar texto",
  assert_image: "Confirmar imagem",
  wait_image: "Aguardar imagem",
  if_exists: "Se o alvo existir",
  pause: "Pedir intervenção do operador",
};
const blankStep = (action: FlowAction = "fill"): Step => ({
  action,
  locator: "",
  value: "",
  data_ref: action === "fill" ? "employee.name" : "",
  timeout_seconds: 30,
  success_condition: "",
  screen_context: null,
  button_text: "",
  reference_image_id: null,
  confidence: 0.9,
  on_match: "finish_success",
  skip_steps: 1,
});
const initialSteps = [
  { ...blankStep("open_page"), value: "https://pilot.invalid/users/new" },
  { ...blankStep(), locator: "#name" },
  {
    ...blankStep("assert"),
    locator: "[role=status]",
    success_condition: "Cadastro concluído",
  },
];

export function AutomationEditor({
  platform,
  onChange,
}: {
  platform: Platform;
  onChange: () => void;
}) {
  const [versions, setVersions] = useState<Automation[]>([]);
  const [name, setName] = useState("Cadastro de colaborador");
  const [steps, setSteps] = useState<Step[]>(
    platform.mode === "local_desktop" ? [] : initialSteps,
  );
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const [testTarget, setTestTarget] = useState<{
    step: Step;
    position: number;
    initialUrl: string;
  } | null>(null);
  async function load(populate = false) {
    const items = await apiGet<Automation[]>(
      `/platforms/${platform.id}/automations`,
    );
    setVersions(items);
    if (populate && items.length) {
      setName(items[0].name);
      setSteps(items[0].steps.map(({ position: _position, ...step }) => step));
    }
    if (populate && !items.length && platform.name.includes("SOL")) {
      const template = await apiGet<{ steps: Step[]; inspection: string }>(
        "/pilot-templates/sol",
      );
      setName("Acesso SOL · PUC Goiás");
      setSteps(template.steps);
      setFeedback(
        template.inspection +
          " Preencha os seletores e a confirmação de sucesso antes de salvar.",
      );
    }
  }
  useEffect(() => {
    void load(true).catch((error) => setFeedback(message(error)));
  }, [platform.id]);
  function changeStep(index: number, change: Partial<Step>) {
    setSteps((current) =>
      current.map((step, i) => (i === index ? { ...step, ...change } : step)),
    );
  }
  function move(index: number, offset: number) {
    setSteps((current) => {
      const copy = [...current];
      const other = index + offset;
      [copy[index], copy[other]] = [copy[other], copy[index]];
      return copy;
    });
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback("");
    try {
      await apiPost(`/platforms/${platform.id}/automations`, { name, steps });
      await load();
      setFeedback("Nova versão salva como rascunho. Valide antes de usar.");
      onChange();
    } catch (error) {
      setFeedback(message(error));
    } finally {
      setBusy(false);
    }
  }
  async function validate(id: string) {
    setBusy(true);
    try {
      const result = await apiPost<{ warnings: string[] }>(
        `/automations/${id}/validate`,
      );
      await load();
      setFeedback(
        result.warnings.join(" ") ||
          "Versão validada e disponível para solicitações.",
      );
      onChange();
    } catch (error) {
      setFeedback(message(error));
    } finally {
      setBusy(false);
    }
  }
  const refs = [
    "employee.name",
    "employee.email",
    "employee.department",
    "employee.employee_id",
    ...platform.fields.map((field) => "platform." + field.key),
  ];
  return (
    <section className="panel editor">
      <div className="panel-title">
        <div>
          <p className="eyebrow">EDITOR DE FLUXO</p>
          <h2>Automação · {platform.name}</h2>
        </div>
        <span className="muted">{versions.length} versões</span>
      </div>
      <div className="notice">
        Modo: {platform.mode}. As versões preservam as etapas. Validação
        confirma a estrutura; execução real exige habilitar o executor na
        máquina autorizada.
      </div>
      <VisualCapture
        onAdd={(step) =>
          setSteps((current) => {
            const end =
              !["assert", "assert_image"].includes(step.action) &&
              current.length &&
              ["assert", "assert_image"].includes(
                current[current.length - 1].action,
              )
                ? current.length - 1
                : current.length;
            return [...current.slice(0, end), step, ...current.slice(end)];
          })
        }
      />
      {feedback && (
        <p role="status" className="notice">
          {feedback}
        </p>
      )}
      {testTarget && (
        <StepTestPanel
          key={testTarget.position}
          platform={platform}
          {...testTarget}
          onClose={() => setTestTarget(null)}
        />
      )}
      <form onSubmit={(event) => void save(event)}>
        <label>
          Nome da automação
          <input
            required
            maxLength={120}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <div className="steps">
          {steps.map((step, index) => (
            <fieldset className="step-card" key={index}>
              <legend>Etapa {index + 1}</legend>
              <div className="step-top">
                <select
                  aria-label={`Ação da etapa ${index + 1}`}
                  value={step.action}
                  onChange={(event) => {
                    const action = event.target.value as FlowAction;
                    changeStep(index, {
                      ...blankStep(action),
                      reference_image_id: [
                        "click_image",
                        "assert_image",
                        "wait_image",
                        "if_exists",
                      ].includes(action)
                        ? step.reference_image_id
                        : null,
                      screen_context:
                        step.screen_context ||
                        (action === "click_point"
                          ? {
                              x: 0,
                              y: 0,
                              width: 1920,
                              height: 1080,
                              window: "Navegador",
                            }
                          : null),
                    });
                  }}
                >
                  {Object.entries(actions).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="button small ghost"
                  disabled={steps.length >= 50}
                  aria-label={`Duplicar etapa ${index + 1}`}
                  onClick={() =>
                    setSteps((current) => [
                      ...current.slice(0, index + 1),
                      structuredClone(step),
                      ...current.slice(index + 1),
                    ])
                  }
                >
                  Duplicar
                </button>
                <button
                  type="button"
                  className="button small primary"
                  aria-label={`Testar etapa ${index + 1}`}
                  onClick={() =>
                    setTestTarget({
                      step: structuredClone(step),
                      position: index + 1,
                      initialUrl:
                        [...steps.slice(0, index + 1)]
                          .reverse()
                          .find((item) => item.action === "open_page")?.value ||
                        "",
                    })
                  }
                >
                  Testar esta etapa
                </button>
                <button
                  type="button"
                  className="button small ghost"
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                  aria-label="Mover etapa para cima"
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="button small ghost"
                  disabled={index === steps.length - 1}
                  onClick={() => move(index, 1)}
                  aria-label="Mover etapa para baixo"
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="button small danger"
                  disabled={steps.length === 1}
                  onClick={() => setSteps(steps.filter((_, i) => i !== index))}
                  aria-label="Remover etapa"
                >
                  ×
                </button>
              </div>
              <div className="form-grid">
                {step.action === "open_page" && (
                  <label>
                    URL de destino
                    <input
                      required
                      type="url"
                      value={step.value}
                      onChange={(event) =>
                        changeStep(index, { value: event.target.value })
                      }
                    />
                  </label>
                )}
                {!(
                  platform.mode === "local_desktop" && step.action === "fill"
                ) &&
                  ["locate", "fill", "click", "assert", "if_exists"].includes(
                    step.action,
                  ) && (
                    <label>
                      Seletor
                      <input
                        required={step.action !== "if_exists"}
                        value={step.locator}
                        onChange={(event) =>
                          changeStep(index, { locator: event.target.value })
                        }
                        placeholder="#email ou [data-testid=submit]"
                      />
                    </label>
                  )}
                {step.action === "fill" && (
                  <label>
                    Referência de dado
                    <input
                      required
                      list="data-refs"
                      value={step.data_ref}
                      onChange={(event) =>
                        changeStep(index, { data_ref: event.target.value })
                      }
                      placeholder="employee.name ou credential.PORTAL_PASSWORD"
                    />
                    <datalist id="data-refs">
                      {refs.map((ref) => (
                        <option key={ref} value={ref} />
                      ))}
                    </datalist>
                    <small>
                      Credenciais: credential.NOME lê AUTOMATION_SECRET_NOME no
                      worker.
                    </small>
                  </label>
                )}
                {step.action === "click_button" && (
                  <label>
                    Nome exato do botão
                    <input
                      required
                      value={step.button_text}
                      onChange={(event) =>
                        changeStep(index, { button_text: event.target.value })
                      }
                      placeholder="Salvar cadastro"
                    />
                  </label>
                )}
                {[
                  "click_image",
                  "assert_image",
                  "wait_image",
                  "if_exists",
                ].includes(step.action) && (
                  <>
                    <label>
                      ID da imagem de referência
                      <input
                        required={step.action !== "if_exists"}
                        value={step.reference_image_id || ""}
                        onChange={(event) =>
                          changeStep(index, {
                            reference_image_id: event.target.value,
                          })
                        }
                        placeholder="Use a captura visual acima"
                      />
                    </label>
                    <label>
                      Confiança mínima
                      <input
                        type="number"
                        min={0.7}
                        max={0.99}
                        step={0.01}
                        value={step.confidence}
                        onChange={(event) =>
                          changeStep(index, {
                            confidence: Number(event.target.value),
                          })
                        }
                      />
                    </label>
                  </>
                )}
                {step.action === "if_exists" && (
                  <>
                    <label>
                      Quando o alvo existir
                      <select
                        value={step.on_match || "finish_success"}
                        onChange={(event) =>
                          changeStep(index, {
                            on_match: event.target.value as Step["on_match"],
                          })
                        }
                      >
                        <option value="finish_success">
                          Encerrar com sucesso (ex.: cadastro já existe)
                        </option>
                        <option value="skip_next">Pular próximas etapas</option>
                        <option value="continue">Continuar normalmente</option>
                      </select>
                    </label>
                    {step.on_match === "skip_next" && (
                      <label>
                        Quantidade a pular
                        <input
                          required
                          type="number"
                          min={1}
                          max={50}
                          value={step.skip_steps || 1}
                          onChange={(event) =>
                            changeStep(index, {
                              skip_steps: Number(event.target.value),
                            })
                          }
                        />
                      </label>
                    )}
                    <p className="muted">
                      Informe seletor ou imagem. Sem correspondência, o fluxo
                      continua.
                    </p>
                  </>
                )}
                <label>
                  Timeout (segundos)
                  <input
                    type="number"
                    min={1}
                    max={300}
                    required
                    value={step.timeout_seconds}
                    onChange={(event) =>
                      changeStep(index, {
                        timeout_seconds: Number(event.target.value),
                      })
                    }
                  />
                </label>
                {step.action === "assert" && (
                  <label>
                    Condição de sucesso
                    <input
                      required
                      value={step.success_condition}
                      onChange={(event) =>
                        changeStep(index, {
                          success_condition: event.target.value,
                        })
                      }
                      placeholder="Texto ou condição reconhecida pelo fluxo"
                    />
                  </label>
                )}
              </div>
              {step.reference_image_id && (
                <img
                  className="reference-thumbnail"
                  src={apiAssetUrl(
                    `/reference-images/${step.reference_image_id}`,
                  )}
                  alt={`Referência visual da etapa ${index + 1}`}
                />
              )}
              {step.action === "pause" && (
                <p className="notice">
                  A execução aguardará confirmação no histórico.
                </p>
              )}
              <button
                type="button"
                className="button small ghost"
                onClick={() =>
                  changeStep(index, {
                    screen_context: step.screen_context
                      ? null
                      : {
                          x: 0,
                          y: 0,
                          width: 1920,
                          height: 1080,
                          window: "Navegador",
                        },
                  })
                }
              >
                {step.screen_context
                  ? "Remover contexto de tela"
                  : "Adicionar contexto de tela"}
              </button>
              {step.screen_context && (
                <>
                  <p className="warning">
                    O contexto protege os cliques: a janela e a resolução devem
                    corresponder à referência.
                  </p>
                  <div className="form-grid">
                    {(["x", "y", "width", "height", "window"] as const).map(
                      (key) => (
                        <label key={key}>
                          {
                            {
                              x: "X",
                              y: "Y",
                              width: "Largura",
                              height: "Altura",
                              window: "Janela",
                            }[key]
                          }
                          <input
                            required
                            type={key === "window" ? "text" : "number"}
                            min={key === "width" || key === "height" ? 1 : 0}
                            value={step.screen_context![key]}
                            onChange={(event) =>
                              changeStep(index, {
                                screen_context: {
                                  ...step.screen_context!,
                                  [key]:
                                    key === "window"
                                      ? event.target.value
                                      : Number(event.target.value),
                                },
                              })
                            }
                          />
                        </label>
                      ),
                    )}
                  </div>
                </>
              )}
            </fieldset>
          ))}
        </div>
        <div className="actions">
          <button
            type="button"
            className="button ghost"
            disabled={steps.length >= 50}
            onClick={() => setSteps([...steps, blankStep()])}
          >
            ＋ Adicionar etapa
          </button>
          <button className="button primary" disabled={busy}>
            Salvar nova versão
          </button>
        </div>
      </form>
      <h3 className="subheading">Histórico de versões</h3>
      <div className="version-list">
        {versions.length ? (
          versions.map((version) => (
            <div className="version-row" key={version.id}>
              <span>
                <b>v{version.version}</b> {version.name}
              </span>
              <Status value={version.status} />
              <button
                className="button small ghost"
                onClick={() => {
                  setName(version.name);
                  setSteps(
                    version.steps.map(
                      ({ position: _position, ...step }) => step,
                    ),
                  );
                  setFeedback(
                    "Versão carregada no editor. Salvar criará uma nova versão.",
                  );
                }}
              >
                Carregar
              </button>
              <button
                className="button small primary"
                disabled={busy || version.status === "validated"}
                onClick={() => void validate(version.id)}
              >
                Validar
              </button>
            </div>
          ))
        ) : (
          <p className="muted">Salve a primeira versão para validar.</p>
        )}
      </div>
    </section>
  );
}

export default function Platforms({
  platforms,
  onChange,
  isAdmin,
}: {
  platforms: Platform[];
  onChange: () => void | Promise<void>;
  isAdmin: boolean;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [selected, setSelected] = useState<Platform | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [active, setActive] = useState(true);
  const [mode, setMode] = useState<Platform["mode"]>("simulation");
  const [fail, setFail] = useState(false);
  const [fields, setFields] = useState<PlatformField[]>([]);
  const [deletionFeedback, setDeletionFeedback] = useState<{
    error: boolean;
    text: string;
  } | null>(null);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  function edit(platform: Platform) {
    setEditing(platform.id);
    setName(platform.name);
    setDescription(platform.description);
    setMode(platform.mode);
    setActive(platform.active);
    setFail(platform.config.simulate_failure);
    setFields(
      platform.fields.map((field) => ({
        key: field.key,
        label: field.label,
        field_type: field.field_type,
        required: field.required,
        options: field.options,
      })),
    );
  }
  function reset() {
    setEditing(null);
    setName("");
    setDescription("");
    setActive(true);
    setMode("simulation");
    setFail(false);
    setFields([]);
  }
  async function remove(platform: Platform) {
    if (
      !isAdmin ||
      busy ||
      !window.confirm(
        `Excluir a plataforma “${platform.name}”? Ela sairá das listas e o histórico de execuções será preservado.`,
      )
    )
      return;
    setBusy(true);
    setDeletionFeedback(null);
    try {
      await apiRequest(`/platforms/${platform.id}`, { method: "DELETE" });
      if (editing === platform.id) reset();
      if (selected?.id === platform.id) setSelected(null);
      await onChange();
      setDeletionFeedback({
        error: false,
        text: "Plataforma excluída. O histórico de execuções foi preservado.",
      });
    } catch (error) {
      setDeletionFeedback({ error: true, text: message(error) });
    } finally {
      setBusy(false);
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback("");
    const body = {
      name,
      description,
      active,
      mode,
      fields,
      config: { simulate_failure: fail },
    };
    try {
      editing
        ? await apiPut(`/platforms/${editing}`, body)
        : await apiPost("/platforms", body);
      reset();
      onChange();
      setSelected(null);
      setFeedback(
        "Plataforma salva. Valide a automação após alterações de configuração.",
      );
    } catch (error) {
      setFeedback(message(error));
    } finally {
      setBusy(false);
    }
  }
  function updateField(index: number, change: Partial<PlatformField>) {
    setFields(
      fields.map((field, i) => (i === index ? { ...field, ...change } : field)),
    );
  }
  return (
    <div className="stack">
      <div className="split">
        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>Plataformas</h2>
              <p>Destinos e suas configurações de cadastro.</p>
            </div>
            <span className="counter">{platforms.length}</span>
          </div>
          {deletionFeedback && (
            <p
              className={deletionFeedback.error ? "alert" : "notice"}
              role={deletionFeedback.error ? "alert" : "status"}
            >
              {deletionFeedback.text}
            </p>
          )}
          {platforms.length ? (
            <div className="platform-list">
              {platforms.map((platform) => (
                <article className="platform-row" key={platform.id}>
                  <div className="platform-symbol">↗</div>
                  <div className="grow">
                    <h3>{platform.name}</h3>
                    <p>
                      {platform.fields.length} campos ·{" "}
                      {platform.mode === "simulation"
                        ? "Simulado"
                        : "Power Automate"}
                    </p>
                    <span
                      className={`status ${platform.active ? "status-succeeded" : "status-cancelled"}`}
                    >
                      {platform.active ? "Ativa" : "Desativada"}
                    </span>
                  </div>
                  <div className="actions vertical">
                    <button
                      className="button small ghost"
                      disabled={busy}
                      onClick={() => edit(platform)}
                    >
                      Editar
                    </button>
                    <button
                      className="button small primary"
                      disabled={busy}
                      onClick={() => setSelected(platform)}
                    >
                      Configurar fluxo
                    </button>
                    {isAdmin && (
                      <button
                        className="button small danger"
                        disabled={busy}
                        aria-label={`Excluir plataforma ${platform.name}`}
                        onClick={() => void remove(platform)}
                      >
                        Excluir
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Adicione o primeiro destino">
              Defina os campos exigidos e depois configure a automação.
            </Empty>
          )}
        </section>
        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>{editing ? "Editar plataforma" : "Nova plataforma"}</h2>
              <p>Configuração sem senhas ou tokens.</p>
            </div>
            {editing && (
              <button className="button small ghost" onClick={reset}>
                Cancelar edição
              </button>
            )}
          </div>
          {feedback && (
            <p className="notice" role="status">
              {feedback}
            </p>
          )}
          {!editing && (
            <button
              type="button"
              className="button small ghost"
              onClick={async () => {
                try {
                  const template = await apiGet<{
                    name: string;
                    description: string;
                    fields: PlatformField[];
                  }>("/pilot-templates/sol");
                  setName(template.name);
                  setDescription(template.description);
                  setFields(template.fields);
                  setMode("local_browser");
                  setFeedback(
                    "Modelo SOL carregado. Depois de salvar, configure os seletores no construtor. A senha será credential.SOL_PASSWORD.",
                  );
                } catch (error) {
                  setFeedback(message(error));
                }
              }}
            >
              Usar modelo SOL · PUC Goiás
            </button>
          )}
          <form onSubmit={(event) => void save(event)}>
            <label>
              Nome da plataforma
              <input
                required
                maxLength={120}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Ex.: Portal de Treinamento"
              />
            </label>
            <label>
              Descrição
              <textarea
                maxLength={2000}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={2}
              />
            </label>
            <label>
              Modo
              <select
                value={mode}
                onChange={(event) =>
                  setMode(event.target.value as Platform["mode"])
                }
              >
                <option value="simulation">Simulação controlada</option>
                <option value="local_browser">
                  Navegador · executor local
                </option>
                <option value="local_desktop">
                  Desktop · imagem e click point
                </option>
                <option value="power_automate">Power Automate</option>
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={active}
                onChange={(event) => setActive(event.target.checked)}
              />{" "}
              Plataforma ativa
            </label>
            {mode === "simulation" && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={fail}
                  onChange={(event) => setFail(event.target.checked)}
                />{" "}
                Simular falha na primeira tentativa
              </label>
            )}
            <div className="label-line">
              <b>Campos adicionais</b>
              <button
                className="button small ghost"
                type="button"
                disabled={fields.length >= 30}
                onClick={() =>
                  setFields([
                    ...fields,
                    {
                      key: "",
                      label: "",
                      field_type: "text",
                      required: true,
                      options: [],
                    },
                  ])
                }
              >
                ＋ Campo
              </button>
            </div>
            {fields.map((field, index) => (
              <fieldset className="field-card" key={index}>
                <legend>Campo {index + 1}</legend>
                <div className="form-grid">
                  <label>
                    Chave
                    <input
                      required
                      pattern="[a-z][a-z0-9_]*"
                      maxLength={60}
                      placeholder="profile"
                      value={field.key}
                      onChange={(event) =>
                        updateField(index, { key: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Rótulo
                    <input
                      required
                      maxLength={120}
                      placeholder="Perfil"
                      value={field.label}
                      onChange={(event) =>
                        updateField(index, { label: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Tipo
                    <select
                      value={field.field_type}
                      onChange={(event) =>
                        updateField(index, {
                          field_type: event.target
                            .value as PlatformField["field_type"],
                          options: [],
                        })
                      }
                    >
                      <option value="text">Texto</option>
                      <option value="email">E-mail</option>
                      <option value="integer">Número inteiro</option>
                      <option value="select">Seleção</option>
                    </select>
                  </label>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={field.required}
                      onChange={(event) =>
                        updateField(index, { required: event.target.checked })
                      }
                    />{" "}
                    Obrigatório
                  </label>
                </div>
                {field.field_type === "select" && (
                  <label>
                    Opções, separadas por vírgula
                    <input
                      required
                      value={field.options.join(",")}
                      onChange={(event) =>
                        updateField(index, {
                          options: event.target.value
                            .split(",")
                            .map((value) => value.trim()),
                        })
                      }
                      placeholder="Colaborador, Gestor"
                    />
                  </label>
                )}
                <button
                  type="button"
                  className="button small danger"
                  onClick={() =>
                    setFields(fields.filter((_, i) => i !== index))
                  }
                >
                  Remover campo
                </button>
              </fieldset>
            ))}
            <button className="button primary full" disabled={busy}>
              {busy ? "Salvando..." : "Salvar plataforma"}
            </button>
          </form>
        </section>
      </div>
      {selected && (
        <AutomationEditor
          key={selected.id}
          platform={
            platforms.find((platform) => platform.id === selected.id) ||
            selected
          }
          onChange={onChange}
        />
      )}
    </div>
  );
}
