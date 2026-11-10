import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  apiGet,
  apiPost,
  setCsrfToken,
} from "../services/api/client";
import { getHealth, type HealthResponse } from "../services/api/health";
import {
  formatDate,
  message,
  type AuditEvent,
  type Platform,
  type ProvisioningRequest,
  type Session,
  type User,
} from "../types";
import { Empty, Icon } from "../components/ui";
import Platforms from "../features/Platforms";
import RequestForm from "../features/RequestForm";
import { RequestDetail, RequestTable } from "../features/Requests";
import Studio from "../features/Studio";
import ServiceStatus from "../features/ServiceStatus";

type View =
  | "studio"
  | "overview"
  | "platforms"
  | "new"
  | "requests"
  | "audit"
  | "users"
  | "system";
const views: { id: View; label: string; admin?: boolean }[] = [
  { id: "studio", label: "Construtor visual", admin: true },
  { id: "overview", label: "Visão geral" },
  { id: "platforms", label: "Plataformas", admin: true },
  { id: "new", label: "Nova solicitação" },
  { id: "requests", label: "Execuções" },
  { id: "audit", label: "Auditoria", admin: true },
  { id: "users", label: "Equipe e acessos", admin: true },
  { id: "system", label: "Diagnóstico", admin: true },
];

function Team() {
  const [users, setUsers] = useState<User[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setUsers(await apiGet<User[]>("/auth/users"));
  }
  useEffect(() => {
    void load().catch((error) => setFeedback(message(error)));
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await apiPost("/auth/users", { username, password, role });
      setPassword("");
      setUsername("");
      await load();
      setFeedback("Acesso criado.");
    } catch (error) {
      setFeedback(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="split">
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Pessoas do workspace</h2>
            <p>
              Administradores configuram. Operadores solicitam e acompanham.
            </p>
          </div>
        </div>
        {users.map((user) => (
          <div className="user-row" key={user.id}>
            <span className="avatar">{user.username[0].toUpperCase()}</span>
            <div className="grow">
              <b>{user.username}</b>
              <small>
                {user.role === "admin" ? "Administrador" : "Operador"} ·{" "}
                {user.active ? "Ativo" : "Desativado"}
              </small>
            </div>
            <button
              className="button small ghost"
              disabled={!user.active || busy}
              onClick={async () => {
                if (!window.confirm(`Desativar o acesso de ${user.username}?`))
                  return;
                setBusy(true);
                try {
                  await apiPost(`/auth/users/${user.id}/disable`);
                  await load();
                } catch (error) {
                  setFeedback(message(error));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Desativar
            </button>
          </div>
        ))}
      </section>
      <section className="panel">
        <h2>Novo acesso</h2>
        {feedback && (
          <p role="status" className="notice">
            {feedback}
          </p>
        )}
        <form onSubmit={(event) => void save(event)}>
          <label>
            Usuário
            <input
              required
              minLength={3}
              pattern="[a-zA-Z0-9._@-]+"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="off"
            />
          </label>
          <label>
            Senha inicial
            <input
              required
              minLength={12}
              maxLength={128}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
            />
            <small>
              Pelo menos 12 caracteres. A senha não será exibida novamente.
            </small>
          </label>
          <label>
            Perfil
            <select
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="operator">Operador</option>
              <option value="admin">Administrador</option>
            </select>
          </label>
          <button className="button primary full" disabled={busy}>
            Criar acesso
          </button>
        </form>
      </section>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [requests, setRequests] = useState<ProvisioningRequest[]>([]);
  const [audits, setAudits] = useState<AuditEvent[]>([]);
  const [view, setView] = useState<View>("studio");
  const [detail, setDetail] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function acceptSession(session: Session) {
    setCsrfToken(session.csrf_token);
    setUser(session.user);
    setView(session.user.role === "admin" ? "studio" : "overview");
  }
  useEffect(() => {
    apiGet<Session>("/auth/me")
      .then(acceptSession)
      .catch(() => {})
      .finally(() => setBooting(false));
  }, []);
  const load = useCallback(async () => {
    if (!user) return;
    try {
      const [destinations, history, state] = await Promise.all([
        apiGet<Platform[]>("/platforms"),
        apiGet<ProvisioningRequest[]>("/provisioning-requests"),
        getHealth(),
      ]);
      setPlatforms(destinations);
      setRequests(history);
      setHealth(state);
    } catch (exception) {
      if (exception instanceof ApiError && exception.status === 401) {
        setUser(null);
        setCsrfToken("");
        setPlatforms([]);
        setRequests([]);
      }
      setError(message(exception));
      setHealth(null);
    }
  }, [user]);
  useEffect(() => {
    void load();
    if (!user) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [load, user]);
  useEffect(() => {
    if (view === "audit" && user?.role === "admin")
      apiGet<AuditEvent[]>("/audit-events")
        .then(setAudits)
        .catch((exception) => setError(message(exception)));
  }, [view, user]);
  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      acceptSession(
        await apiPost<Session>("/auth/login", { username, password }),
      );
      setPassword("");
    } catch (exception) {
      setError(message(exception));
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    try {
      await apiPost("/auth/logout");
    } finally {
      setUser(null);
      setCsrfToken("");
      setPlatforms([]);
      setRequests([]);
      setAudits([]);
      setDetail(null);
      setError("");
    }
  }
  function navigate(next: View) {
    setView(next);
    setDetail(null);
    setError("");
  }
  function created(item: ProvisioningRequest) {
    setDetail(item.id);
    setView("requests");
    void load();
  }
  const executions = requests.flatMap((item) => item.executions);
  const succeeded = executions.filter(
    (execution) => execution.status === "succeeded",
  ).length;
  const queued = executions.filter((execution) =>
    ["queued", "dispatching", "running"].includes(execution.status),
  ).length;
  const failed = executions.filter(
    (execution) => execution.status === "failed",
  ).length;

  if (booting)
    return (
      <div className="boot" role="status">
        <div className="brand-mark">A</div>
        <p>Preparando seu workspace...</p>
      </div>
    );
  if (!user)
    return (
      <main className="login-screen">
        <section className="login-story">
          <a className="brand" href="#">
            <span className="brand-mark">A</span>
            <span>
              Automation<small>PLATFORM</small>
            </span>
          </a>
          <span className="chip">SEU PRÓXIMO FLUXO COMEÇA AQUI</span>
          <h1>
            Transforme cliques
            <br />
            em possibilidades.
          </h1>
          <p>
            Monte automações visuais, conecte suas plataformas e acompanhe cada
            etapa em um só lugar.
          </p>
          <div className="login-flow">
            <span>⌖</span>
            <i />
            <span>↗</span>
            <i />
            <span>✓</span>
          </div>
          <small>Seletores · Reconhecimento de botão · Click point</small>
        </section>
        <section className="login-form">
          <div className="login-card">
            <p className="eyebrow">BEM-VINDO AO WORKSPACE</p>
            <h2>Acesse sua conta</h2>
            <p className="muted">
              Entre para criar e acompanhar suas automações.
            </p>
            {error && (
              <p className="alert" role="alert">
                {error}
              </p>
            )}
            <form onSubmit={(event) => void login(event)}>
              <label>
                Usuário
                <input
                  required
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  placeholder="Seu usuário"
                />
              </label>
              <label>
                Senha
                <input
                  required
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  placeholder="Sua senha"
                />
              </label>
              <button className="button primary full" disabled={busy}>
                {busy ? "Entrando..." : "Entrar no workspace →"}
              </button>
            </form>
            <p className="login-help">
              Primeiro acesso? Solicite uma conta ao administrador da
              plataforma.
            </p>
          </div>
          <small className="login-footer">
            Automation Platform · Construa. Execute. Acompanhe.
          </small>
        </section>
      </main>
    );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#studio"
          onClick={(event) => {
            event.preventDefault();
            navigate(user.role === "admin" ? "studio" : "overview");
          }}
        >
          <span className="brand-mark">A</span>
          <span>
            Automation<small>PLATFORM</small>
          </span>
        </a>
        <p className="nav-label">SEU WORKSPACE</p>
        <nav aria-label="Menu principal">
          {views
            .filter((item) => !item.admin || user.role === "admin")
            .map((item) => (
              <button
                key={item.id}
                className={`nav-item ${view === item.id ? "active" : ""}`}
                onClick={() => navigate(item.id)}
              >
                <Icon name={item.id === "studio" ? "new" : item.id} />
                <span>{item.label}</span>
                {item.id === "requests" && queued > 0 && <b>{queued}</b>}
              </button>
            ))}
        </nav>
        <div className="sidebar-note">
          <span>✦</span>
          <b>Um fluxo de cada vez.</b>
          <p>Valide suas etapas antes de conectar um destino real.</p>
        </div>
        <div className="sidebar-user">
          <span className="avatar">{user.username[0].toUpperCase()}</span>
          <div className="grow">
            <b>{user.username}</b>
            <small>
              {user.role === "admin" ? "Administrador" : "Operador"}
            </small>
          </div>
          <button
            className="logout"
            aria-label="Sair"
            onClick={() => void logout()}
          >
            ↪
          </button>
        </div>
      </aside>
      <main className="main-content">
        <div className="topbar">
          <span>
            Workspace <b>/</b> {views.find((item) => item.id === view)?.label}
          </span>
          <span className={`api-state ${health ? "connected" : ""}`}>
            <i />
            {health ? "API conectada" : "Verificando API"}
            <button
              className="mobile-logout button small ghost"
              onClick={() => void logout()}
            >
              Sair
            </button>
          </span>
        </div>
        <header className="page-heading">
          <div>
            <p className="eyebrow">AUTOMATION WORKSPACE</p>
            <h1>
              {detail
                ? "Detalhes da execução"
                : views.find((item) => item.id === view)?.label}
            </h1>
            <p>
              {view === "studio"
                ? "Crie sua própria automação, do primeiro clique à confirmação final."
                : "Configure, execute e acompanhe seus fluxos com clareza."}
            </p>
          </div>
          {view !== "new" && (
            <button className="button primary" onClick={() => navigate("new")}>
              ＋ Nova solicitação
            </button>
          )}
        </header>
        {error && (
          <div className="alert" role="alert">
            {error}
            <button
              className="dismiss"
              onClick={() => setError("")}
              aria-label="Fechar erro"
            >
              ×
            </button>
          </div>
        )}
        {view === "studio" && user.role === "admin" && (
          <Studio
            platforms={platforms}
            onChange={() => void load()}
            onCreated={created}
            onConfigure={() => navigate("platforms")}
          />
        )}
        {view === "overview" && (
          <div className="stack">
            <section className="stats-grid">
              <article className="stat-card">
                <span className="stat-icon purple">
                  <Icon name="platforms" />
                </span>
                <span>Plataformas ativas</span>
                <strong>
                  {platforms.filter((platform) => platform.active).length}
                </strong>
                <small>destinos no workspace</small>
              </article>
              <article className="stat-card">
                <span className="stat-icon blue">
                  <Icon name="requests" />
                </span>
                <span>Em andamento</span>
                <strong>{queued}</strong>
                <small>na fila ou em execução</small>
              </article>
              <article className="stat-card">
                <span className="stat-icon green">✓</span>
                <span>Concluídas</span>
                <strong>{succeeded}</strong>
                <small>execuções confirmadas</small>
              </article>
              <article className="stat-card">
                <span className="stat-icon orange">!</span>
                <span>Precisam de atenção</span>
                <strong>{failed}</strong>
                <small>falhas no histórico recente</small>
              </article>
            </section>
            <section className="panel">
              <div className="panel-title">
                <div>
                  <h2>Atividade recente</h2>
                  <p>Acompanhe o resultado de cada destino.</p>
                </div>
                <button
                  className="button ghost small"
                  onClick={() => navigate("requests")}
                >
                  Ver todas →
                </button>
              </div>
              <RequestTable
                requests={requests.slice(0, 8)}
                onSelect={(id) => {
                  setView("requests");
                  setDetail(id);
                }}
              />
            </section>
          </div>
        )}
        {view === "system" && user.role === "admin" && <ServiceStatus />}
        {view === "platforms" && user.role === "admin" && (
          <Platforms
            platforms={platforms}
            onChange={load}
            isAdmin={user.role === "admin"}
          />
        )}
        {view === "new" && (
          <RequestForm platforms={platforms} onCreated={created} />
        )}
        {view === "requests" &&
          (detail ? (
            <RequestDetail
              key={detail}
              id={detail}
              isAdmin={user.role === "admin"}
              onBack={() => setDetail(null)}
              onUpdate={() => void load()}
            />
          ) : (
            <section className="panel">
              <div className="panel-title">
                <div>
                  <h2>Histórico de execuções</h2>
                  <p>Últimas 50 solicitações · atualização automática</p>
                </div>
                <span className="counter">{requests.length}</span>
              </div>
              <RequestTable requests={requests} onSelect={setDetail} />
            </section>
          ))}
        {view === "audit" && (
          <section className="panel">
            <div className="panel-title">
              <div>
                <h2>Trilha de auditoria</h2>
                <p>Alterações administrativas e ações do workspace.</p>
              </div>
              <span className="chip">SOMENTE ADMINISTRADORES</span>
            </div>
            {audits.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>HORÁRIO</th>
                      <th>AÇÃO</th>
                      <th>ATOR</th>
                      <th>RECURSO</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audits.map((event) => (
                      <tr key={event.id}>
                        <td>{formatDate(event.created_at)}</td>
                        <td>{event.action}</td>
                        <td>{event.actor_id?.slice(0, 8) || "Sistema"}</td>
                        <td>{event.resource_id.slice(0, 12)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Sem eventos">
                As próximas ações administrativas aparecerão aqui.
              </Empty>
            )}
          </section>
        )}
        {view === "users" && user.role === "admin" && <Team />}
        <footer className="app-footer">
          <span>Automation Platform · Workspace local</span>
          <span>
            {health ? `v${health.version}` : "Conexão em verificação"}
          </span>
        </footer>
      </main>
    </div>
  );
}
