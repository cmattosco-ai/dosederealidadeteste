"""Pagamento com Mercado Pago (Checkout Pro: Pix, cartão e boleto).

O app nunca confia no que vem na URL de retorno: a confirmação é sempre
feita consultando a API do Mercado Pago pelo número do pedido.
"""

from __future__ import annotations

import mercadopago


class ErroPagamento(Exception):
    pass


class MercadoPago:
    def __init__(self, access_token: str):
        self.sdk = mercadopago.SDK(access_token)

    def criar_link(self, pedido_id: str, preco: float, app_url: str = "") -> str:
        """Cria a preferência de pagamento e devolve o link do checkout."""
        dados: dict = {
            "items": [
                {
                    "id": "curriculo",
                    "title": "Currículo profissional (PDF + Word)",
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": round(float(preco), 2),
                }
            ],
            "external_reference": pedido_id,
            "statement_descriptor": "CURRICULO",
        }
        if app_url.startswith("https://"):
            volta = f"{app_url.rstrip('/')}/?pedido={pedido_id}"
            dados["back_urls"] = {"success": volta, "pending": volta, "failure": volta}
            dados["auto_return"] = "approved"

        r = self.sdk.preference().create(dados)
        if r.get("status") not in (200, 201):
            raise ErroPagamento(f"Mercado Pago recusou a criação do pagamento ({r.get('status')}).")
        return r["response"]["init_point"]

    def pagamento_aprovado(self, pedido_id: str, preco: float) -> str | None:
        """Devolve o id do pagamento aprovado deste pedido, ou None."""
        r = self.sdk.payment().search(
            {"external_reference": pedido_id, "sort": "date_created", "criteria": "desc"}
        )
        if r.get("status") != 200:
            raise ErroPagamento(f"Não foi possível consultar o Mercado Pago ({r.get('status')}).")
        for p in r["response"].get("results", []):
            if (
                p.get("status") == "approved"
                and p.get("external_reference") == pedido_id
                and p.get("currency_id") == "BRL"
                and float(p.get("transaction_amount") or 0) + 0.001 >= float(preco)
            ):
                return str(p.get("id"))
        return None
