# Backend — Automation Platform

API da Automation Platform, desenvolvida com Python, FastAPI e Pydantic Settings.

## Requisitos

- Python 3.13
- Ambiente virtual Python

## Configuração local

Execute a partir da raiz do projeto:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Se o ambiente virtual já estiver criado, basta ativá-lo e instalar as dependências quando necessário.

## Executar a API

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Endpoints iniciais

- `GET /health`: verifica se a API está respondendo.
- `/docs`: documentação interativa.
- `/openapi.json`: esquema OpenAPI.

## Testes e qualidade

```powershell
python -m pytest
python -m ruff check app tests
python -m pip check
```

## Configuração

Consulte `pyproject.toml` para as dependências e `../.env.example` para as configurações iniciais do projeto.

Não armazene credenciais reais no repositório. Funcionalidades como autenticação, persistência em banco de dados e integração com o Power Automate ainda serão implementadas em etapas posteriores.