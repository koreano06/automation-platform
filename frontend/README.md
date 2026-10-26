# Frontend — Automation Platform

Aplicação web desenvolvida com React, TypeScript e Vite.

## Requisitos

- Node.js
- npm

## Instalação

Execute a partir da raiz do projeto:

```powershell
Set-Location frontend
npm install
```

## Desenvolvimento

```powershell
npm run dev
```

O Vite disponibiliza a aplicação localmente em `http://127.0.0.1:5173/`.

## Verificações

```powershell
npm run typecheck
npm run build
```

O comando `build` verifica os projetos TypeScript e gera a versão de produção no diretório `dist/`.

## Configuração

O frontend ainda não depende de variáveis de ambiente próprias. Quando a integração com a API for configurada, a URL do backend será definida explicitamente por meio da configuração apropriada do Vite.

Não coloque segredos no código ou em variáveis `VITE_*`: essas variáveis podem ser incorporadas ao bundle entregue ao navegador.