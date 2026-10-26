# Guia de contribuição

## Fluxo de trabalho

1. Crie uma branch para cada funcionalidade ou correção.
2. Mantenha as alterações pequenas e focadas.
3. Execute os testes antes de enviar alterações.
4. Atualize a documentação quando necessário.
5. Nunca inclua senhas, tokens ou credenciais reais.

## Backend

Na pasta `backend/`, execute:

```powershell
python -m pytest
python -m ruff check app tests
```

## Frontend

Na pasta `frontend/`, execute:

```powershell
npm run typecheck
npm run build
```

## Qualidade

- Não introduza regressões nos testes.
- Mantenha o código legível e tipado.
- Evite dependências desnecessárias.
- Documente alterações relevantes.
