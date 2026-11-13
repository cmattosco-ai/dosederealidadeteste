"""Guarda os pedidos em SQLite, para a pessoa voltar do Mercado Pago e encontrar o currículo.

Atenção: no Streamlit Community Cloud o disco é apagado quando o app reinicia.
Para produção com volume, troque por um banco externo (ex.: Supabase/Postgres).
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid

DIAS_RETENCAO = 7


class Pedidos:
    def __init__(self, caminho: str = "pedidos.db"):
        self.caminho = caminho
        with self._con() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS pedidos (
                    id TEXT PRIMARY KEY,
                    criado REAL NOT NULL,
                    entrada TEXT NOT NULL,
                    curriculo TEXT,
                    geracoes INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pendente',
                    pagamento_id TEXT,
                    link_pagamento TEXT
                )"""
            )

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def novo(self, entrada: dict) -> str:
        pid = uuid.uuid4().hex
        with self._con() as c:
            c.execute("INSERT INTO pedidos (id, criado, entrada) VALUES (?, ?, ?)",
                      (pid, time.time(), json.dumps(entrada, ensure_ascii=False)))
        return pid

    def obter(self, pid: str) -> dict | None:
        with self._con() as c:
            row = c.execute("SELECT * FROM pedidos WHERE id = ?", (pid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["entrada"] = json.loads(d["entrada"])
        d["curriculo"] = json.loads(d["curriculo"]) if d["curriculo"] else None
        return d

    def salvar_curriculo(self, pid: str, entrada: dict, curriculo: dict) -> None:
        with self._con() as c:
            c.execute(
                "UPDATE pedidos SET entrada = ?, curriculo = ?, geracoes = geracoes + 1, link_pagamento = NULL "
                "WHERE id = ? AND status = 'pendente'",
                (json.dumps(entrada, ensure_ascii=False), json.dumps(curriculo, ensure_ascii=False), pid),
            )

    def salvar_link(self, pid: str, link: str) -> None:
        with self._con() as c:
            c.execute("UPDATE pedidos SET link_pagamento = ? WHERE id = ?", (link, pid))

    def marcar_pago(self, pid: str, pagamento_id: str) -> None:
        with self._con() as c:
            c.execute("UPDATE pedidos SET status = 'pago', pagamento_id = ? WHERE id = ?", (pagamento_id, pid))

    def limpar_antigos(self, dias: int = DIAS_RETENCAO) -> None:
        with self._con() as c:
            c.execute("DELETE FROM pedidos WHERE criado < ?", (time.time() - dias * 86400,))
