from html import escape

from .models import Oferta


def preco_br(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def preco_post(valor: float) -> str:
    """Sem centavos quando o valor é inteiro: "R$ 1.419"; com centavos: "R$ 1.419,90"."""
    texto = preco_br(valor)
    return texto.removesuffix(",00")


def montar_caption(o: Oferta) -> str:
    """Título, preço e o link no corpo da mensagem (o post no canal não tem botão)."""
    linhas = [f"🔥 {escape(o.titulo[:180])}"]
    if o.preco:
        linhas += ["", f"💵 {preco_post(o.preco)}"]
    if o.url_afiliado:
        linhas += ["", f"🔗 LINK: {escape(o.url_afiliado)}"]
    return "\n".join(linhas)
