# Automation Platform

Plataforma para gerenciamento, execução e monitoramento de automações, com integração planejada ao Microsoft Power Automate.

## Tecnologias

- **Frontend:** React, TypeScript e Vite
- **Backend:** Python 3.13, FastAPI e Pydantic Settings
- **Testes:** Pytest e HTTPX
- **Qualidade de código:** Ruff
- **Controle de versão:** Git

## Estrutura do projeto

- `frontend/`: aplicação web
- `backend/`: API e regras de negócio
- `power-automate/`: espaço destinado à integração com o Microsoft Power Automate
- `tests/`: testes complementares do projeto
- `docs/`: documentação técnica
- `scripts/`: scripts auxiliares
- `infrastructure/`: configurações de infraestrutura

Alguns diretórios estão reservados para funcionalidades futuras e ainda não estão implementados.

## Pré-requisitos

- Git
- Node.js e npm
- Python 3.13

## Executar o frontend

No PowerShell, a partir da raiz do projeto:

```powershell
Set-Location frontend
npm install
npm run dev
```

Acesse `http://127.0.0.1:5173/`.

## Executar o backend

Em outro terminal, a partir da raiz do projeto:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints disponíveis nesta versão inicial:

- Health check: `http://127.0.0.1:8000/health`
- Documentação interativa: `http://127.0.0.1:8000/docs`
- Esquema OpenAPI: `http://127.0.0.1:8000/openapi.json`

Se o ambiente virtual ainda não existir, consulte a configuração de dependências em `backend/pyproject.toml` e crie-o antes de ativá-lo.

## Testes e verificações

No diretório `backend/`, com o ambiente virtual ativado:

```powershell
python -m pytest
python -m ruff check app tests
python -m pip check
```

No diretório `frontend/`:

```powershell
npm run typecheck
npm run build
```

## Configuração e segurança

- Use `.env.example` como referência para as variáveis de ambiente.
- Mantenha os arquivos `.env` locais fora do controle de versão.
- Nunca inclua senhas, tokens ou credenciais reais no repositório.
- Não considere a integração com o Power Automate ou outros módulos futuros como implementados até que tenham código e testes correspondentes.

## Estado atual

A versão inicial contém uma aplicação React funcional, uma API FastAPI com endpoint de saúde e testes básicos. Autenticação, gerenciamento de automações, banco de dados e integração com o Power Automate ainda precisam ser implementados.