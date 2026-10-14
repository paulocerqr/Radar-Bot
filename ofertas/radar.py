"""Envia cada oferta publicada ao Radar (POST /radar/ingest), que escolhe as de
informática para o perfil de vídeos ofertas-tech. Falhas aqui nunca impedem a
postagem: o canal continua funcionando com o Radar fora do ar.
"""
import datetime as dt
import logging

from telegram import Message

from .config import config
from .formatter import preco_br
from .models import Oferta
from .utils import sessao

log = logging.getLogger("ofertas.radar")


def ativo() -> bool:
    return bool(config.radar_api_url and config.radar_token and config.radar_source_id)


def _link_mensagem(mensagem: Message | None) -> str | None:
    """Canal privado (-100...) -> https://t.me/c/<id>/<mensagem>; canal público -> t.me/<nome>/<mensagem>."""
    if not mensagem:
        return None
    if mensagem.chat.username:
        return f"https://t.me/{mensagem.chat.username}/{mensagem.message_id}"
    chat = str(mensagem.chat.id)
    return f"https://t.me/c/{chat.removeprefix('-100')}/{mensagem.message_id}" if chat.startswith("-100") else None


def _descricao(o: Oferta) -> str:
    """Texto que a triagem lê: produto, loja e preço."""
    partes = [f"Oferta publicada no canal Radar de Ofertas ({o.plataforma})."]
    if o.categoria:
        partes.append(f"Categoria na loja: {o.categoria}.")
    if o.preco:
        partes.append(f"Preço: {preco_br(o.preco)}" + (f" (era {preco_br(o.preco_original)})" if o.preco_original else "")
                      + (f", {o.desconto}% de desconto." if o.desconto else "."))
    if o.extra:
        partes.append(o.extra)
    return " ".join(partes)


def payload(o: Oferta, mensagem: Message | None) -> dict:
    agora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return {
        "platform": o.plataforma,
        "external_id": o.id_produto,
        "source_id": config.radar_source_id,
        "canonical_url": o.url_produto or o.url_afiliado,
        "thumbnail_url": o.imagem,
        "title": o.titulo[:300],
        "description": _descricao(o),
        "creator_name": "Radar de Ofertas",
        "community": "Radar de Ofertas",
        "published_at": agora,
        "is_video": False,
        "views": 0,
        # the analysis queue orders each profile by source rank; a published offer was already chosen
        "source_rank": 1,
        "offer": {
            "plataforma": o.plataforma,
            "id_produto": o.id_produto,
            "titulo": o.titulo,
            "preco": o.preco,
            "preco_original": o.preco_original,
            "desconto": o.desconto,
            "url_produto": o.url_produto,
            "url_afiliado": o.url_afiliado,
            "imagem": o.imagem,
            "extra": o.extra,
            "categoria": o.categoria,
            "mensagem_id": mensagem.message_id if mensagem else None,
            "mensagem_url": _link_mensagem(mensagem),
            "publicada_em": agora,
        },
    }


def enviar_oferta(o: Oferta, mensagem: Message | None) -> None:
    if not ativo():
        return
    try:
        r = sessao().post(f"{config.radar_api_url.rstrip('/')}/ingest",
                          json={"items": [payload(o, mensagem)]},
                          headers={"X-Radar-Token": config.radar_token}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log.warning("Radar não recebeu a oferta '%s': %s", o.titulo[:60], e)
