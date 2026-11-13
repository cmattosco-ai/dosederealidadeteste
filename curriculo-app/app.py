"""Currículo Ideal: formulário → IA monta o currículo → prévia → pagamento → download."""

from __future__ import annotations

import os
import re

import streamlit as st

from cv import ia
from cv.modelos import Contato, CurriculoIA
from cv.pagamento import ErroPagamento, MercadoPago
from cv.pedidos import DIAS_RETENCAO, Pedidos
from cv.render import docx_curriculo, html_curriculo, pdf_curriculo

st.set_page_config(page_title="Currículo Ideal", page_icon="📄", layout="centered")


# --------------------------------------------------------------------------- configuração


def cfg(chave: str, padrao: str = "") -> str:
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:  # sem secrets.toml
        pass
    return os.environ.get(chave, padrao)


ANTHROPIC_KEY = cfg("ANTHROPIC_API_KEY")
MP_TOKEN = cfg("MP_ACCESS_TOKEN")
PRECO = float(cfg("PRECO", "19.90").replace(",", "."))
APP_URL = cfg("APP_URL")
MODO_TESTE = cfg("MODO_TESTE", "false").lower() in ("1", "true", "sim", "yes")
MAX_GERACOES = int(cfg("MAX_GERACOES", "3"))
SUPORTE = cfg("CONTATO_SUPORTE")


def reais(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_resource
def banco() -> Pedidos:
    p = Pedidos(cfg("DB_PATH", "pedidos.db"))
    p.limpar_antigos()
    return p


def mercado_pago() -> MercadoPago | None:
    return MercadoPago(MP_TOKEN) if MP_TOKEN else None


# --------------------------------------------------------------------------- formulário

# (campo, rótulo, tipo, opções)
LISTAS: dict[str, dict] = {
    "exp": {
        "titulo": "Experiência profissional",
        "ajuda": "Uma entrada por cargo. Se teve mais de um cargo na mesma empresa, repita o nome da empresa.",
        "add": "+ Adicionar experiência",
        "max": 8,
        "inicial": 1,
        "campos": [
            ("empresa", "Empresa", "text", None),
            ("cidade_estado", "Cidade/Estado", "text", None),
            ("cargo", "Cargo", "text", None),
            ("inicio", "Início (mm/aaaa)", "text", None),
            ("fim", "Fim (mm/aaaa)", "text", None),
            ("atual", "Trabalho aqui atualmente", "check", None),
            ("descricao", "O que você fazia, pelo que respondia e que resultados alcançou", "area", None),
        ],
    },
    "form": {
        "titulo": "Formação acadêmica",
        "add": "+ Adicionar formação",
        "max": 5,
        "inicial": 1,
        "campos": [
            ("curso", "Curso", "text", None),
            ("instituicao", "Instituição", "text", None),
            ("ano", "Ano de conclusão (ou previsão)", "text", None),
            ("situacao", "Situação", "select", ["Concluído", "Em curso", "Trancado"]),
        ],
    },
    "idi": {
        "titulo": "Idiomas",
        "add": "+ Adicionar idioma",
        "max": 5,
        "inicial": 0,
        "campos": [
            ("idioma", "Idioma", "text", None),
            ("nivel", "Nível", "select", ["Básico", "Intermediário", "Avançado", "Fluente", "Nativo"]),
            ("em_curso", "Estou cursando", "check", None),
        ],
    },
    "cur": {
        "titulo": "Cursos e certificações",
        "ajuda": "A IA mantém só os que têm relação com a vaga.",
        "add": "+ Adicionar curso",
        "max": 10,
        "inicial": 0,
        "campos": [
            ("nome", "Curso ou certificação", "text", None),
            ("instituicao", "Instituição", "text", None),
            ("ano", "Ano", "text", None),
        ],
    },
    "vol": {
        "titulo": "Trabalho voluntário (opcional)",
        "add": "+ Adicionar trabalho voluntário",
        "max": 3,
        "inicial": 0,
        "campos": [
            ("nome", "Função ou projeto", "text", None),
            ("instituicao", "Instituição", "text", None),
            ("ano", "Ano", "text", None),
        ],
    },
}


def _k(lista: str, i: int, campo: str) -> str:
    return f"f_{lista}_{i}_{campo}"


def _vazio(tipo: str, opcoes):
    return False if tipo == "check" else (opcoes[0] if tipo == "select" else "")


def preservar_formulario() -> None:
    """O Streamlit apaga o valor de campos que deixam de aparecer na tela; isto os mantém."""
    for k in list(st.session_state.keys()):
        if k.startswith(("f_", "n_")):
            st.session_state[k] = st.session_state[k]


def _adicionar(lista: str) -> None:
    st.session_state[f"n_{lista}"] = st.session_state.get(f"n_{lista}", LISTAS[lista]["inicial"]) + 1


def _remover(lista: str, i: int) -> None:
    n = st.session_state.get(f"n_{lista}", LISTAS[lista]["inicial"])
    campos = LISTAS[lista]["campos"]
    for j in range(i, n - 1):
        for campo, _, tipo, op in campos:
            st.session_state[_k(lista, j, campo)] = st.session_state.get(_k(lista, j + 1, campo), _vazio(tipo, op))
    for campo, *_ in campos:
        st.session_state.pop(_k(lista, n - 1, campo), None)
    st.session_state[f"n_{lista}"] = n - 1


def bloco_lista(lista: str) -> None:
    spec = LISTAS[lista]
    st.subheader(spec["titulo"])
    if spec.get("ajuda"):
        st.caption(spec["ajuda"])
    n = st.session_state.setdefault(f"n_{lista}", spec["inicial"])
    for i in range(n):
        with st.container(border=True):
            curtos = [c for c in spec["campos"] if c[2] != "area"]
            for linha in range(0, len(curtos), 3):
                cols = st.columns(3)
                for col, (campo, rotulo, tipo, op) in zip(cols, curtos[linha:linha + 3]):
                    key = _k(lista, i, campo)
                    with col:
                        if tipo == "check":
                            st.checkbox(rotulo, key=key)
                        elif tipo == "select":
                            st.selectbox(rotulo, op, key=key)
                        else:
                            st.text_input(rotulo, key=key)
            for campo, rotulo, tipo, _ in spec["campos"]:
                if tipo == "area":
                    st.text_area(
                        rotulo, key=_k(lista, i, campo), height=130,
                        placeholder="Ex.: Responsável pelo contas a pagar de 3 filiais. Lançava notas no ERP, "
                                    "conciliava extratos e fazia relatórios mensais. Reduzi atrasos de pagamento "
                                    "de 15 para 2 por mês.",
                    )
            st.button("Remover", key=f"b_rm_{lista}_{i}", on_click=_remover, args=(lista, i))
    if n < spec["max"]:
        st.button(spec["add"], key=f"b_add_{lista}", on_click=_adicionar, args=(lista,))


def coletar(lista: str) -> list[dict]:
    spec = LISTAS[lista]
    itens = []
    for i in range(st.session_state.get(f"n_{lista}", spec["inicial"])):
        item = {}
        for campo, _, tipo, op in spec["campos"]:
            v = st.session_state.get(_k(lista, i, campo), _vazio(tipo, op))
            item[campo] = v.strip() if isinstance(v, str) else v
        if item[spec["campos"][0][0]]:  # ignora linhas sem o 1º campo
            itens.append(item)
    return itens


def montar_entrada() -> tuple[dict, list[str]]:
    s = st.session_state
    g = lambda k: (s.get(k) or "").strip()  # noqa: E731
    contato = {
        "nome": g("f_nome"), "cidade": g("f_cidade"), "estado": g("f_estado"),
        "telefone": g("f_telefone"), "email": g("f_email"), "linkedin": g("f_linkedin"),
    }
    entrada = {
        "contato": contato,
        "vaga": {"cargo": g("f_vaga"), "anuncio": g("f_anuncio")},
        "experiencias": coletar("exp"),
        "formacao": coletar("form"),
        "idiomas": coletar("idi"),
        "informatica": g("f_informatica"),
        "cursos": coletar("cur"),
        "voluntario": coletar("vol"),
    }
    erros = []
    for campo, rotulo in (("nome", "Nome completo"), ("cidade", "Cidade"), ("estado", "Estado"),
                          ("telefone", "Telefone"), ("email", "E-mail")):
        if not contato[campo]:
            erros.append(f"Preencha: {rotulo}.")
    if contato["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contato["email"]):
        erros.append("E-mail inválido.")
    if not entrada["vaga"]["cargo"]:
        erros.append("Preencha a vaga pretendida.")
    if not entrada["experiencias"] and not entrada["formacao"]:
        erros.append("Inclua pelo menos uma experiência ou uma formação.")
    for e in entrada["experiencias"]:
        if not e["cargo"] or not e["inicio"]:
            erros.append(f"Experiência em {e['empresa']}: preencha cargo e início.")
        if not e["atual"] and not e["fim"]:
            erros.append(f"Experiência em {e['empresa']}: preencha o fim ou marque 'Trabalho aqui atualmente'.")
    if not s.get("f_lgpd"):
        erros.append("Marque a autorização de uso dos dados.")
    return entrada, erros


def tela_formulario() -> None:
    st.title("📄 Currículo Ideal")
    st.write(
        "Preencha seus dados e a IA monta um currículo de **1 página**, objetivo e orientado a resultados, "
        f"no formato que recrutadores procuram. Você vê uma prévia antes de pagar **{reais(PRECO)}**."
    )

    st.subheader("Seus dados")
    st.text_input("Nome completo", key="f_nome")
    c1, c2 = st.columns([3, 1])
    c1.text_input("Cidade", key="f_cidade", help="Nunca coloque o endereço completo.")
    c2.text_input("Estado (UF)", key="f_estado", max_chars=2)
    c1, c2 = st.columns(2)
    c1.text_input("Telefone", key="f_telefone", placeholder="21 99999-9999")
    c2.text_input("E-mail", key="f_email")
    st.text_input("LinkedIn (opcional)", key="f_linkedin", placeholder="linkedin.com/in/seu-usuario")
    st.caption("Não pedimos foto, idade, estado civil, RG ou CPF: eles não devem ir no currículo.")

    st.subheader("Vaga pretendida")
    st.text_input("Cargo", key="f_vaga", placeholder="Ex.: Assistente Administrativo")
    st.text_area(
        "Anúncio da vaga (opcional, recomendado)", key="f_anuncio", height=120,
        help="Cole o texto de uma ou mais vagas que você está buscando. A IA espelha as palavras-chave.",
    )

    bloco_lista("exp")
    bloco_lista("form")
    bloco_lista("idi")
    st.subheader("Informática")
    st.text_input("Programas e ferramentas que você domina", key="f_informatica",
                  placeholder="Excel, Word, PowerPoint, SAP...")
    bloco_lista("cur")
    bloco_lista("vol")

    st.divider()
    st.checkbox(
        f"Autorizo o uso destes dados apenas para montar meu currículo. Eles são apagados em {DIAS_RETENCAO} dias.",
        key="f_lgpd",
    )
    usadas = st.session_state.get("geracoes", 0)
    if usadas >= MAX_GERACOES:
        st.warning("Você atingiu o limite de prévias desta sessão.")
        return
    if st.button("Gerar prévia do currículo", type="primary", use_container_width=True):
        entrada, erros = montar_entrada()
        if erros:
            for e in erros:
                st.error(e)
            return
        gerar_curriculo(entrada)


def gerar_curriculo(entrada: dict) -> None:
    pedidos = banco()
    pid = st.session_state.get("pedido_id")
    ped = pedidos.obter(pid) if pid else None
    if ped and (ped["status"] != "pendente" or ped["geracoes"] >= MAX_GERACOES):
        ped, pid = None, None

    if ANTHROPIC_KEY:
        try:
            with st.spinner("Montando seu currículo... isso leva cerca de 1 minuto."):
                cv = ia.gerar(entrada, ANTHROPIC_KEY)
        except ia.ErroIA as e:
            st.error(str(e))
            return
    elif MODO_TESTE:
        cv = ia.sem_ia(entrada)
    else:
        st.error("O app ainda não está configurado (falta ANTHROPIC_API_KEY).")
        return

    if not pid:
        pid = pedidos.novo(entrada)
    pedidos.salvar_curriculo(pid, entrada, cv.model_dump())
    st.session_state.geracoes = st.session_state.get("geracoes", 0) + 1
    carregar_pedido(pid)
    st.query_params["pedido"] = pid
    st.rerun()


# --------------------------------------------------------------------------- prévia, pagamento, download


def carregar_pedido(pid: str) -> bool:
    ped = banco().obter(pid)
    if not ped or not ped["curriculo"]:
        return False
    st.session_state.pedido_id = pid
    st.session_state.entrada = ped["entrada"]
    st.session_state.curriculo = ped["curriculo"]
    st.session_state.link_pagamento = ped["link_pagamento"]
    st.session_state.etapa = "pago" if ped["status"] == "pago" else "previa"
    st.session_state.pop("arquivos", None)
    if "f_nome" not in st.session_state:
        preencher_formulario(ped["entrada"])
    return True


def preencher_formulario(entrada: dict) -> None:
    """Repõe os campos do formulário a partir de um pedido salvo (ex.: ao voltar do Mercado Pago)."""
    s = st.session_state
    for campo, valor in entrada["contato"].items():
        s[f"f_{campo}"] = valor
    s["f_vaga"] = entrada["vaga"]["cargo"]
    s["f_anuncio"] = entrada["vaga"].get("anuncio", "")
    s["f_informatica"] = entrada.get("informatica", "")
    s["f_lgpd"] = True
    for lista, chave in (("exp", "experiencias"), ("form", "formacao"), ("idi", "idiomas"),
                         ("cur", "cursos"), ("vol", "voluntario")):
        itens = entrada.get(chave, [])
        s[f"n_{lista}"] = len(itens)
        for i, item in enumerate(itens):
            for campo, *_ in LISTAS[lista]["campos"]:
                if campo in item:
                    s[_k(lista, i, campo)] = item[campo]


def verificar_pagamento(silencioso: bool = False) -> bool:
    pid = st.session_state.pedido_id
    mp = mercado_pago()
    if not mp:
        return False
    try:
        pagamento_id = mp.pagamento_aprovado(pid, PRECO)
    except ErroPagamento as e:
        if not silencioso:
            st.error(str(e))
        return False
    if pagamento_id:
        banco().marcar_pago(pid, pagamento_id)
        st.session_state.etapa = "pago"
        return True
    return False


def dados_atuais() -> tuple[Contato, CurriculoIA]:
    return (Contato(**st.session_state.entrada["contato"]),
            CurriculoIA.model_validate(st.session_state.curriculo))


def tela_previa() -> None:
    contato, cv = dados_atuais()
    st.title("Prévia do seu currículo")
    st.caption("Parte do texto aparece embaralhada até o pagamento. Depois dele você baixa o PDF e o Word completos.")
    st.html(html_curriculo(contato, cv, bloquear=True))
    if cv.sugestoes:
        st.info(f"A versão final vem com {len(cv.sugestoes)} dica(s) para deixar o currículo ainda mais forte.")

    if st.button("✏️ Editar meus dados"):
        st.session_state.etapa = "form"
        st.rerun()

    st.subheader(f"Liberar currículo completo: {reais(PRECO)}")
    mp = mercado_pago()
    if mp:
        link = st.session_state.get("link_pagamento")
        if not link:
            try:
                link = mp.criar_link(st.session_state.pedido_id, PRECO, APP_URL)
                banco().salvar_link(st.session_state.pedido_id, link)
                st.session_state.link_pagamento = link
            except ErroPagamento as e:
                st.error(str(e))
        if link:
            st.link_button(f"Pagar {reais(PRECO)} com Pix ou cartão", link, type="primary",
                           use_container_width=True)
            st.caption("O pagamento abre no Mercado Pago. Ao concluir, volte aqui.")
            if st.button("Já paguei: liberar meu currículo", use_container_width=True):
                with st.spinner("Consultando o Mercado Pago..."):
                    ok = verificar_pagamento()
                if ok:
                    st.rerun()
                st.warning("Ainda não encontramos o pagamento. Pix costuma cair em segundos; "
                           "cartão pode levar alguns minutos. Tente de novo em instantes.")
    if MODO_TESTE:
        if st.button("Simular pagamento aprovado (modo teste)"):
            banco().marcar_pago(st.session_state.pedido_id, "teste")
            st.session_state.etapa = "pago"
            st.rerun()
    if not mp and not MODO_TESTE:
        st.error("Pagamento ainda não configurado (falta MP_ACCESS_TOKEN).")

    if APP_URL:
        st.caption(f"Guarde este link para voltar ao seu pedido: {APP_URL.rstrip('/')}/?pedido={st.session_state.pedido_id}")


def tela_pago() -> None:
    contato, cv = dados_atuais()
    st.title("✅ Seu currículo está pronto")
    if "arquivos" not in st.session_state:
        pdf, paginas = pdf_curriculo(contato, cv)
        st.session_state.arquivos = {"pdf": pdf, "paginas": paginas, "docx": docx_curriculo(contato, cv)}
    arq = st.session_state.arquivos
    nome = re.sub(r"[^\w\- ]", "", contato.nome).strip() or "curriculo"

    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Baixar PDF", arq["pdf"], f"Curriculo - {nome}.pdf", "application/pdf",
                       type="primary", use_container_width=True)
    c2.download_button("⬇️ Baixar Word (editável)", arq["docx"], f"Curriculo - {nome}.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       use_container_width=True)
    if arq["paginas"] > 1:
        st.warning("O currículo passou de 1 página. Use o arquivo Word para remover os itens menos "
                   "relevantes para a vaga.")
    st.caption("Precisa ajustar algum detalhe? O arquivo Word é editável.")

    if cv.sugestoes:
        with st.expander("💡 Dicas para melhorar ainda mais", expanded=True):
            for s in cv.sugestoes:
                st.markdown(f"- {s}")

    st.html(html_curriculo(contato, cv))

    if st.button("Montar outro currículo"):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()


# --------------------------------------------------------------------------- roteamento


def tratar_retorno() -> None:
    """Quando a pessoa volta do Mercado Pago (ou recarrega a página) com ?pedido=..."""
    pid = st.query_params.get("pedido")
    if not pid or st.session_state.get("pedido_id") == pid:
        return
    if not carregar_pedido(pid):
        msg = "Não encontramos este pedido (os pedidos são apagados após alguns dias)."
        if SUPORTE:
            msg += f" Se você já pagou, fale com {SUPORTE} informando o código {pid}."
        st.warning(msg)
        st.query_params.clear()
        return
    if st.session_state.etapa == "previa":
        verificar_pagamento(silencioso=True)


def main() -> None:
    preservar_formulario()
    tratar_retorno()
    etapa = st.session_state.get("etapa", "form")
    if etapa == "previa":
        tela_previa()
    elif etapa == "pago":
        tela_pago()
    else:
        tela_formulario()
    st.divider()
    rodape = f"Seus dados são usados só para montar o currículo e apagados em {DIAS_RETENCAO} dias."
    if SUPORTE:
        rodape += f" Dúvidas: {SUPORTE}"
    st.caption(rodape)


main()
