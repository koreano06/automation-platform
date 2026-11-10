# Varredura de arquivos sensíveis — 10/11/2026

## Escopo e resultado

Foi usado Gitleaks 8.30.1, obtido da distribuição oficial com verificação do digest. A varredura cobriu o histórico disponível do repositório e uma cópia local dos arquivos próprios do projeto, incluindo fontes, exemplos de ambiente, build, logs e ZIP de entrega. Dependências de terceiros e ferramentas locais foram excluídas da análise de conteúdo; essas pastas já são ignoradas.

- Histórico anterior à revisão: 4 commits analisados, sem detecção de vazamento.
- Revisão-base: 118 arquivos rastreados, sem arquivo sensível correspondente às regras do Git ignorado indevidamente no índice.
- Arquivos locais em data/, release/ e docs/verification/: 22 encontrados e 22 protegidos.
- Regras verificadas com 22 caminhos sensíveis e 13 caminhos de código/modelos que precisam continuar versionáveis.
- Um alerta do pacote foi conferido: era o SHA-256 de um arquivo no RELEASE-MANIFEST.json, confirmado contra o conteúdo do ZIP, e não uma credencial.
- Não foram identificadas credenciais reais nos arquivos próprios analisados.

Os relatórios detalhados, redigidos para não exibir segredos, ficam somente em .tools/security-scan/, fora do Git.

## Proteções adicionadas

- Toda a pasta data/, incluindo futuros CSV/JSON com dados, bancos, backups, capturas, referências visuais, artefatos e estado dos processos.
- Bancos e arquivos auxiliares SQLite em qualquer diretório configurado, além de dumps e backups.
- Chaves privadas, identidades de assinatura, cofres locais e arquivos de credenciais de serviços.
- Configurações locais de SSH, AWS/Azure/GCloud, npm e publicação Python.
- Sessões de navegador, cookies, estados de autenticação e gravações HAR/trace.
- Toda a pasta de verificação gerada, incluindo formatos além de PNG.
- Pacotes e ferramentas gerados continuam fora do repositório.

Os exemplos .env.example permanecem versionáveis. Módulos como auth.py, security.py e session.py contêm implementação, não credenciais fixas, e permanecem no Git.

## Arquivos já rastreados

A conferência do índice não encontrou arquivo privado que precisasse ser removido do rastreamento. A proteção também foi testada com git check-ignore --no-index para evitar que um arquivo já rastreado escondesse uma falha das regras.

## Pacote de entrega

O empacotador foi alinhado à proteção de chaves, credenciais e estados de navegador. Um teste usa arquivos fictícios sensíveis e confirma que eles não entram no ZIP. O pacote 0.3.0 e seu checksum foram regenerados.

A varredura de histórico não exigiu remoção de credenciais nem rotação de tokens nesta revisão.
