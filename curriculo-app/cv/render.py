"""Gera o currículo em HTML (prévia), DOCX e PDF, no layout do "Modelo Ideal"."""

from __future__ import annotations

import html
import io
import random
import string

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from .modelos import Contato, CurriculoIA

AZUL_LINK = "#1155CC"


def _linkedin_url(link: str) -> str:
    link = link.strip()
    if link and not link.startswith("http"):
        link = "https://" + link
    return link


def _tracos(*partes: str, sep: str = " - ") -> str:
    return sep.join(p for p in partes if p and p.strip())


def _linha_item(nome: str, instituicao: str, ano: str) -> tuple[str, str]:
    """('Nome', ' – instituição - ano') no padrão do modelo."""
    resto = _tracos(instituicao, ano)
    return nome, (f" – {resto}" if resto else "")


# --------------------------------------------------------------------------- HTML


def _embaralhar(texto: str, rnd: random.Random) -> str:
    """Troca letras e números por aleatórios, mantendo o formato. O texto real não chega ao navegador."""
    out = []
    for ch in texto:
        if ch.isdigit():
            out.append(rnd.choice(string.digits))
        elif ch.isalpha():
            c = rnd.choice(string.ascii_lowercase)
            out.append(c.upper() if ch.isupper() else c)
        else:
            out.append(ch)
    return "".join(out)


def html_curriculo(contato: Contato, cv: CurriculoIA, bloquear: bool = False) -> str:
    rnd = random.Random(contato.nome)

    def t(texto: str, protegido: bool = True) -> str:
        if bloquear and protegido:
            texto = _embaralhar(texto, rnd)
        return html.escape(texto)

    css = """
    <style>
      .cv{font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111;background:#fff;
          padding:28px 32px;border:1px solid #ddd;border-radius:6px;line-height:1.35;position:relative;}
      .cv h1{font-size:16px;margin:0 0 2px 0}
      .cv .ct{margin:0}
      .cv hr{border:0;border-top:1px solid #999;margin:8px 0}
      .cv h2{font-size:15px;text-decoration:underline;margin:14px 0 4px 0}
      .cv p{margin:2px 0}
      .cv ul{margin:2px 0 6px 18px;padding:0}
      .cv .ind{margin-left:22px}
      .cv a{color:#1155CC}
      .cv .bl{filter:blur(4px);user-select:none;pointer-events:none}
      .cv .selo{position:absolute;top:40%;left:0;right:0;text-align:center;font-size:44px;font-weight:700;
          color:rgba(200,0,0,.18);transform:rotate(-18deg);pointer-events:none}
    </style>"""

    p: list[str] = [css, '<div class="cv">']
    li = _linkedin_url(contato.linkedin)
    p.append(f"<h1>{html.escape(contato.nome)}</h1>")
    p.append(f'<p class="ct">{html.escape(contato.cidade)}, {html.escape(contato.estado)}</p>')
    p.append(f'<p class="ct">{html.escape(contato.telefone)}</p>')
    p.append(f'<p class="ct"><b>{html.escape(contato.email)}</b></p>')
    if li:
        p.append(f'<p class="ct"><a href="{html.escape(li)}">{html.escape(li)}</a></p>')
    p.append("<hr>")
    p.append(f"<p><b>Objetivo:</b> {html.escape(cv.objetivo)}</p><hr>")

    p.append("<h2>Resumo</h2>")
    p.append(f"<p>{html.escape(cv.resumo_perfil)}</p>")
    p.append(f'<div class="{"bl" if bloquear else ""}">')
    p.append(f"<p>{t(cv.resumo_competencias)}</p>")

    if cv.formacao:
        p.append("<h2>Formação Acadêmica</h2>")
        for f in cv.formacao:
            n, r = _linha_item(f.curso, f.instituicao, f.ano)
            p.append(f"<p><b>{t(n)}</b>{t(r)}</p>")

    if cv.experiencias:
        p.append("<h2>Experiência Profissional</h2>")
        for e in cv.experiencias:
            p.append(f"<p><b>{t(_tracos(e.empresa, e.cidade_estado))}</b></p>")
            for c in e.cargos:
                p.append(f"<p>{t(c.cargo)} – {t(c.periodo)}</p><ul>")
                for rot, val in (("Responsabilidades", c.responsabilidades),
                                 ("Atividades Principais", c.atividades),
                                 ("Resultados", c.resultados)):
                    p.append(f"<li><b>{rot}:</b> {t(val)}</li>")
                p.append("</ul>")

    if cv.idiomas:
        p.append("<h2>Idiomas</h2>")
        for i in cv.idiomas:
            p.append(f'<p class="ind">{t(i.idioma)}: {t(i.nivel)}</p>')
    if cv.informatica:
        p.append("<h2>Informática</h2>")
        p.append(f'<p class="ind">{t(", ".join(cv.informatica))}</p>')
    if cv.outros_conhecimentos:
        p.append("<h2>Outros Conhecimentos</h2>")
        for o in cv.outros_conhecimentos:
            n, r = _linha_item(o.nome, o.instituicao, o.ano)
            p.append(f'<p class="ind">{t(n + r)}</p>')
    if cv.voluntario:
        p.append("<h2>Trabalho Voluntário</h2>")
        for v in cv.voluntario:
            n, r = _linha_item(v.nome, v.instituicao, v.ano)
            p.append(f'<p class="ind">{t(n + r)}</p>')
    p.append("</div>")
    if bloquear:
        p.append('<div class="selo">PRÉVIA</div>')
    p.append("</div>")
    return "\n".join(p)


# --------------------------------------------------------------------------- DOCX


def _borda_inferior(paragrafo) -> None:
    pPr = paragrafo._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "999999")):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    pPr.append(bdr)


def _hyperlink(paragrafo, url: str) -> None:
    rel = paragrafo.part.relate_to(
        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True
    )
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rel)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    cor = OxmlElement("w:color")
    cor.set(qn("w:val"), AZUL_LINK.lstrip("#"))
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(cor)
    rPr.append(u)
    r.append(rPr)
    tx = OxmlElement("w:t")
    tx.text = url
    r.append(tx)
    h.append(r)
    paragrafo._p.append(h)


def docx_curriculo(contato: Contato, cv: CurriculoIA) -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(1.5)
    sec.left_margin = sec.right_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.line_spacing = 1.1

    def par(texto: str = "", negrito: bool = False, recuo: bool = False, tamanho: float | None = None):
        p = doc.add_paragraph()
        if recuo:
            p.paragraph_format.left_indent = Cm(0.9)
        if texto:
            r = p.add_run(texto)
            r.bold = negrito
            if tamanho:
                r.font.size = Pt(tamanho)
        return p

    def titulo(texto: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(texto)
        r.bold = True
        r.underline = True
        r.font.size = Pt(11.5)

    par(contato.nome, negrito=True, tamanho=12)
    par(f"{contato.cidade}, {contato.estado}")
    par(contato.telefone)
    par(contato.email, negrito=True)
    li = _linkedin_url(contato.linkedin)
    p = par()
    if li:
        _hyperlink(p, li)
    _borda_inferior(p)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    r = p.add_run("Objetivo: ")
    r.bold = True
    r.font.size = Pt(11)
    r = p.add_run(cv.objetivo)
    r.font.size = Pt(11)
    _borda_inferior(p)

    titulo("Resumo")
    par(cv.resumo_perfil)
    par()
    par(cv.resumo_competencias)

    if cv.formacao:
        titulo("Formação Acadêmica")
        for f in cv.formacao:
            n, rst = _linha_item(f.curso, f.instituicao, f.ano)
            p = doc.add_paragraph()
            p.add_run(n).bold = True
            p.add_run(rst)

    if cv.experiencias:
        titulo("Experiência Profissional")
        for i, e in enumerate(cv.experiencias):
            if i:
                par()
            par(_tracos(e.empresa, e.cidade_estado), negrito=True)
            for j, c in enumerate(e.cargos):
                if j:
                    par()
                par(f"{c.cargo} – {c.periodo}")
                for rot, val in (("Responsabilidades", c.responsabilidades),
                                 ("Atividades Principais", c.atividades),
                                 ("Resultados", c.resultados)):
                    b = doc.add_paragraph(style="List Bullet")
                    b.paragraph_format.space_after = Pt(0)
                    b.add_run(f"{rot}: ").bold = True
                    b.add_run(val)

    if cv.idiomas:
        titulo("Idiomas")
        for idi in cv.idiomas:
            par(f"{idi.idioma}: {idi.nivel}", recuo=True)
    if cv.informatica:
        titulo("Informática")
        par(", ".join(cv.informatica), recuo=True)
    if cv.outros_conhecimentos:
        titulo("Outros Conhecimentos")
        for o in cv.outros_conhecimentos:
            n, rst = _linha_item(o.nome, o.instituicao, o.ano)
            par(n + rst, recuo=True)
    if cv.voluntario:
        titulo("Trabalho Voluntário")
        for v in cv.voluntario:
            n, rst = _linha_item(v.nome, v.instituicao, v.ano)
            par(n + rst, recuo=True)

    for p in doc.paragraphs:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------- PDF


def _esc(t: str) -> str:
    return html.escape(t, quote=False)


def _pdf_uma_vez(contato: Contato, cv: CurriculoIA, fs: float) -> tuple[bytes, int]:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Currículo - {contato.nome}", author=contato.nome,
    )
    lead = fs * 1.3
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=fs, leading=lead, alignment=TA_LEFT,
                          textColor=HexColor("#111111"))
    ind = ParagraphStyle("ind", parent=base, leftIndent=0.9 * cm)
    nome = ParagraphStyle("nome", parent=base, fontName="Helvetica-Bold", fontSize=fs + 2, leading=(fs + 2) * 1.3)
    obj = ParagraphStyle("obj", parent=base, fontSize=fs + 1, leading=(fs + 1) * 1.3)
    tit = ParagraphStyle("tit", parent=base, fontName="Helvetica-Bold", fontSize=fs + 1.5,
                         leading=(fs + 1.5) * 1.3, spaceBefore=fs * 0.9, spaceAfter=fs * 0.2)

    def T(texto: str) -> Paragraph:
        return Paragraph(f"<u>{_esc(texto)}</u>", tit)

    s: list = []
    s.append(Paragraph(_esc(contato.nome), nome))
    s.append(Paragraph(_esc(f"{contato.cidade}, {contato.estado}"), base))
    s.append(Paragraph(_esc(contato.telefone), base))
    s.append(Paragraph(f"<b>{_esc(contato.email)}</b>", base))
    li = _linkedin_url(contato.linkedin)
    if li:
        s.append(Paragraph(f'<a href="{_esc(li)}" color="{AZUL_LINK}"><u>{_esc(li)}</u></a>', base))
    s.append(HRFlowable(width="100%", thickness=0.6, color=HexColor("#999999"), spaceBefore=3, spaceAfter=3))
    s.append(Paragraph(f"<b>Objetivo:</b> {_esc(cv.objetivo)}", obj))
    s.append(HRFlowable(width="100%", thickness=0.6, color=HexColor("#999999"), spaceBefore=3, spaceAfter=0))

    s.append(T("Resumo"))
    s.append(Paragraph(_esc(cv.resumo_perfil), base))
    s.append(Spacer(1, fs * 0.6))
    s.append(Paragraph(_esc(cv.resumo_competencias), base))

    if cv.formacao:
        s.append(T("Formação Acadêmica"))
        for f in cv.formacao:
            n, r = _linha_item(f.curso, f.instituicao, f.ano)
            s.append(Paragraph(f"<b>{_esc(n)}</b>{_esc(r)}", base))

    if cv.experiencias:
        s.append(T("Experiência Profissional"))
        for i, e in enumerate(cv.experiencias):
            if i:
                s.append(Spacer(1, fs * 0.6))
            s.append(Paragraph(f"<b>{_esc(_tracos(e.empresa, e.cidade_estado))}</b>", base))
            for j, c in enumerate(e.cargos):
                if j:
                    s.append(Spacer(1, fs * 0.4))
                s.append(Paragraph(_esc(f"{c.cargo} – {c.periodo}"), base))
                itens = [
                    ListItem(Paragraph(f"<b>{rot}:</b> {_esc(val)}", base), leftIndent=0.6 * cm, value="•")
                    for rot, val in (("Responsabilidades", c.responsabilidades),
                                     ("Atividades Principais", c.atividades),
                                     ("Resultados", c.resultados))
                ]
                s.append(ListFlowable(itens, bulletType="bullet", start="•", leftIndent=0.6 * cm,
                                      bulletFontSize=fs))

    if cv.idiomas:
        s.append(T("Idiomas"))
        for idi in cv.idiomas:
            s.append(Paragraph(_esc(f"{idi.idioma}: {idi.nivel}"), ind))
    if cv.informatica:
        s.append(T("Informática"))
        s.append(Paragraph(_esc(", ".join(cv.informatica)), ind))
    if cv.outros_conhecimentos:
        s.append(T("Outros Conhecimentos"))
        for o in cv.outros_conhecimentos:
            n, r = _linha_item(o.nome, o.instituicao, o.ano)
            s.append(Paragraph(_esc(n + r), ind))
    if cv.voluntario:
        s.append(T("Trabalho Voluntário"))
        for v in cv.voluntario:
            n, r = _linha_item(v.nome, v.instituicao, v.ano)
            s.append(Paragraph(_esc(n + r), ind))

    doc.build(s)
    return buf.getvalue(), doc.page


def pdf_curriculo(contato: Contato, cv: CurriculoIA) -> tuple[bytes, int]:
    """Gera o PDF reduzindo a fonte, se preciso, para caber em 1 página. Devolve (pdf, nº de páginas)."""
    pdf, paginas = b"", 0
    for fs in (10.0, 9.5, 9.0, 8.5):
        pdf, paginas = _pdf_uma_vez(contato, cv, fs)
        if paginas == 1:
            break
    return pdf, paginas
