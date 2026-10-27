import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "../services/api/health";

type EstadoConexao = "carregando" | "conectada" | "erro";

export default function App() {
  const [estado, setEstado] = useState<EstadoConexao>("carregando");
  const [saude, setSaude] = useState<HealthResponse | null>(null);
  const [mensagemErro, setMensagemErro] = useState("");

  async function verificarConexao() {
    setEstado("carregando");
    setMensagemErro("");

    try {
      const resultado = await getHealth();
      setSaude(resultado);
      setEstado("conectada");
    } catch {
      setSaude(null);
      setMensagemErro(
        "Não foi possível conectar à API. Verifique se o servidor está em execução.",
      );
      setEstado("erro");
    }
  }

  useEffect(() => {
    void verificarConexao();
  }, []);

  return (
    <main>
      <header>
        <p className="sobretitulo">PAINEL DE CONTROLE</p>
        <h1>Automation Platform</h1>
        <p>
          Gerencie, execute e monitore suas automações em um único lugar.
        </p>
      </header>

      <section className="painel" aria-labelledby="titulo-conexao">
        <div className="cabecalho-painel">
          <div>
            <h2 id="titulo-conexao">Conexão com a API</h2>
            <p>Estado da comunicação com o servidor.</p>
          </div>

          <span
            className={`indicador indicador-${estado}`}
            role="status"
            aria-live="polite"
          >
            {estado === "carregando" && "Verificando..."}
            {estado === "conectada" && "Conectada"}
            {estado === "erro" && "Desconectada"}
          </span>
        </div>

        {estado === "carregando" && (
          <p>Carregando informações do servidor...</p>
        )}

        {estado === "conectada" && saude && (
          <dl className="detalhes">
            <div>
              <dt>Status</dt>
              <dd>Operacional</dd>
            </div>
            <div>
              <dt>Aplicação</dt>
              <dd>{saude.app_name}</dd>
            </div>
            <div>
              <dt>Versão</dt>
              <dd>{saude.version}</dd>
            </div>
            <div>
              <dt>Ambiente</dt>
              <dd>
                {saude.environment === "development"
                  ? "Desenvolvimento"
                  : saude.environment}
              </dd>
            </div>
          </dl>
        )}

        {estado === "erro" && (
          <p className="mensagem-erro" role="alert">
            {mensagemErro}
          </p>
        )}

        <button
          type="button"
          onClick={() => void verificarConexao()}
          disabled={estado === "carregando"}
        >
          {estado === "carregando" ? "Verificando..." : "Verificar novamente"}
        </button>
      </section>

      <footer>
        <p>Automation Platform · Ambiente de desenvolvimento</p>
      </footer>
    </main>
  );
}
