import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ofertas import radar
from ofertas.models import Oferta


def _oferta():
    return Oferta('amazon', 'B0TESTE123', 'Mouse Gamer Logitech G203', 'https://www.amazon.com.br/dp/B0TESTE123?tag=x-20',
                  url_produto='https://www.amazon.com.br/dp/B0TESTE123', preco=99.9, preco_original=149.9,
                  imagem='https://m.media-amazon.com/images/I/x.jpg', categoria='Games > Acessórios > Mouses')


def _mensagem():
    return SimpleNamespace(message_id=42, chat=SimpleNamespace(id=-1003558182778, username=None))


class RadarTest(unittest.TestCase):
    def test_payload_carries_the_offer_and_the_channel_message(self):
        with patch.object(radar.config, 'radar_source_id', '189'):
            item = radar.payload(_oferta(), _mensagem())
        self.assertEqual((item['platform'], item['external_id'], item['source_id']), ('amazon', 'B0TESTE123', '189'))
        self.assertEqual(item['canonical_url'], 'https://www.amazon.com.br/dp/B0TESTE123')
        self.assertFalse(item['is_video'])
        self.assertEqual(item['source_rank'], 1)
        self.assertEqual(item['offer']['desconto'], 33)
        self.assertEqual(item['offer']['mensagem_url'], 'https://t.me/c/3558182778/42')
        self.assertIn('R$ 99,90', item['description'])
        self.assertIn('Categoria na loja: Games > Acessórios > Mouses.', item['description'])
        self.assertEqual(item['offer']['categoria'], 'Games > Acessórios > Mouses')

    def test_disabled_without_configuration(self):
        client = MagicMock()
        with patch.object(radar.config, 'radar_api_url', ''), patch.object(radar, 'sessao', return_value=client):
            radar.enviar_oferta(_oferta(), _mensagem())
        client.post.assert_not_called()

    def test_radar_failure_never_raises(self):
        client = MagicMock()
        client.post.side_effect = ConnectionError('fora do ar')
        with patch.object(radar.config, 'radar_api_url', 'https://radar.test/webhook/radar'), \
             patch.object(radar.config, 'radar_token', 't'), patch.object(radar.config, 'radar_source_id', '189'), \
             patch.object(radar, 'sessao', return_value=client):
            radar.enviar_oferta(_oferta(), _mensagem())
        url = client.post.call_args.args[0]
        self.assertEqual(url, 'https://radar.test/webhook/radar/ingest')


if __name__ == '__main__':
    unittest.main()
