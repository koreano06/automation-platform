# Automation Platform

Construtor de automações por plataforma, com click points, reconhecimento de botões por imagem ou nome acessível, seletores e confirmação de resultado. React/TypeScript/Vite no frontend; Python 3.13, FastAPI, SQLAlchemy, Alembic e SQLite no backend.

Versão 0.3: teste individual de etapas, prévia esquemática do alvo, duplicação, decisões, pausa com intervenção e diagnóstico dos serviços. Consulte [a entrega 0.3](docs/ENTREGA_0_3.md) e [o piloto SOL](docs/PILOTO_SOL.md).

Você pode criar fluxos genéricos ou solicitações de cadastro para vários destinos, com uma execução e um resultado independente por plataforma.

## Começar no Windows

Requisitos: Python 3.13 completo e Node.js 22.12+ (ou outra versão compatível com Vite 7).

No PowerShell na raiz:

```powershell
.\scripts\Setup.ps1 -Browser
.\scripts\Manage.ps1 create-admin -Username admin
.\scripts\Manage.ps1 seed-demo
.\scripts\Start-Dev.ps1
```

O administrador define a senha no terminal. Não há senha padrão. seed-demo é opcional. Abra http://127.0.0.1:5173. Para parar, execute .\scripts\Stop-Dev.ps1.

Após alterações de código, atualize com powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Restart-Dev.ps1. O comando encerra os serviços registrados, aplica migrações com backup SQLite e inicia a versão atual. Se o Windows negar o encerramento, execute no terminal que iniciou os serviços ou no PowerShell como administrador.

O ambiente desta entrega possui Python portátil em .tools para as verificações locais; o executor desktop precisa de Python completo com Tkinter. Scripts preferem backend/.venv quando disponível.

## Usar o construtor

1. Em Plataformas, cadastre um destino, seus campos não secretos e o modo (simulação, navegador local, desktop local ou Power Automate).
2. Em Construtor visual, escolha o destino. Carregue uma captura e selecione um botão/imagem ou um ponto de clique.
3. Defina e ordene as etapas. Use uma confirmação textual ou por imagem como última etapa.
4. Salve uma versão e valide. Versões anteriores e snapshots de execuções ficam preservados.
5. Preencha os dados do fluxo e enfileire a versão validada, ou use Nova solicitação para vários destinos.
6. Acompanhe estados e eventos em Execuções.

O modo simulado não realiza ações externas. Os executores reais são opcionais e precisam ser habilitados na máquina. Reconhecimento por imagem depende da aparência/escala; pontos dependem do contexto da tela. A documentação explica os limites.

## Implementado

- Plataformas, campos dinâmicos, versões e etapas ordenadas.
- Exclusão de plataformas somente para administradores, com confirmação, auditoria e preservação do histórico. Execuções pendentes precisam ser concluídas ou canceladas antes da exclusão.
- Captura visual com recorte local, click points, imagem, seletores e botão por nome.
- Fila persistente, worker separado, eventos, falhas parciais, idempotência e retomada controlada.
- Autenticação por sessão HttpOnly, proteção CSRF, perfis administrador/operador e auditoria.
- Executor de navegador e executor desktop Windows opcionais.
- Adaptador HTTP Power Automate, correlação, callbacks HMAC e protocolo documentado; ainda sem fluxo Microsoft real conectado.
- Migrações, backup com referências visuais, testes e workflow de CI.
- Diagnóstico do worker/banco/API, teste de etapa sem ação por padrão, decisões, intervenção do operador e evidências temporárias somente para administradores.

## Documentação

- [Relatório de entrega e pendências](docs/RELATORIO_DE_ENTREGA.md)
- [Piloto, contratos e critérios de aceite](docs/PILOTO_E_CONTRATOS.md)
- [Operação, executores, backup e implantação](docs/OPERACAO.md)
- [Contrato Power Automate](docs/POWER_AUTOMATE.md)

## Verificação

Backend, com o ambiente ativado, na pasta backend:

```powershell
python -m pytest -q
python -m ruff check app tests
python -m pip check
python -m alembic check
```

Para incluir os dois testes de navegador real, instale os extras runner e Chromium, então defina PLAYWRIGHT_TESTS=1 antes do pytest. Os testes de navegador usam apenas uma página local controlada.

Frontend, na pasta frontend:

```powershell
npm run typecheck
npm test
npm run build
```

Aceite da interface completa, na raiz, com frontend instalado e extras runner/Chromium:

```powershell
python scripts/browser_smoke.py
```

Esse script inicia serviços temporários, usa banco/credenciais descartáveis, percorre o fluxo pela interface e encerra os processos. Capturas de dados fictícios ficam em docs/verification/.

O schema antigo do MVP sem controle Alembic não é convertido automaticamente. O comando de migração o detecta e exige intervenção para preservar dados. O piloto SOL depende de seletores e acesso autorizados; a inspeção pública foi bloqueada por HTTP 403.

Para gerar um ZIP de entrega em outra máquina, execute scripts/Package.ps1. O pacote contém código/build e manifesto de hashes; banco, credenciais e ferramentas locais são excluídos.
