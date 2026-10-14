import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from ofertas.formatter import montar_caption
from ofertas.models import Oferta
from ofertas.sources import amazon
from ofertas.sources import mercadolivre as ml


def _oferta(**extra):
    return Oferta('mercadolivre', 'MLB1', 'SSD M.2 2280 2TB Sandisk Plus NVMe 3200MB/s', 'https://meli.la/2HrKWfZ',
                  url_produto='https://www.mercadolivre.com.br/p/MLB1', preco=1419.0, preco_original=1899.0,
                  extra='🚚 Frete grátis', **extra)


class PostTest(unittest.TestCase):
    def test_post_has_the_link_in_the_text_and_no_category(self):
        caption = montar_caption(_oferta(categoria='Informática > Armazenamento'))
        self.assertEqual(caption, '🔥 SSD M.2 2280 2TB Sandisk Plus NVMe 3200MB/s\n\n💵 R$ 1.419\n\n'
                                  '🔗 LINK: https://meli.la/2HrKWfZ')

    def test_cents_are_kept_when_the_price_has_them(self):
        o = _oferta()
        o.preco = 99.9
        self.assertIn('💵 R$ 99,90', montar_caption(o))


class CategoryTest(unittest.TestCase):
    def test_amazon_reads_the_breadcrumb(self):
        html = ('<div id="wayfinding-breadcrumbs_feature_div"><a>Computadores e Informática</a> › '
                '<a>Notebooks</a></div>')
        self.assertEqual(amazon._categoria(BeautifulSoup(html, 'lxml')), 'Computadores e Informática > Notebooks')
        self.assertIsNone(amazon._categoria(BeautifulSoup('<html></html>', 'lxml')))

    def test_amazon_stops_at_the_first_block(self):
        client = MagicMock()
        client.get.return_value.status_code = 503
        offers = [Oferta('amazon', 'B1', 'A', ''), Oferta('amazon', 'B2', 'B', '')]
        with patch.object(amazon, '_sessao', return_value=client), patch.object(amazon.time, 'sleep'):
            amazon.preencher_categorias(offers)
        self.assertEqual(client.get.call_count, 1)
        self.assertIsNone(offers[0].categoria)

    def test_mercadolivre_reads_the_breadcrumb_inside_the_logged_page(self):
        page = MagicMock()
        page.evaluate.return_value = [{'categoria': 'Informática > Impressão > Impressoras', 'titulo': 'Outro'}, {}]
        offers = [_oferta(), _oferta()]
        ml._preencher_da_pagina(page, offers)
        self.assertEqual(page.evaluate.call_args.args[1], [o.url_produto for o in offers])
        self.assertEqual([o.categoria for o in offers], ['Informática > Impressão > Impressoras', None])
        self.assertEqual(offers[0].titulo, 'SSD M.2 2280 2TB Sandisk Plus NVMe 3200MB/s')  # collected data is kept

    def test_pasted_link_gets_title_price_and_photo_from_the_logged_page(self):
        page = MagicMock()
        page.evaluate.return_value = [{'categoria': 'Informática > Monitores', 'titulo': 'Monitor Gamer LG UltraGear 24',
                                       'imagem': 'https://http2.mlstatic.com/x-O.webp', 'preco': '699', 'original': '1.099'}]
        offer = Oferta('mercadolivre', 'MLB38947984', '', '', url_produto='https://www.mercadolivre.com.br/p/MLB38947984')
        ml._preencher_da_pagina(page, [offer])
        self.assertEqual((offer.titulo, offer.preco, offer.preco_original, offer.imagem),
                         ('Monitor Gamer LG UltraGear 24', 699.0, 1099.0, 'https://http2.mlstatic.com/x-O.jpg'))


if __name__ == '__main__':
    unittest.main()
