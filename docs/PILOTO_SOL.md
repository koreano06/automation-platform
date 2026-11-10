# Piloto SOL · PUC Goiás

Destino informado: https://sol.pucgoias.edu.br/menu.asp. Fluxo inicial: abrir a página, informar matrícula e senha, acionar a entrada e confirmar um elemento exclusivo da área autenticada.

## Estado verificado em 10/11/2026

A tentativa pública por Chromium retornou HTTP 403 / "Just a moment...". Nenhuma credencial foi usada e nenhum login foi enviado. Não foi possível confirmar os seletores reais dos campos/botão nem o elemento de sucesso.

O projeto inclui um modelo de configuração com seletores em branco. Ele precisa ser configurado no navegador autorizado antes de salvar e validar a versão.

## Configurar

1. Em Plataformas, use "Usar modelo SOL · PUC Goiás" e salve o destino.
2. No Construtor visual, escolha a plataforma. O modelo propõe URL, matrícula, senha, clique e confirmação.
3. Abra o SOL no navegador autorizado e preencha os seletores reais no editor.
4. A matrícula usa platform.matricula. A senha usa credential.SOL_PASSWORD. Não cole a senha na configuração, no chat ou no Git.
5. A confirmação deve aparecer exclusivamente depois de um login bem-sucedido.
6. Comece por "Testar esta etapa" em modo de reconhecimento. Esse teste abre uma sessão isolada; ações anteriores não são repetidas.

Se o destino continuar bloqueando a automação, será necessário um meio autorizado de integração ou orientação da administração da plataforma. A entrega não tenta contornar o bloqueio.

## Credencial local

Após instalar o extra Browser e configurar a versão, execute:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-SolPilot.ps1

O script pede a senha com entrada oculta, habilita o executor em navegador visível, autoriza sol.pucgoias.edu.br e passa a credencial pelo ambiente dos processos. Não grava a senha em arquivo e restaura o ambiente do terminal ao terminar. A cópia do worker fica em memória até o processo encerrar.

O script não envia matrícula/senha nem enfileira ações automaticamente. Você confirma a execução na interface. Domínios adicionais legítimos precisam ser identificados e autorizados caso o fluxo os utilize.

## Pendências do piloto real

- Acesso autorizado à página no navegador de execução.
- Seletores reais de matrícula, senha e botão.
- Confirmação exclusiva de login bem-sucedido.
- Teste com a conta do usuário, fornecendo a senha somente na máquina local.
