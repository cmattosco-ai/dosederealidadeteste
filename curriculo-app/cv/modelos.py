"""Estruturas de dados do currículo.

`Contato` vem direto do formulário (a IA nunca altera esses dados).
`CurriculoIA` é o que a IA devolve, já organizado na ordem do modelo.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Contato(BaseModel):
    nome: str
    cidade: str
    estado: str
    telefone: str
    email: str
    linkedin: str = ""


class Formacao(BaseModel):
    curso: str
    instituicao: str
    ano: str = Field(description="Ano de conclusão, ou 'em curso' / 'previsão AAAA'.")


class Cargo(BaseModel):
    cargo: str
    periodo: str = Field(description="'mm/aaaa - atual' ou 'mm/aaaa a mm/aaaa'.")
    responsabilidades: str
    atividades: str
    resultados: str


class Experiencia(BaseModel):
    empresa: str
    cidade_estado: str
    cargos: list[Cargo] = Field(description="Cargo mais recente primeiro.")


class Idioma(BaseModel):
    idioma: str
    nivel: str = Field(description="Ex.: 'Intermediário' ou 'Intermediário: em curso'.")


class Item(BaseModel):
    nome: str
    instituicao: str
    ano: str


class CurriculoIA(BaseModel):
    objetivo: str = Field(description="Nome exato da vaga pretendida.")
    resumo_perfil: str = Field(description="1º parágrafo do resumo: perfil, tempo de experiência, setores.")
    resumo_competencias: str = Field(description="2º parágrafo: 'Sólidos conhecimentos em ...' com palavras-chave.")
    formacao: list[Formacao] = Field(description="Mais recente primeiro.")
    experiencias: list[Experiencia] = Field(description="Empresa mais recente primeiro.")
    idiomas: list[Idioma]
    informatica: list[str]
    outros_conhecimentos: list[Item]
    voluntario: list[Item]
    sugestoes: list[str] = Field(
        description="Dicas curtas para a pessoa melhorar o currículo (ex.: dados que faltaram). Não vão no currículo."
    )
