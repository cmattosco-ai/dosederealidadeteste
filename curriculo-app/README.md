# Currículo Ideal

App em Streamlit que monta currículos automaticamente seguindo o "Template de Currículo – O Modelo Ideal".

**Fluxo:** a pessoa preenche o formulário → a IA (Claude) monta o currículo de 1 página → a pessoa vê uma
prévia com parte do texto embaralhado → paga pelo Mercado Pago (Pix ou cartão) → baixa PDF e Word.

## Estrutura

| Arquivo | O que faz |
|---|---|
| `app.py` | Telas: formulário, prévia, pagamento e download |
| `cv/ia.py` | Regras do modelo (`REGRAS`) e chamada à API do Claude |
| `cv/render.py` | Gera o currículo em PDF, Word e HTML (prévia) |
| `cv/pagamento.py` | Cria o link do Mercado Pago e confirma o pagamento pela API |
| `cv/pedidos.py` | Guarda pedidos (SQLite), apagados após 7 dias |

Para mudar as orientações de montagem, edite o texto `REGRAS` em `cv/ia.py`.

## Rodar no computador

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # preencha as chaves
streamlit run app.py
```

Sem chaves, rode com `MODO_TESTE = "true"`: o currículo é montado sem IA e aparece um botão de pagamento simulado.

Testes: `pip install pytest && python -m pytest -q`

## Publicar no Streamlit Community Cloud

1. Em share.streamlit.io, **Create app** → escolha este repositório, branch `main`, arquivo `app.py`.
2. Em **Advanced settings → Secrets**, cole o conteúdo de `secrets.toml.example` com os valores reais e
   `MODO_TESTE = "false"`.
3. Depois do primeiro deploy, copie o endereço do app para `APP_URL` nos secrets (é para onde o Mercado
   Pago devolve a pessoa depois de pagar).

## Como o pagamento é confirmado

Cada pedido tem um código (`external_reference`). O app consulta a API do Mercado Pago por esse código e só
libera o download se houver um pagamento **aprovado**, em BRL, de valor igual ou maior que `PRECO`.
O que vem na URL de retorno nunca é usado como prova de pagamento.

## Limitações conhecidas

- No Streamlit Community Cloud o disco é apagado quando o app reinicia. Um pedido pago pode se perder se o
  app reiniciar antes de a pessoa baixar o arquivo. Com volume de vendas, troque `cv/pedidos.py` por um
  banco externo (ex.: Supabase).
- O limite de prévias (`MAX_GERACOES`) é por sessão e por pedido; não impede alguém de abrir várias abas.
  Acompanhe o gasto no console da Anthropic e defina um limite mensal lá.
- Custo de IA: cerca de US$ 0,05 a 0,10 por prévia gerada com o modelo atual (`claude-opus-5-5`).
