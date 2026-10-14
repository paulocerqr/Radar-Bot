"""Mercado Livre: scraping da página de ofertas + link de afiliado via Linkbuilder.

O ML não tem API pública para afiliados, mas o Linkbuilder do painel usa uma API
interna simples (createLink), autenticada só pelos cookies da sessão. O bot chama
essa API de dentro de uma página logada (perfil persistente do Chrome em
data/ml_profile). Faça login uma única vez com:

    uv run python -m ofertas ml-login
"""
import logging
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import USER_AGENT, ambiente_navegador, parse_preco_br, sessao

log = logging.getLogger("ofertas.ml")

URL_OFERTAS = "https://www.mercadolivre.com.br/ofertas"
URL_LINKBUILDER = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
API_CREATELINK = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"
PERFIL_DIR = DATA_DIR / "ml_profile"

_RE_ID = re.compile(r"(MLB-?\d{6,})")


def e_link(url: str) -> bool:
    return any(d in url for d in ("mercadolivre.com", "mercadolibre.com", "meli.la/"))


def tem_sessao() -> bool:
    return PERFIL_DIR.exists() and any(PERFIL_DIR.iterdir())


def normalizar_cookies(dados: list) -> list[dict]:
    if not isinstance(dados, list) or not 1 <= len(dados) <= 500:
        raise ValueError("O arquivo precisa conter uma lista de cookies.")
    cookies = []
    sites = {"no_restriction": "None", "unspecified": "Lax", "strict": "Strict", "lax": "Lax"}
    for item in dados:
        domain = item.get("domain", "") if isinstance(item, dict) else ""
        host = domain.lstrip(".").lower()
        if host != "mercadolivre.com.br" and not host.endswith(".mercadolivre.com.br"):
            raise ValueError("O arquivo contém cookies de outro domínio.")
        if not isinstance(item.get("name"), str) or not item["name"] or not isinstance(item.get("value"), str):
            raise ValueError("Cookie com nome ou valor inválido.")
        cookie = {key: item[key] for key in ("name", "value", "domain")}
        cookie.update(path=item.get("path", "/"), secure=item.get("secure", False),
                      httpOnly=item.get("httpOnly", False), sameSite=sites.get(item.get("sameSite"), item.get("sameSite") or "Lax"))
        if cookie["sameSite"] not in {"Lax", "Strict", "None"} or not isinstance(cookie["path"], str) or not cookie["path"].startswith("/"):
            raise ValueError("Cookie com atributos inválidos.")
        if type(cookie["secure"]) is not bool or type(cookie["httpOnly"]) is not bool:
            raise ValueError("Cookie com atributos booleanos inválidos.")
        expires = item.get("expirationDate", item.get("expires", -1))
        if not item.get("session") and expires != -1:
            if type(expires) not in (int, float) or not math.isfinite(expires):
                raise ValueError("Cookie com validade inválida.")
            if expires <= time.time():
                continue
            cookie["expires"] = expires
        partition = item.get("partitionKey")
        if isinstance(partition, dict):
            partition = partition.get("topLevelSite")
        if partition:
            if not isinstance(partition, str) or not partition.startswith("https://"):
                raise ValueError("Cookie particionado inválido.")
            cookie["partitionKey"] = partition
        cookies.append(cookie)
    if not cookies:
        raise ValueError("Não há cookies válidos; exporte uma sessão atualizada.")
    return cookies


def importar_cookies(arquivo: str) -> int:
    from playwright.sync_api import sync_playwright
    path = Path(arquivo)
    path.chmod(0o600)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Arquivo de cookies grande demais.")
    dados = json.loads(path.read_text(encoding="utf-8-sig"))
    cookies = normalizar_cookies(dados.get("cookies") if isinstance(dados, dict) else dados)
    PERFIL_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    PERFIL_DIR.chmod(0o700)
    with sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=True)
        try:
            ctx.add_cookies(cookies)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            response = page.goto(URL_LINKBUILDER, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            if not response or response.status != 200 or "/afiliados/linkbuilder" not in page.url:
                raise RuntimeError("A sessão não abriu o Linkbuilder autenticado. Login ou verificação adicional pode ser necessário.")
        finally:
            ctx.close()
    return len(cookies)


# ── Busca de ofertas (scraping, sem login) ───────────────────────────

def _categorias() -> dict[str, str]:
    """{id: nome} das categorias do config (aceita dict ou lista de ids); vazio = todas."""
    cats = config.fonte_ml.get("categorias") or {}
    return dict(cats) if isinstance(cats, dict) else {str(c): str(c) for c in cats}


def buscar_ofertas() -> list[Oferta]:
    """Página de ofertas do ML, filtrada pelas categorias do config (ofertas?category=MLB...)."""
    paginas = max(1, int(config.fonte_ml.get("paginas", 1)))
    categorias = _categorias() or {"": "todas"}
    s = sessao()
    ofertas: dict[str, Oferta] = {}
    for cat_id, nome in categorias.items():
        for pagina in range(1, paginas + 1):
            params = {}
            if cat_id:
                params["category"] = cat_id
            if pagina > 1:
                params["page"] = pagina
            try:
                r = s.get(URL_OFERTAS, params=params or None, timeout=30)
                r.raise_for_status()
                achadas = _parse_pagina(r.text)
                if not achadas and tem_sessao():
                    achadas = _buscar_pagina_autenticada(params)
            except Exception as e:  # uma página com erro (ou sem mais ofertas) encerra só esta categoria
                log.warning("Mercado Livre %s, página %d: %s", nome, pagina, str(e).splitlines()[0][:120])
                break
            for o in achadas:
                ofertas.setdefault(o.id_produto, o)
            log.info("Mercado Livre %s: %d ofertas", nome, len(achadas))
            time.sleep(1)
    log.info("Mercado Livre: %d ofertas coletadas", len(ofertas))
    return list(ofertas.values())


def _preco_de(card, seletor_base: str) -> float | None:
    fracao = card.select_one(f"{seletor_base} .andes-money-amount__fraction")
    if not fracao:
        return None
    centavos = card.select_one(f"{seletor_base} .andes-money-amount__cents")
    texto = fracao.get_text(strip=True) + ("," + centavos.get_text(strip=True) if centavos else "")
    return parse_preco_br(texto)


def _parse_card(card) -> Oferta | None:
    a = card.select_one("a.poly-component__title")
    if not (a and a.get("href")):
        return None
    titulo = a.get_text(strip=True)
    url = a["href"].split("#")[0].split("?")[0]

    m = _RE_ID.search(a["href"])
    id_produto = m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40]

    preco = _preco_de(card, ".poly-price__current")
    preco_original = _preco_de(card, "s.andes-money-amount--previous")

    desconto = None
    selo = card.select_one(".poly-price__discount-polylabel, .andes-money-amount__discount")
    if selo:
        m = re.search(r"(\d+)\s*%", selo.get_text())
        desconto = int(m.group(1)) if m else None

    img = card.select_one("img.poly-component__picture")
    imagem = (img.get("data-src") or img.get("src")) if img else None
    if imagem and imagem.startswith("data:"):
        imagem = None  # placeholder de lazy-load

    partes = []
    review = card.select_one(".poly-component__review-compacted")
    if review:
        partes.append("⭐ " + re.sub(r"\s*\|\s*", " · ", review.get_text(" ", strip=True)))
    if "Frete grátis" in card.get_text():
        partes.append("🚚 Frete grátis")
    pix = card.select_one(".poly-price__unit-description")
    if pix and "pix" in pix.get_text().lower():
        partes.append("💠 preço no Pix")

    return Oferta(
        plataforma="mercadolivre",
        id_produto=id_produto,
        titulo=titulo,
        url_afiliado="",  # preenchido depois pelo Linkbuilder
        url_produto=url,
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto,
        imagem=imagem,
        extra=" · ".join(partes) or None,
    )


def _parse_pagina(html: str) -> list[Oferta]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.poly-card")
    ofertas = [o for o in (_parse_card(c) for c in cards) if o]
    if cards and not ofertas:
        log.warning("Página de ofertas do ML mudou de layout? %d cards, 0 parseados", len(cards))
    return ofertas


def _buscar_pagina_autenticada(params: dict) -> list[Oferta]:
    from playwright.sync_api import sync_playwright
    # ponytail: um navegador por página; compartilhar o contexto se muitas categorias tornarem o ciclo lento.
    with sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            response = page.goto(URL_OFERTAS + ("?" + urlencode(params) if params else ""),
                                 wait_until="domcontentloaded", timeout=45000)
            if not response or response.status != 200:
                raise RuntimeError("A página de ofertas não respondeu corretamente.")
            page.wait_for_selector("div.poly-card", timeout=15000)
            return _parse_pagina(page.content())
        finally:
            ctx.close()


# ── Link de afiliado via Linkbuilder (Playwright + sessão logada) ────

def _abrir_contexto(pw, headless: bool):
    """Google Chrome instalado (build de produção) + perfil persistente do projeto.

    O ML recusa login no "Chrome for Testing" do Playwright, então usamos o
    Chrome real via channel="chrome" e removemos as marcas de automação.
    """
    kwargs = dict(
        channel="chrome",
        headless=headless,
        locale="pt-BR",
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    if headless:
        kwargs["user_agent"] = USER_AGENT  # o headless real se anuncia como HeadlessChrome
    else:
        kwargs["no_viewport"] = True
    if ambiente_navegador():
        kwargs["env"] = ambiente_navegador()
    try:
        return pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)
    except Exception as e:
        if "chrome" not in str(e).lower():
            raise
        log.warning("Google Chrome não encontrado (%s); usando Chromium do projeto — "
                    "o login no ML pode ser recusado", type(e).__name__)
        kwargs.pop("channel")
        return pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)


def _achar_chrome() -> str:
    """Caminho do Google Chrome instalado (Windows, macOS ou Linux)."""
    import shutil
    candidatos: list[str] = []

    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    chave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                    with winreg.OpenKey(hive, chave) as k:
                        candidatos.append(winreg.QueryValueEx(k, None)[0])
                except OSError:
                    continue
        except ImportError:
            pass
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidatos.append(str(Path(base) / "Google/Chrome/Application/chrome.exe"))
    elif sys.platform == "darwin":
        candidatos += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux e afins
        for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                     "brave-browser", "microsoft-edge"):
            achado = shutil.which(nome)
            if achado:
                candidatos.append(achado)
        candidatos += ["/usr/bin/google-chrome", "/usr/bin/chromium",
                       "/snap/bin/chromium", "/usr/bin/chromium-browser"]

    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise RuntimeError("Google Chrome não encontrado — instale o Google Chrome e tente de novo.")


def ml_login() -> None:
    """Abre um Chrome comum (SEM automação — indetectável porque não há o que
    detectar) no perfil do bot, para você logar no ML uma única vez."""
    chrome = _achar_chrome()
    PERFIL_DIR.mkdir(parents=True, exist_ok=True)
    print("\n➡️  Vai abrir um Chrome normal com o perfil do bot (separado do seu).")
    print("    1. Faça login no Mercado Livre (senha, 2FA etc.)")
    print("    2. Confira que o Linkbuilder carrega logado")
    print("    3. FECHE o navegador para terminar\n")
    proc = subprocess.Popen([chrome, f"--user-data-dir={PERFIL_DIR}", "--no-first-run",
                             "--no-default-browser-check", URL_LINKBUILDER])
    proc.wait()
    print(f"✅ Perfil salvo em {PERFIL_DIR} — o bot usa essa sessão sozinho daqui pra frente.")
    print('   Teste com: uv run python -m ofertas converter "<link de produto do ML>"')


def _criar_links_api(page, urls: list[str], etiqueta: str) -> list[str]:
    """Chama a API interna do Linkbuilder de dentro da página logada; retorna os short links.

    Payload/resposta observados em 2026-08-21:
    POST createLink {"urls": [...], "tag": "<etiqueta>"} ->
    {"status": 200, "urls": [{"id", "created", "short_url": "https://meli.la/...", ...}]}
    """
    r = page.evaluate(
        """async ({api, urls, tag}) => {
            const resp = await fetch(api, {
                method: 'POST',
                headers: {'content-type': 'application/json'},
                body: JSON.stringify({urls, tag}),
            });
            const corpo = await resp.text();
            try { return {http: resp.status, dados: JSON.parse(corpo)}; }
            catch (e) { return {http: resp.status, texto: corpo.slice(0, 300)}; }
        }""",
        {"api": API_CREATELINK, "urls": urls, "tag": etiqueta},
    )
    if r.get("http") != 200 or not r.get("dados"):
        raise RuntimeError(f"createLink respondeu HTTP {r.get('http')}: {r.get('texto', '')}")
    itens = (r["dados"].get("urls")) or []
    links = [i.get("short_url") or "" for i in itens]
    if len(links) != len(urls) or not all(links):
        raise RuntimeError(f"createLink devolveu {sum(1 for l in links if l)} links "
                           f"para {len(urls)} URLs: {r['dados']}")
    return links


def _preencher_da_pagina(page, ofertas: list[Oferta]) -> None:
    """Lê a página de cada produto na mesma página logada (fora dela o ML pede verificação de conta): a trilha
    de categorias, que vai só para o Radar, e título, preço e foto quando a oferta ainda não os tem (links
    colados no privado). Uma página que falhar fica sem esses dados."""
    paginas = page.evaluate(
        """async (urls) => Promise.all(urls.map(async (u) => {
            try {
                const d = new DOMParser().parseFromString(await (await fetch(u)).text(), 'text/html');
                const q = (s) => d.querySelector(s);
                return {
                    categoria: [...d.querySelectorAll('.andes-breadcrumb__link')].map(a => a.textContent.trim()).join(' > '),
                    titulo: q('h1.ui-pdp-title')?.textContent.trim() || '',
                    imagem: q('meta[property="og:image"]')?.content || '',
                    preco: q('meta[itemprop="price"]')?.content
                        || q('.ui-pdp-price__second-line .andes-money-amount__fraction')?.textContent || '',
                    original: q('s.andes-money-amount--previous .andes-money-amount__fraction')?.textContent || '',
                };
            } catch (e) { return {}; }
        }))""",
        [o.url_produto for o in ofertas],
    )
    for o, dados in zip(ofertas, paginas):
        o.categoria = dados.get("categoria") or None
        o.titulo = o.titulo or dados.get("titulo") or ""
        # o Telegram publica foto em JPEG/PNG; o servidor de imagens do ML entrega a mesma foto em .jpg
        o.imagem = o.imagem or re.sub(r"\.webp$", ".jpg", dados.get("imagem") or "") or None
        if o.preco is None and dados.get("preco"):
            o.preco = parse_preco_br(dados["preco"])
        if o.preco_original is None and dados.get("original"):
            o.preco_original = parse_preco_br(dados["original"])


def _links_do_lote(page, lote: list[Oferta], erros: list[str]) -> list[Oferta]:
    """Gera os links de um lote; se o createLink falhar, tenta de novo e depois URL por URL,
    para uma falha (HTTP 500, URL recusada) não deixar o lote inteiro sem link."""
    for tentativa in range(2):
        try:
            links = _criar_links_api(page, [o.url_produto for o in lote], config.ml_etiqueta)
        except Exception as e:
            log.warning("Mercado Livre: createLink falhou para %d URLs (tentativa %d): %s",
                        len(lote), tentativa + 1, e)
            erros.append(str(e))
            page.wait_for_timeout(3000)
            continue
        for o, link in zip(lote, links):
            o.url_afiliado = link
        return lote
    if len(lote) == 1:
        return []
    gerados = []
    for o in lote:
        try:
            o.url_afiliado = _criar_links_api(page, [o.url_produto], config.ml_etiqueta)[0]
            gerados.append(o)
        except Exception as e:
            log.warning("Mercado Livre: sem link para '%s': %s", o.titulo[:60], e)
            erros.append(str(e))
    return gerados


def gerar_links_afiliado(ofertas: list[Oferta]) -> None:
    """Preenche oferta.url_afiliado via API do Linkbuilder (lotes de 10 URLs)."""
    from playwright.sync_api import sync_playwright

    if not tem_sessao():
        raise RuntimeError("Sessão do ML não encontrada — rode: uv run python -m ofertas ml-login")
    if not config.ml_etiqueta:
        raise RuntimeError("ML_ETIQUETA não configurada no .env "
                           "(é a 'Etiqueta em uso' do Linkbuilder no painel de afiliados)")
    pendentes = [o for o in ofertas if not o.url_afiliado and o.url_produto]
    if not pendentes:
        return

    with sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL_LINKBUILDER, wait_until="domcontentloaded")
            if "login" in page.url or "registration" in page.url:
                raise RuntimeError("Sessão do ML expirou — rode de novo: "
                                   "uv run python -m ofertas ml-login")
            page.wait_for_timeout(1500)  # deixa os scripts de sessão da página rodarem
            erros = []
            for i in range(0, len(pendentes), 10):
                lote = pendentes[i:i + 10]
                gerados = _links_do_lote(page, lote, erros)
                if not gerados:
                    continue
                try:
                    _preencher_da_pagina(page, gerados)
                except Exception as e:  # os dados da página são opcionais: o link já foi gerado
                    log.warning("Mercado Livre: páginas dos produtos indisponíveis: %s", e)
            gerados = sum(1 for o in pendentes if o.url_afiliado)
            log.info("Mercado Livre: %d de %d links de afiliado gerados", gerados, len(pendentes))
            if erros and not gerados:
                raise RuntimeError(f"nenhum link gerado ({erros[-1]})")
        finally:
            ctx.close()


def converter(url: str) -> Oferta:
    """Link de produto -> Oferta com dados da página + link de afiliado."""
    url = url.split("#")[0]
    if "meli.la/" in url:  # link de afiliado encurtado: expande até o produto
        try:
            url = sessao().get(url, allow_redirects=True, timeout=20).url.split("#")[0]
        except Exception as e:
            log.warning("Não consegui expandir o link meli.la: %s", e)
    m = _RE_ID.search(url)
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto=m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40],
        titulo="",
        url_afiliado="",
        url_produto=url.split("?")[0],
    )
    # o link de afiliado e os dados da página (título, preço, foto) saem da mesma sessão logada
    gerar_links_afiliado([oferta])
    if not oferta.url_afiliado:
        raise RuntimeError("Linkbuilder não devolveu o link de afiliado")
    oferta.titulo = oferta.titulo or "Oferta Mercado Livre"
    return oferta
