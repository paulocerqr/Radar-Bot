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
