"""Testes que rodam sem chave de API e sem Mercado Pago real: `python -m pytest -q`."""

from __future__ import annotations

import io
import json

import httpx2 as httpx
import pytest
from docx import Document

from cv import ia
from cv.modelos import Contato, CurriculoIA
from cv.pagamento import MercadoPago
from cv.pedidos import Pedidos
from cv.render import docx_curriculo, html_curriculo, pdf_curriculo

CONTATO = Contato(nome="Ana Souza", cidade="Niterói", estado="RJ", telefone="21 99999-9999",
                  email="ana@example.com", linkedin="linkedin.com/in/ana")

CV = CurriculoIA.model_validate({
    "objetivo": "Assistente Administrativo",
    "resumo_perfil": "Profissional da área administrativa com mais de 7 anos de experiência.",
    "resumo_competencias": "Sólidos conhecimentos em rotinas administrativas, fluxo de caixa e Excel.",
    "formacao": [{"curso": "Administração", "instituicao": "UFF", "ano": "2019"}],
    "experiencias": [{
        "empresa": "Empresa Alfa", "cidade_estado": "Niterói/RJ",
        "cargos": [{"cargo": "Assistente Administrativo", "periodo": "03/2021 - atual",
                    "responsabilidades": "Contas a pagar de 3 filiais.",
                    "atividades": "Lançamento de notas, conciliação bancária e relatórios mensais.",
                    "resultados": "Redução de atrasos de pagamento de 15 para 2 por mês."}],
    }],
    "idiomas": [{"idioma": "Inglês", "nivel": "Intermediário: em curso"}],
    "informatica": ["Excel", "Word", "SAP"],
    "outros_conhecimentos": [{"nome": "Excel Avançado", "instituicao": "SENAC", "ano": "2022"}],
    "voluntario": [],
    "sugestoes": ["Inclua um número no resultado."],
})

ENTRADA = {
    "contato": CONTATO.model_dump(),
    "vaga": {"cargo": "Assistente Administrativo", "anuncio": ""},
    "experiencias": [{"empresa": "Empresa Alfa", "cidade_estado": "Niterói/RJ", "cargo": "Assistente",
                      "inicio": "03/2021", "fim": "", "atual": True, "descricao": "Contas a pagar."}],
    "formacao": [{"curso": "Administração", "instituicao": "UFF", "ano": "2019", "situacao": "Concluído"}],
    "idiomas": [{"idioma": "Inglês", "nivel": "Intermediário", "em_curso": True}],
    "informatica": "Excel, Word",
    "cursos": [],
    "voluntario": [],
}


def test_pdf_cabe_em_uma_pagina():
    pdf, paginas = pdf_curriculo(CONTATO, CV)
    assert pdf.startswith(b"%PDF") and paginas == 1


def test_docx_segue_ordem_do_modelo():
    doc = Document(io.BytesIO(docx_curriculo(CONTATO, CV)))
    texto = "\n".join(p.text for p in doc.paragraphs)
    ordem = ["Ana Souza", "Objetivo:", "Resumo", "Formação Acadêmica", "Experiência Profissional",
             "Idiomas", "Informática", "Outros Conhecimentos"]
    posicoes = [texto.index(t) for t in ordem]
    assert posicoes == sorted(posicoes)
    assert "Trabalho Voluntário" not in texto  # seção vazia não aparece
    assert "Resultados: Redução de atrasos" in texto


def test_previa_nao_vaza_texto_bloqueado():
    h = html_curriculo(CONTATO, CV, bloquear=True)
    assert "Ana Souza" in h and CV.resumo_perfil in h  # parte aberta
    assert "Redução de atrasos" not in h and "Empresa Alfa" not in h  # parte paga
    assert "Empresa Alfa" in html_curriculo(CONTATO, CV)


def test_sem_ia_monta_curriculo_valido():
    cv = ia.sem_ia(ENTRADA)
    assert cv.experiencias[0].cargos[0].periodo == "03/2021 - atual"
    assert cv.idiomas[0].nivel == "Intermediário: em curso"
    pdf_curriculo(CONTATO, cv)


def test_requisicao_para_claude(monkeypatch):
    capturado = {}

    def responder(req: httpx.Request) -> httpx.Response:
        capturado["corpo"] = json.loads(req.content)
        capturado["beta"] = req.headers.get("anthropic-beta")
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": ia.MODELO,
            "content": [{"type": "text", "text": CV.model_dump_json()}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    original = ia.anthropic.Anthropic

    def cliente_falso(**kw):
        return original(**kw, http_client=httpx.Client(transport=httpx.MockTransport(responder)))

    monkeypatch.setattr(ia.anthropic, "Anthropic", cliente_falso)
    cv = ia.gerar(ENTRADA, "sk-teste")
    corpo = capturado["corpo"]
    assert cv.objetivo == "Assistente Administrativo"
    assert corpo["model"] == "claude-opus-5-5"
    assert corpo["fallbacks"] == "default"
    assert corpo["output_config"]["effort"] == "medium"
    assert corpo["output_config"]["format"]["type"] == "json_schema"
    assert "server-side-fallback-2026-07-01" in capturado["beta"]
    assert "<dados>" in corpo["messages"][0]["content"]


def test_recusa_vira_erro_amigavel(monkeypatch):
    def responder(req):
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": ia.MODELO,
            "content": [], "stop_reason": "refusal", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 0},
        })
    original = ia.anthropic.Anthropic
    monkeypatch.setattr(ia.anthropic, "Anthropic", lambda **kw: original(
        **kw, http_client=httpx.Client(transport=httpx.MockTransport(responder))))
    with pytest.raises(ia.ErroIA):
        ia.gerar(ENTRADA, "sk-teste")


def test_pedidos(tmp_path):
    p = Pedidos(str(tmp_path / "t.db"))
    pid = p.novo(ENTRADA)
    p.salvar_curriculo(pid, ENTRADA, CV.model_dump())
    assert p.obter(pid)["geracoes"] == 1
    p.marcar_pago(pid, "123")
    p.salvar_curriculo(pid, ENTRADA, CV.model_dump())  # pedido pago não é regravado
    ped = p.obter(pid)
    assert ped["status"] == "pago" and ped["geracoes"] == 1
    p.limpar_antigos(dias=-1)
    assert p.obter(pid) is None


class _Busca:
    def __init__(self, resultados):
        self.resultados = resultados

    def search(self, filtros):
        self.filtros = filtros
        return {"status": 200, "response": {"results": self.resultados}}


@pytest.mark.parametrize("pagamento,esperado", [
    ({"id": 9, "status": "approved", "external_reference": "abc", "currency_id": "BRL",
      "transaction_amount": 19.9}, "9"),
    ({"id": 9, "status": "pending", "external_reference": "abc", "currency_id": "BRL",
      "transaction_amount": 19.9}, None),
    ({"id": 9, "status": "approved", "external_reference": "abc", "currency_id": "BRL",
      "transaction_amount": 1.0}, None),
    ({"id": 9, "status": "approved", "external_reference": "outro", "currency_id": "BRL",
      "transaction_amount": 19.9}, None),
])
def test_confirmacao_de_pagamento(pagamento, esperado):
    mp = MercadoPago("TEST-x")
    busca = _Busca([pagamento])
    mp.sdk.payment = lambda: busca
    assert mp.pagamento_aprovado("abc", 19.90) == esperado
    assert busca.filtros["external_reference"] == "abc"
