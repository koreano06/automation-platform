# Entrega 0.3 — 10/11/2026

## Adicionado

- Diagnóstico administrativo: versão/build da API, migração aplicada/esperada, banco, fila e worker conectado/desatualizado/desconectado.
- Worker com sinal de atividade persistido e identificação do trabalho atual.
- Teste individual de etapa, persistido na fila. O padrão reconhece o alvo sem clicar/preencher, em uma sessão isolada com URL inicial explícita.
- Duplicação profunda de etapas e visualização da referência do botão.
- Ações Aguardar imagem, Se alvo existir (encerrar com sucesso, pular ou continuar) e Pedir intervenção.
- Continuação pelo operador e cancelamento cooperativo nos pontos de controle dos executores locais.
- Falha identificada por etapa/ação e geometria do alvo, com evidência esquemática disponível somente a administradores.
- Retenção configurável de evidências (24 horas por padrão), com remoção pelo worker.
- Modelo de piloto SOL · PUC Goiás e script de credencial local com entrada oculta.
- Pacote ZIP com build e manifesto SHA-256, excluindo banco, segredos, ambientes virtuais e ferramentas.
- Git ligado ao histórico de origin/main e CI para as verificações em uma revisão.

## Limites

As prévias são diagramas de posição/tamanho do alvo; não reproduzem conteúdo real da tela. Não há coleta de screenshots reais ou traces brutos do Playwright, que podem conter dados e tráfego sensíveis.

O teste individual não reaproveita a sessão pessoal do navegador nem repete cliques/preenchimentos anteriores. Etapas após login devem ser verificadas no fluxo completo com credenciais locais e intervenção quando necessária.

Pausa mantém a sessão enquanto o worker está vivo, pelo timeout da etapa. Reiniciar o processo não reconstrói a sessão do navegador/desktop. O resultado precisa ser conferido. Cancelamento é cooperativo; uma ação em andamento pode terminar antes da interrupção.

As novas ações no Power Automate exigem implementação correspondente no fluxo remoto.

## Piloto real

O SOL respondeu 403 / Just a moment na inspeção pública. O modelo está preparado, mas login real não foi feito. Consulte PILOTO_SOL.md para configurar alvos no ambiente autorizado.

Desktop continua exigindo Python completo, sessão Windows interativa e validação nas telas do usuário.

## Atualizar e empacotar

Atualizar os serviços:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Restart-Dev.ps1

O comando aplica 0005_studio_tools, faz backup SQLite e inicia os serviços. Se o Windows negar o encerramento, execute no terminal que iniciou o projeto ou no PowerShell como administrador.

Gerar pacote:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Package.ps1

Saída: release/automation-platform-0.3.0.zip e .zip.sha256, incluindo RELEASE-MANIFEST.json. Na outra máquina, extraia e siga Setup.ps1 -Browser e a criação do administrador do README. Não há credenciais padrão ou cópia do banco do desenvolvedor.

## Verificação

Os testes abrangem permissões, fila/preview, artefatos/expiração, heartbeat, pausa/continuação, decisões e diagnóstico sem valores de entrada. Chromium usa páginas locais controladas. O aceite da interface inclui duplicação, teste individual, versão/validação, dois destinos, falha/repetição e exclusão com histórico.

Os resultados finais e o estado do CI são apresentados na revisão. Implantação em produção e validação no SOL dependem do ambiente real.
