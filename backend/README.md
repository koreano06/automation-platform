# Backend

Python 3.13. Instale com python -m pip install -e ".[dev]" na pasta backend (use constraints em requirements.lock para reproduzir as versões verificadas).

Aplique migrações com python -m app.cli migrate. Crie o administrador com python -m app.cli create-admin. Inicie a API com python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 e o worker em outro processo com python -m app.worker.

A configuração vem de backend/.env ou do ambiente; consulte .env.example. A documentação interativa está em /docs. As operações exigem sessão e CSRF, exceto health, login e callback autenticado por assinatura.

Os extras runner e desktop acrescentam executores reais opcionais. O modo padrão é simulação. Consulte ../docs/OPERACAO.md, ../docs/PILOTO_E_CONTRATOS.md e ../docs/POWER_AUTOMATE.md.
