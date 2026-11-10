import { useRef, useState, type FormEvent } from "react";
import { apiPost } from "../services/api/client";
import {
  message,
  type Employee,
  type Platform,
  type ProvisioningRequest,
} from "../types";

const blankEmployee: Employee = {
  name: "",
  email: "",
  department: "",
  employee_id: "",
};
export function EmployeeFields({
  value,
  onChange,
}: {
  value: Employee;
  onChange: (value: Employee) => void;
}) {
  return (
    <div className="form-grid">
      {(["name", "email", "department", "employee_id"] as const).map((key) => (
        <label key={key}>
          {
            {
              name: "Nome completo",
              email: "E-mail corporativo",
              department: "Departamento",
              employee_id: "Matrícula",
            }[key]
          }
          <input
            required
            minLength={key === "name" ? 2 : 1}
            maxLength={key === "email" ? 254 : key === "employee_id" ? 60 : 120}
            type={key === "email" ? "email" : "text"}
            value={value[key]}
            onChange={(event) =>
              onChange({ ...value, [key]: event.target.value })
            }
          />
        </label>
      ))}
    </div>
  );
}
export function DynamicFields({
  platform,
  value,
  onChange,
}: {
  platform: Platform;
  value: Record<string, string | number>;
  onChange: (value: Record<string, string | number>) => void;
}) {
  return (
    <div className="form-grid">
      {platform.fields.map((field) => (
        <label key={field.key}>
          {field.label}
          {field.required ? " *" : " (opcional)"}
          {field.field_type === "select" ? (
            <select
              required={field.required}
              value={value[field.key] ?? ""}
              onChange={(event) =>
                onChange({ ...value, [field.key]: event.target.value })
              }
            >
              <option value="">Selecione</option>
              {field.options.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
          ) : (
            <input
              required={field.required}
              maxLength={500}
              type={
                field.field_type === "integer"
                  ? "number"
                  : field.field_type === "email"
                    ? "email"
                    : "text"
              }
              step={field.field_type === "integer" ? 1 : undefined}
              value={value[field.key] ?? ""}
              onChange={(event) =>
                onChange({
                  ...value,
                  [field.key]:
                    field.field_type === "integer" && event.target.value !== ""
                      ? Number(event.target.value)
                      : event.target.value,
                })
              }
            />
          )}
        </label>
      ))}
    </div>
  );
}
export default function RequestForm({
  platforms,
  onCreated,
}: {
  platforms: Platform[];
  onCreated: (item: ProvisioningRequest) => void;
}) {
  const [employee, setEmployee] = useState<Employee>(blankEmployee);
  const [selected, setSelected] = useState<string[]>([]);
  const [values, setValues] = useState<
    Record<string, Record<string, string | number>>
  >({});
  const [review, setReview] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submission = useRef({ payload: "", key: "" });
  const available = platforms.filter((platform) => platform.active);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!selected.length) {
      setError("Selecione pelo menos uma plataforma.");
      return;
    }
    if (!review) {
      setReview(true);
      return;
    }
    const payload = {
      employee,
      targets: selected.map((id) => ({
        platform_id: id,
        fields: values[id] || {},
      })),
    };
    const serialized = JSON.stringify(payload);
    if (submission.current.payload !== serialized)
      submission.current = { payload: serialized, key: crypto.randomUUID() };
    setBusy(true);
    try {
      onCreated(
        await apiPost<ProvisioningRequest>("/provisioning-requests", payload, {
          "Idempotency-Key": submission.current.key,
        }),
      );
    } catch (exception) {
      setError(message(exception));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel request-form">
      <div className="wizard">
        <span className={!review ? "current" : "done"}>
          1 <b>Dados e destinos</b>
        </span>
        <i />
        <span className={review ? "current" : ""}>
          2 <b>Revisão e envio</b>
        </span>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <form onSubmit={(event) => void submit(event)}>
        {!review ? (
          <>
            <h2>Quem será cadastrado?</h2>
            <p className="muted">
              Preencha os dados comuns e escolha os destinos.
            </p>
            <EmployeeFields value={employee} onChange={setEmployee} />
            <h3 className="subheading">Selecione as plataformas</h3>
            <div className="destination-grid">
              {available.map((platform) => (
                <label
                  className={`destination ${selected.includes(platform.id) ? "selected" : ""}`}
                  key={platform.id}
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(platform.id)}
                    onChange={(event) =>
                      setSelected(
                        event.target.checked
                          ? [...selected, platform.id]
                          : selected.filter((id) => id !== platform.id),
                      )
                    }
                  />
                  <span>
                    <b>{platform.name}</b>
                    <small>
                      {platform.mode === "simulation"
                        ? "Simulação"
                        : platform.mode.replaceAll("_", " ")}
                    </small>
                  </span>
                </label>
              ))}
            </div>
            {!available.length && (
              <p className="notice">
                Peça a um administrador para configurar e validar uma
                plataforma.
              </p>
            )}
            {available
              .filter((platform) => selected.includes(platform.id))
              .map((platform) => (
                <fieldset className="target-fields" key={platform.id}>
                  <legend>{platform.name}</legend>
                  {platform.fields.length ? (
                    <DynamicFields
                      platform={platform}
                      value={values[platform.id] || {}}
                      onChange={(value) =>
                        setValues({ ...values, [platform.id]: value })
                      }
                    />
                  ) : (
                    <p className="muted">
                      Este destino não exige campos adicionais.
                    </p>
                  )}
                </fieldset>
              ))}
          </>
        ) : (
          <>
            <h2>Revise a solicitação</h2>
            <p className="muted">
              Cada destino terá uma execução e um resultado independente.
            </p>
            <dl className="review-data">
              <div>
                <dt>Colaborador</dt>
                <dd>{employee.name}</dd>
              </div>
              <div>
                <dt>E-mail</dt>
                <dd>{employee.email}</dd>
              </div>
              <div>
                <dt>Departamento</dt>
                <dd>{employee.department}</dd>
              </div>
              <div>
                <dt>Matrícula</dt>
                <dd>{employee.employee_id}</dd>
              </div>
            </dl>
            {available
              .filter((platform) => selected.includes(platform.id))
              .map((platform) => (
                <div className="review-target" key={platform.id}>
                  <h3>{platform.name}</h3>
                  <p className="muted">
                    {platform.mode === "simulation"
                      ? "Nenhuma conta externa será criada."
                      : "O worker executará o fluxo configurado neste destino."}
                  </p>
                  {Object.entries(values[platform.id] || {}).map(
                    ([key, value]) => (
                      <p key={key}>
                        <b>
                          {
                            platform.fields.find((field) => field.key === key)
                              ?.label
                          }
                          :
                        </b>{" "}
                        {value}
                      </p>
                    ),
                  )}
                </div>
              ))}
          </>
        )}
        <div className="actions end">
          {review && (
            <button
              type="button"
              className="button ghost"
              disabled={busy}
              onClick={() => setReview(false)}
            >
              Voltar e editar
            </button>
          )}
          <button
            className="button primary"
            disabled={busy || !available.length}
          >
            {busy
              ? "Enviando..."
              : review
                ? "Confirmar solicitação"
                : "Revisar solicitação →"}
          </button>
        </div>
      </form>
    </section>
  );
}
