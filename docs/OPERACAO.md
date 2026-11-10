# Operação local e preparação de implantação

O piloto usa SQLite em disco e um worker separado na mesma máquina. A API não aguarda as ações terminarem. Dados/estados/eventos ficam no banco, não na memória da API.

## Instalação e início

Use Python 3.13 completo e Node.js 22.12+ ou compatível com Vite 7. Em PowerShell na raiz:

```powershell
.\scripts\Setup.ps1 -Browser
.\scripts\Manage.ps1 create-admin -Username admin
.\scripts\Manage.ps1 seed-demo
.\scripts\Start-Dev.ps1
```

O comando de criação pede a senha sem exibir nem gravar o texto puro. Não há senha padrão. O seed é opcional e cria dados fictícios. O frontend fica em http://127.0.0.1:5173 e a documentação da API em http://127.0.0.1:8000/docs.

Parar: .\scripts\Stop-Dev.ps1. O script confere PID e horário de início antes de encerrar os processos registrados. Logs técnicos ficam em data/*.log, ignorados pelo Git.

Para aplicar alterações e reiniciar em um único comando, use .\scripts\Restart-Dev.ps1. Start-Dev.ps1 agora aplica as migrações antes de iniciar os serviços; se houver atualização pendente no SQLite, o comando de migração faz backup antes de alterar o schema. A inicialização também confere a presença da rota DELETE de plataformas. Portas já ocupadas são detectadas antes de modificar o banco.

Se a política local bloquear arquivos .ps1, é possível executar cada script em um processo temporário, por exemplo: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-Dev.ps1. Isso não altera a política permanente da máquina. Na verificação desta entrega, essa forma foi necessária e o início/encerramento dos três serviços passou.

No workspace desta entrega, .tools/python contém um Python portátil utilizado nas verificações. Scripts aceitam esse fallback; ele não inclui Tkinter. Para o executor desktop, instale o Python completo e crie backend/.venv antes de rodar Setup.ps1 -Desktop.

## Configuração

backend/.env é carregado por caminho absoluto; consulte backend/.env.example. O SQLite padrão aponta para data/automation_platform.db na raiz, independente do diretório atual. Um caminho SQLite relativo personalizado também é resolvido contra a raiz do projeto.

frontend/.env define VITE_API_BASE_URL. Use consistentemente 127.0.0.1 ou localhost nos dois serviços para os cookies funcionarem. Em produção, usar HTTPS e COOKIE_SECURE=true. ALLOWED_ORIGINS deve ser uma lista JSON das origens exatas permitidas.

## Execução local real

Navegador:

```powershell
.\scripts\Setup.ps1 -Browser
```

No backend/.env, configure LOCAL_RUNNER_ENABLED=true, BROWSER_HEADLESS=false para acompanhar visualmente e LOCAL_ALLOWED_HOSTS como lista JSON de todos os domínios autorizados (incluindo domínios necessários de autenticação/recursos). Reinicie o worker. Browser abre uma sessão isolada; não reutiliza automaticamente o navegador pessoal.

Desktop:

```powershell
.\scripts\Setup.ps1 -Desktop
```

Use Python completo com Tkinter, uma sessão Windows interativa desbloqueada, tela primária, escala/resolução estáveis e a aplicação correta em primeiro plano. Configure modo local_desktop, contexto de tela em cada etapa e LOCAL_RUNNER_ENABLED=true. O aplicativo deve estar aberto; o executor não inicia processos arbitrários. Mover o mouse para um canto aciona o fail-safe do PyAutoGUI. Não execute em paralelo dois workers de desktop que compartilhem a mesma tela.

Desktop reconhece imagens, usa pontos, preenche o controle focado com Unicode e confirma imagens. Navegador acrescenta URL, seletores, nome acessível e confirmação textual.

Na versão 0.3, Diagnóstico mostra o worker e o schema. Testar esta etapa cria um trabalho independente e reconhece o alvo sem agir por padrão. Condições podem encerrar com sucesso ou pular etapas mantendo a confirmação final. Pausas aguardam confirmação no histórico. Evidências são diagramas sem pixels da tela, disponíveis ao administrador por ARTIFACT_RETENTION_HOURS (24 horas por padrão).

Credenciais usam data_ref credential.NOME e são lidas exclusivamente de AUTOMATION_SECRET_NOME no ambiente do worker. Não cole senhas em campos de plataforma, seletores, URLs ou imagens. Integrações remotas resolvem as credenciais no próprio destino.

## Recuperação e repetição

Execuções pendentes sobrevivem ao reinício. O worker detecta dispatching/running sem heartbeat pelo timeout configurado. Simulações podem voltar à fila até MAX_ATTEMPTS. Execuções reais são marcadas como resultado incerto; não são repetidas automaticamente. Repetição externa só é liberada com garantia configurada de idempotência. Execuções locais reais não permitem repetição automática, pois as ações podem já ter ocorrido.

Cancelamento antes do despacho remove o item da fila. Em execuções locais iniciadas, o cancelamento é cooperativo nos pontos de controle; uma ação em andamento pode terminar antes da interrupção. Cancelamento remoto do Power Automate continua dependendo de suporte do destino.

## Migrações e backup

Pare API e worker antes de migrar. Faça backup:

```powershell
.\scripts\Manage.ps1 backup
.\scripts\Manage.ps1 migrate
```

O backup SQLite usa a API de backup consistente e copia os recortes referenciados para data/backups/<timestamp>/. Guarde o backup com o mesmo controle de acesso aplicado ao banco, que contém os dados não secretos solicitados. Para restaurar, pare processos, preserve o banco atual e restaure o .db e reference-images do mesmo backup. Credenciais por ambiente são configuradas separadamente.

Um banco do MVP antigo sem controle Alembic é recusado pelo comando migrate para evitar sobrescrita. Exporte os dados/prepare uma migração específica antes de reutilizá-lo; não há conversão automática desse formato.

## Produção

A decisão de banco/servidor de produção ainda depende do ambiente. A base não inclui promessa de suporte operacional a outros bancos: escolha e valide driver, migrações, concorrência, HTTPS, backup, retenção e identidade antes de implantar. Um SQLite local e um worker são a configuração validada nesta entrega.

CI está em .github/workflows/ci.yml; executa testes, navegação controlada, validação das migrações, typecheck e build quando o código for enviado ao GitHub. Esta entrega não faz publicação remota automaticamente.
