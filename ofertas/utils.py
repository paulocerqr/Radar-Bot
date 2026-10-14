import os
import re

import requests

from .config import DATA_DIR

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)


def ambiente_navegador() -> dict | None:
    """Ambiente do Chromium do projeto: bibliotecas do Ubuntu extraídas em data/, sem instalação como root."""
    libs = DATA_DIR / "browser-libs/usr/lib/x86_64-linux-gnu"
    if not libs.is_dir():
        return None
    return {**os.environ, "LD_LIBRARY_PATH": str(libs) + ":" + os.getenv("LD_LIBRARY_PATH", "")}


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
    return s


def parse_preco_br(texto: str | None) -> float | None:
    """Converte "R$ 1.234,56" / "1.234" / "56,43" em float."""
    t = re.sub(r"[^\d,.]", "", texto or "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or (t.count(".") == 1 and len(t.rsplit(".", 1)[1]) == 3):
        t = t.replace(".", "")  # ponto de milhar, sem centavos
    try:
        return float(t)
    except ValueError:
        return None


def extrair_urls(texto: str | None) -> list[str]:
    return re.findall(r"https?://\S+", texto or "")
