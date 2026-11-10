# Contrato do adaptador Power Automate

O adaptador implementa um protocolo HTTP do projeto. Um fluxo do Power Automate precisa ser criado/configurado para obedecer a esse contrato. Não há fluxo Microsoft exportado ou credenciais reais incluídos.

Configure no backend/.env, fora do Git:

- POWER_AUTOMATE_URL: URL HTTPS de disparo do fluxo.
- POWER_AUTOMATE_TOKEN: bearer token, quando o mecanismo de entrada exigir.
- POWER_AUTOMATE_CALLBACK_SECRET: segredo compartilhado de pelo menos 32 caracteres aleatórios.
- PUBLIC_API_BASE_URL: URL HTTPS da API acessível pelo fluxo.
- POWER_AUTOMATE_IDEMPOTENT: habilitar apenas quando o destino garantir uma única operação por execution_id, inclusive após timeout.

Segredos não são devolvidos pela API nem registrados nos eventos. Uma URL de disparo que já contém credencial deve ser tratada como segredo.

## Envio e confirmação

O worker envia POST com Idempotency-Key igual ao execution_id. O JSON contém execution_id, correlation_id, idempotency_key, callback_url, platform_id, automation_id, version, employee, fields e steps. Quando há referências visuais, reference_images contém id e png_base64 de cada recorte (até 2 MB somados).

O destino deve devolver HTTP 200 ou 202 com:

```json
{ "external_id": "id-da-execucao-no-fluxo" }
```

O envio usa timeout de 10 segundos, não segue redirecionamentos e nunca registra o conteúdo de erro do destino. Se o resultado do envio for desconhecido, a execução falha com orientação de conferir o destino antes de repetir.

Ações com credential.NOME são referências. O fluxo remoto deve resolver suas próprias conexões/credenciais seguras; os segredos locais do worker não são enviados no envelope.

## Callback

POST /integrations/power-automate/callbacks

```json
{
  "execution_id": "<id-da-execucao>",
  "event_id": "evento-unico-001",
  "external_id": "id-da-execucao-no-fluxo",
  "status": "running",
  "step": 2
}
```

status: running, succeeded ou failed. result_code opcional: account_created, already_exists, destination_rejected ou execution_error. Não há campo de mensagem livre, para evitar vazar dados do destino.

Headers obrigatórios:

- X-Callback-Timestamp: Unix timestamp em segundos.
- X-Callback-Signature: HMAC SHA-256 hexadecimal de timestamp + "." + bytes EXATOS do corpo, usando o segredo compartilhado.

O desvio de relógio máximo é de cinco minutos. O event_id é único por execução; callbacks repetidos não aplicam a mesma alteração duas vezes. Eventos novos após estado terminal são recusados. Atualizações concorrentes usam versão otimista e podem retornar 409; o remetente deve consultar o estado/repetir de forma idempotente.

## O que o fluxo real precisa fazer

Validar entrada, deduplicar execution_id de forma durável, responder rapidamente com external_id, executar as ações no destino e enviar callbacks assinados. Reconhecer conta já existente como resultado idempotente. O fluxo pode usar credenciais/conexões próprias; não deve devolvê-las em resultados.

A criação do fluxo, licenciamento, conexão a máquina/desktop e endpoint público da API dependem do ambiente escolhido. Até essa configuração, use simulação ou o executor local. Os testes de integração verificam envio, correlação, progresso, sucesso, falha, autenticação e repetição do contrato com um destino simulado.
