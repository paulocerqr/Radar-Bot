import time
import unittest
from unittest.mock import MagicMock, patch

from ofertas.sources.mercadolivre import normalizar_cookies
from ofertas.sources import mercadolivre as ml
from ofertas.models import Oferta


class CollectionMLTest(unittest.TestCase):
    def test_a_failing_page_ends_only_its_category(self):
        client = MagicMock()
        client.get.return_value.text = '<html></html>'
        offer = Oferta('mercadolivre', 'MLB1', 'Mouse', '', url_produto='https://www.mercadolivre.com.br/p/MLB1')
        def page(params):
            if params.get('category') == 'MLB1144':
                raise TimeoutError('Page.wait_for_selector: Timeout 15000ms exceeded.')
            return [offer]
        with patch.object(ml, 'sessao', return_value=client), \
             patch.object(ml, '_categorias', return_value={'MLB1144': 'Games', 'MLB1648': 'Informática'}), \
             patch.object(ml.config, 'fonte_ml', {'paginas': 2}), \
             patch.object(ml, 'tem_sessao', return_value=True), \
             patch.object(ml, '_buscar_pagina_autenticada', side_effect=page), \
             patch.object(ml.time, 'sleep'):
            self.assertEqual([o.id_produto for o in ml.buscar_ofertas()], ['MLB1'])


class CookiesMLTest(unittest.TestCase):
    def test_empty_http_collection_uses_the_authenticated_browser(self):
        client = MagicMock()
        client.get.return_value.text = '<html></html>'
        offer = Oferta('mercadolivre', 'fixture', 'Produto', '', url_produto='https://www.mercadolivre.com.br/product')
        with patch.object(ml, 'sessao', return_value=client), \
             patch.object(ml, '_categorias', return_value={}), \
             patch.object(ml.config, 'fonte_ml', {'paginas': 1}), \
             patch.object(ml, 'tem_sessao', return_value=True), \
             patch.object(ml, '_buscar_pagina_autenticada', return_value=[offer]) as browser, \
             patch.object(ml.time, 'sleep'):
            self.assertEqual(ml.buscar_ofertas(), [offer])
        browser.assert_called_once_with({})

    def test_export_preserves_auth_fields_and_rejects_other_domains(self):
        cookie = {'name': 'fixture', 'value': 'fixture-session', 'domain': '.mercadolivre.com.br',
                  'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'no_restriction',
                  'expirationDate': time.time() + 3600, 'storeId': '0', 'session': False}
        imported = normalizar_cookies([cookie])[0]
        self.assertEqual(imported['value'], 'fixture-session')
        self.assertTrue(imported['httpOnly'])
        self.assertEqual(imported['sameSite'], 'None')
        self.assertNotIn('storeId', imported)
        with self.assertRaises(ValueError):
            normalizar_cookies([{**cookie, 'domain': '.mercadolivre.com.br.attacker.test'}])
        with self.assertRaises(ValueError):
            normalizar_cookies([{**cookie, 'expirationDate': time.time() - 60}])


if __name__ == '__main__':
    unittest.main()


class LinksAfiliadoMLTest(unittest.TestCase):
    def _ofertas(self, n):
        return [Oferta('mercadolivre', f'MLB{i}', f'P{i}', '', url_produto=f'https://ml/p/MLB{i}') for i in range(n)]

    def test_failed_batch_falls_back_to_each_url(self):
        ofertas = self._ofertas(3)
        def criar(page, urls, tag):
            if len(urls) > 1 or urls[0].endswith('MLB1'):
                raise RuntimeError('createLink respondeu HTTP 500: ')
            return ['https://meli.la/' + urls[0][-4:]]
        erros = []
        with patch.object(ml, '_criar_links_api', side_effect=criar):
            gerados = ml._links_do_lote(MagicMock(), ofertas, erros)
        self.assertEqual([o.id_produto for o in gerados], ['MLB0', 'MLB2'])
        self.assertEqual(ofertas[1].url_afiliado, '')
        self.assertTrue(erros)

    def test_retry_recovers_whole_batch(self):
        ofertas = self._ofertas(2)
        criar = MagicMock(side_effect=[RuntimeError('HTTP 500'), ['https://meli.la/a', 'https://meli.la/b']])
        with patch.object(ml, '_criar_links_api', criar):
            gerados = ml._links_do_lote(MagicMock(), ofertas, [])
        self.assertEqual(len(gerados), 2)
        self.assertEqual(criar.call_count, 2)
