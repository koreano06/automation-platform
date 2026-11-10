# Piloto e contratos — 08/11/2026

O produto foi direcionado pelo usuário para um construtor de automações reutilizável por plataforma. Cadastro de colaboradores é um fluxo disponível; também é possível executar um fluxo genérico sem dados de colaborador pelo Construtor visual.

## Piloto controlado

O seed cria Portal de Treinamento e Diretório de Teste, ambos fictícios. O primeiro conclui; o segundo falha na primeira tentativa e aceita repetição segura. Nenhuma conta externa é criada nesse modo.

Campos comuns do cadastro: nome, e-mail, departamento e matrícula. Campo específico do piloto: perfil (Colaborador ou Gestor). Cada plataforma define seus próprios campos de texto, e-mail, número inteiro e seleção. Campos de senha/token são proibidos; credenciais são referências resolvidas no ambiente do executor.

Fluxo demonstrativo: abrir página → preencher nome/e-mail/perfil → clicar → confirmar resultado. O domínio `pilot.invalid` é um identificador fictício, não um sistema real.

## Métodos do construtor

- Seletor: localizar, preencher, clicar e confirmar texto no navegador.
- Nome acessível: localizar exatamente um botão pelo nome usando o navegador.
- Imagem: guardar um recorte PNG e procurar correspondência única na tela. Se não houver correspondência, aguardar até o timeout. Se houver alvos diferentes com correspondência suficiente, falhar por ambiguidade.
- Click point: coordenadas X/Y e contexto (resolução/janela).
- Confirmação por imagem: reconhecer a imagem sem clicar, inclusive como última etapa do fluxo.

A captura completa fica no navegador; apenas o recorte selecionado é enviado. A tela pode ser carregada por arquivo ou capturada com compartilhamento autorizado no próprio navegador. Referências são imutáveis. No navegador, pontos usam coordenadas da área da página, sem barras do navegador. No desktop, usam a tela primária completa. A execução desktop exige a janela esperada em foco e resolução compatível em todas as etapas.

Um reconhecimento visual não compreende semanticamente qualquer botão. Aparência, escala, tema e idioma podem exigir novas referências. CAPTCHA, MFA, login federado, iframes especiais e aplicativos com controles protegidos precisam de configuração e validação específicas.

## Perfis

Administrador: plataformas, campos, versões, validação, execução manual, referências visuais, usuários e auditoria. Operador: consulta de plataformas, solicitação de cadastros e acompanhamento/cancelamento/repetição permitida dos próprios pedidos. A API aplica os mesmos limites; ocultar botões não é a proteção.

## Estados

Execução: queued → dispatching → running → succeeded | failed.
queued também permite cancelled. failed pode voltar a queued apenas quando a repetição é segura e o limite de tentativas não foi atingido.

Solicitação: queued → running → succeeded | partially_succeeded | failed.
Se todos os destinos forem cancelados, a solicitação fica failed e cada execução mantém cancelled.

Versão: draft → validated. Validar outra versão arquiva a anteriormente validada. Alterar a plataforma exige revalidação. Solicitações existentes preservam o snapshot das etapas/entradas/mode/versão anteriores.

## Entrada de exemplo

```json
{
  "employee": {
    "name": "Pessoa de Teste",
    "email": "pessoa@example.invalid",
    "department": "Qualidade",
    "employee_id": "T-001"
  },
  "targets": [
    { "platform_id": "<id-do-portal>", "fields": { "profile": "Colaborador" } },
    { "platform_id": "<id-do-diretorio>", "fields": { "profile": "Gestor" } }
  ]
}
```

Envio: POST /provisioning-requests, com cookie autenticado, X-CSRF-Token e Idempotency-Key. A resposta 202 contém id da solicitação e uma execução queued por destino. Reenvio da mesma entrada/chave retorna o pedido anterior (200); mesma chave com dados diferentes retorna 409. Uma trava única impede dois trabalhos pendentes para o mesmo e-mail/destino.

Fluxo genérico: POST /automations/{id}/runs com fields e employee opcional, quando nenhuma etapa usa employee.*. O Construtor visual fornece esse formulário.

## Critérios de aceite e evidência

1. Administrador configura destino, campos e versão ordenada, depois valida.
2. Operador não consegue alterar configuração nem ler pedidos de outra pessoa.
3. Pedido com dois destinos gera duas execuções e falha parcial observável.
4. Repetição da falha simulada conclui sem duplicar o cadastro fictício.
5. Eventos têm sequência e horários; erros não exibem valores de entrada/credenciais.
6. Fila permanece no banco após recriação de sessão/processo; timeout recupera simulações e marca resultados reais como incertos.
7. Navegador real reconhece botão por nome e por imagem em uma página de teste controlada.
8. Interface completa percorre login, captura/recorte, nova versão/validação, pedido, falha parcial, repetição e layout móvel.

Os testes automatizados e scripts/browser_smoke.py cobrem esses critérios. O piloto em uma plataforma de uso real requer escolher o destino, identificar suas telas/ações permitidas e validar efeitos reais antes de ampliar o uso.
