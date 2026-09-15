import re
from datetime import date
from decimal import Decimal

import yaml

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import ProcessoOffline
from .services import (
    idade_aniversario_mais_proximo,
    obter_taxa,
    simular,
    tabela_tarifa,
    TarifaIndisponivel,
)


class IdadeTests(APITestCase):
    def test_aniversario_mais_proximo(self):
        ref = date(2026, 9, 14)
        self.assertEqual(idade_aniversario_mais_proximo(date(1990, 9, 14), ref), 36)  # faz hoje
        self.assertEqual(idade_aniversario_mais_proximo(date(1990, 6, 1), ref), 36)   # 3 meses -> 36
        self.assertEqual(idade_aniversario_mais_proximo(date(1990, 1, 1), ref), 37)   # 8 meses -> 37
        self.assertEqual(idade_aniversario_mais_proximo(date(1990, 3, 14), ref), 37)  # exactamente 6 meses -> 37


class TaxaTests(APITestCase):
    def test_taxa_por_perfil(self):
        self.assertAlmostEqual(float(obter_taxa("TRABALHADORES", 18, 1)), 3.685402, places=5)
        self.assertAlmostEqual(float(obter_taxa("Mutuários", 18, 1)), 3.863561, places=5)
        self.assertAlmostEqual(float(obter_taxa("militares", 18, 1)), 4.651292, places=5)

    def test_nao_seguravel(self):
        with self.assertRaises(TarifaIndisponivel):
            obter_taxa("TRABALHADORES", 67, 7)  # "A" na tabela
        with self.assertRaises(TarifaIndisponivel):
            obter_taxa("MILITARES", 70, 4)
        with self.assertRaises(TarifaIndisponivel):
            obter_taxa("TRABALHADORES", 17, 1)
        with self.assertRaises(TarifaIndisponivel):
            obter_taxa("OUTRO", 30, 1)


class SimulacaoTests(APITestCase):
    @override_settings(BCI_AGRAVAMENTO=0)
    def test_formula_e_encargos(self):
        # trabalhador, 30 anos, 5 anos, 1.000.000 MZN, taxa 11.593849‰
        # taxa dá o TOTAL: 1.000.000 * 11.593849 / 1000 = 11593.85
        # simples = 11593.85 / 1.025 = 11311.07
        r = simular(Decimal("1000000"), date(1996, 9, 14), 5, "TRABALHADORES", referencia=date(2026, 9, 14))
        self.assertEqual(r.idade, 30)
        self.assertEqual(r.resposta()["taxa"], r.taxa)
        self.assertAlmostEqual(r.taxa, 11.593849, places=6)
        self.assertEqual(r.premio_total, 11593.85)
        self.assertEqual(r.premio_simples, 11311.07)
        self.assertEqual(r.sobre_taxa, 169.67)   # 1,5 %
        self.assertEqual(r.selo, 113.11)         # 1 %
        self.assertEqual(r.comissao_bci, 2375.32)  # 21 %
        # total reconstrói-se a partir das parcelas
        self.assertEqual(r.premio_total, r.premio_simples + r.sobre_taxa + r.selo)

    @override_settings(BCI_AGRAVAMENTO="0.10")
    def test_agravamento(self):
        r = simular(Decimal("1000000"), date(1996, 9, 14), 5, "TRABALHADORES", referencia=date(2026, 9, 14))
        self.assertEqual(r.premio_total, 12753.23)    # 11593.849 * 1.10
        self.assertEqual(r.premio_simples, 12442.18)  # 12753.23 / 1.025

    @override_settings(BCI_AGRAVAMENTO=0)
    def test_bate_com_folha_de_calculo(self):
        """Caso de referência de "Capital Decrescente Consumo Formulas.xlsx".

        Idade 26, duração 5, MUTUARIO NORMAL, capital 1.000.000, agravamento 0.
        Folha: taxa 12.1135 -> PT 12113.50, PS 11818.05, ST 177.27, S 118.18,
        comissão 2481.79. Tolerância de 2 cêntimos: a folha não arredonda os
        valores intermédios, o código arredonda o prémio simples ao cêntimo.
        """
        r = simular(Decimal("1000000"), date(2000, 1, 1), 5, "MUTUARIOS", referencia=date(2026, 1, 1))
        self.assertEqual(r.idade, 26)
        self.assertAlmostEqual(r.taxa, 12.1135, places=4)
        self.assertAlmostEqual(r.premio_total, 12113.50, delta=0.02)
        self.assertAlmostEqual(r.premio_simples, 11818.05, delta=0.02)
        self.assertAlmostEqual(r.sobre_taxa, 177.27, delta=0.02)
        self.assertAlmostEqual(r.selo, 118.18, delta=0.02)
        self.assertAlmostEqual(r.comissao_bci, 2481.79, delta=0.02)

    def test_encargos_sao_percentagens_do_premio_simples(self):
        from .services import SOBRE_TAXA_PCT, SELO_PCT, COMISSAO_BCI_PCT, FACTOR_ENCARGOS
        ps = Decimal("2794.44")
        self.assertEqual(round(ps * SOBRE_TAXA_PCT, 2), Decimal("41.92"))
        self.assertEqual(round(ps * SELO_PCT, 2), Decimal("27.94"))
        self.assertEqual(round(ps * COMISSAO_BCI_PCT, 2), Decimal("586.83"))
        # o factor total<->simples é coerente com a sobretaxa e o selo
        self.assertEqual(FACTOR_ENCARGOS, Decimal(1) + SOBRE_TAXA_PCT + SELO_PCT)


class EndpointTests(APITestCase):
    URL = "/api/bci/processes/quotation"

    def setUp(self):
        user = get_user_model().objects.create_user("bci", password="x")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_sem_token(self):
        self.client.credentials()
        resp = self.client.post(self.URL, {}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_sucesso(self):
        resp = self.client.post(self.URL, {
            "tipo_mutuario": "TRABALHADORES",
            "montante_emprestimo": "1000000",
            "data_nascimento": "1996-01-01",
            "prazo_emprestimo": 5,
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), {"montante_emprestimo", "premio_total", "premio_simples", "sobre_taxa", "selo", "comissao_bci", "taxa"})
        self.assertEqual(resp.data["montante_emprestimo"], 1000000.0)
        # a taxa devolvida reproduz o prémio total
        self.assertAlmostEqual(resp.data["premio_total"], 1000000.0 * resp.data["taxa"] / 1000, delta=0.02)
        self.assertAlmostEqual(resp.data["premio_total"], resp.data["premio_simples"] + resp.data["sobre_taxa"] + resp.data["selo"], places=2)
        self.assertAlmostEqual(resp.data["premio_total"], resp.data["premio_simples"] * 1.025, delta=0.02)

    def test_campo_desconhecido_e_ignorado(self):
        """id_bci foi removido do contrato; um cliente antigo que ainda o envie
        continua a ser servido (o serializer ignora campos não declarados)."""
        resp = self.client.post(self.URL, {
            "id_bci": "BCITESTE0084",
            "tipo_mutuario": "TRABALHADORES",
            "montante_emprestimo": "1000000",
            "data_nascimento": "1996-01-01",
            "prazo_emprestimo": 5,
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn("id_bci", resp.data)

    def test_validacao(self):
        resp = self.client.post(self.URL, {
            "tipo_mutuario": "ESTUDANTES",
            "montante_emprestimo": "abc",
            "data_nascimento": "01/01/1990",
            "prazo_emprestimo": 9,
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        for campo in ("tipo_mutuario", "montante_emprestimo", "data_nascimento", "prazo_emprestimo"):
            self.assertIn(campo, resp.data)

    def test_nao_seguravel_400(self):
        resp = self.client.post(self.URL, {
            "tipo_mutuario": "MUTUARIOS",
            "montante_emprestimo": "500000",
            "data_nascimento": "1958-01-01",  # 68/69 anos
            "prazo_emprestimo": 7,
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data)


class TabelaTarifaTests(APITestCase):
    def test_um_perfil(self):
        t = tabela_tarifa("TRABALHADORES")
        self.assertEqual(t["tipos_mutuario"], ["TRABALHADORES"])
        self.assertEqual(t["prazos"], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(len(t["tarifas"]), 53)  # idades 18..70
        primeira = t["tarifas"][0]
        self.assertEqual(primeira["idade"], 18)
        self.assertAlmostEqual(primeira["taxas"]["1"], 3.685402, places=6)
        self.assertEqual(t["tarifas"][-1]["idade"], 70)

    def test_todos_os_perfis_por_omissao(self):
        t = tabela_tarifa()
        self.assertEqual(t["tipos_mutuario"], ["TRABALHADORES", "MUTUARIOS", "MILITARES"])
        self.assertEqual(len(t["tarifas"]), 53 * 3)

    def test_nao_seguravel_vem_a_null(self):
        linhas = {l["idade"]: l for l in tabela_tarifa("TRABALHADORES")["tarifas"]}
        self.assertIsNone(linhas[67]["taxas"]["7"])  # "A" na tabela de origem
        self.assertIsNotNone(linhas[67]["taxas"]["1"])

    def test_tipo_invalido(self):
        with self.assertRaises(TarifaIndisponivel):
            tabela_tarifa("ESTUDANTES")

    def test_tarifa_bate_com_obter_taxa(self):
        linhas = {l["idade"]: l for l in tabela_tarifa("Mutuários")["tarifas"]}
        self.assertAlmostEqual(linhas[26]["taxas"]["5"], float(obter_taxa("MUTUARIOS", 26, 5)), places=6)


class TarifaEndpointTests(APITestCase):
    URL = "/api/bci/processes/tarif"

    def setUp(self):
        user = get_user_model().objects.create_user("bci", password="x")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_sem_token(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_por_tipo_mutuario(self):
        resp = self.client.get(self.URL, {"tipo_mutuario": "militares"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["tipos_mutuario"], ["MILITARES"])
        self.assertEqual(len(resp.data["tarifas"]), 53)

    def test_sem_parametro_devolve_tudo(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data["tarifas"]), 53 * 3)

    def test_tipo_invalido_400(self):
        resp = self.client.get(self.URL, {"tipo_mutuario": "ESTUDANTES"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data)


class DocumentacaoTests(APITestCase):
    """A documentação é aberta: o browser tem de a conseguir abrir sem token."""

    def test_pagina_sem_token(self):
        resp = self.client.get("/api/bci/docs")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("text/html"))
        corpo = resp.content.decode()
        self.assertIn("/processes/quotation", corpo)
        self.assertIn("/processes/tarif", corpo)

    def test_pagina_nao_depende_de_cdn(self):
        """Tem de abrir numa rede fechada: sem scripts, só fontes externas."""
        corpo = self.client.get("/api/bci/docs").content.decode()
        self.assertNotIn("<script", corpo)
        externos = re.findall(r'(?:src|href)="(https?://[^"]+)"', corpo)
        for url in externos:
            self.assertTrue(
                url.startswith("https://fonts."),
                f"recurso externo inesperado: {url}",
            )

    def test_spec_sem_token(self):
        resp = self.client.get("/api/bci/openapi.yaml")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/yaml"))
        spec = yaml.safe_load(b"".join(resp.streaming_content))
        self.assertEqual(spec["openapi"], "3.0.3")
        self.assertEqual(
            set(spec["paths"]),
            {"/processes/quotation", "/processes/tarif", "/processes/simulate-offline/"},
        )

    def test_spec_descreve_a_resposta_real(self):
        """Guarda contra a spec e o código divergirem."""
        user = get_user_model().objects.create_user("docs", password="x")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        spec = yaml.safe_load(
            b"".join(self.client.get("/api/bci/openapi.yaml").streaming_content)
        )
        real = self.client.post("/api/bci/processes/quotation", {
            "tipo_mutuario": "TRABALHADORES",
            "montante_emprestimo": "1000000",
            "data_nascimento": "1996-01-01",
            "prazo_emprestimo": 5,
        }, format="json").data
        documentado = spec["components"]["schemas"]["SimulacaoResponse"]["properties"]
        self.assertEqual(set(documentado), set(real))

    def test_pagina_e_spec_documentam_as_mesmas_mensagens_de_erro(self):
        """A página HTML e a spec têm de citar o mesmo texto de erro real."""
        pagina = self.client.get("/api/bci/docs").content.decode()
        spec = b"".join(self.client.get("/api/bci/openapi.yaml").streaming_content).decode()

        user = get_user_model().objects.create_user("erros", password="x")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
        reais = self.client.post("/api/bci/processes/quotation", {
            "tipo_mutuario": "ESTUDANTES",
            "montante_emprestimo": "abc",
            "prazo_emprestimo": 9,
        }, format="json").data

        for campo in ("tipo_mutuario", "montante_emprestimo", "prazo_emprestimo"):
            mensagem = str(reais[campo][0])
            self.assertIn(mensagem, spec, f"spec desactualizada para {campo}")
            self.assertIn(mensagem, pagina, f"página desactualizada para {campo}")

    @override_settings(BCI_DOCS=False)
    def test_pode_ser_desligada(self):
        self.assertEqual(self.client.get("/api/bci/docs").status_code, 404)
        self.assertEqual(self.client.get("/api/bci/openapi.yaml").status_code, 404)


# Payload real do canal: prazo 12 (fora da tarifa) e base64 truncado. O stub
# aceita ambos de propósito — não valida o risco nem o certificado.
PEDIDO_OFFLINE = {
    "id_bci": "EMOSETESTE0063",
    "transaction_ref": "TRX-2026-000841",
    "tipo_mutuario": "trabalhador",
    "montante_emprestimo": 1000000.00,
    "data_nascimento": "1995-01-21",
    "prazo_emprestimo": 12,
    "agravamento": 0.00,
    "premio_pago": 11843.99,
    "comissao": 2426.57,
    "certificado_apolice": "JVBERi0xLjQKJeLjz9MK...",
    "nome_cliente": "Raimundo L. Timba",
    "nuit": "125454958",
    "fuma": "Sim",
    "af_diabetes": "sim",
    "ap_hiv": "Sim",
}

RESPOSTA_ESPERADA = {
    "message": "Cotação aprovada. RPA INSIS iniciado para emissão de apólice.",
    "id_bci": "EMOSETESTE0063",
    "estado_processo": "aprovado",
}


def _pedido(**alteracoes):
    pedido = dict(PEDIDO_OFFLINE)
    pedido.update(alteracoes)
    return pedido


class SimulateOfflineTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("offline", password="x")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}"
        )
        self.url = "/api/bci/processes/simulate-offline/"

    def test_exige_token(self):
        self.client.credentials()
        self.assertEqual(self.client.post(self.url, _pedido(), format="json").status_code, 401)

    def test_resposta_e_sempre_a_mesma(self):
        resp = self.client.post(self.url, _pedido(), format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, RESPOSTA_ESPERADA)

    def test_id_bci_vem_do_pedido(self):
        resp = self.client.post(self.url, _pedido(id_bci="OUTRO-123"), format="json")
        self.assertEqual(resp.data["id_bci"], "OUTRO-123")
        self.assertEqual(resp.data["estado_processo"], "aprovado")

    def test_sem_id_bci_devolve_vazio(self):
        pedido = _pedido()
        del pedido["id_bci"]
        resp = self.client.post(self.url, pedido, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id_bci"], "")

    def test_corpo_vazio_e_aceite(self):
        """Stub: não há campos obrigatórios."""
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["estado_processo"], "aprovado")

    def test_nao_valida_o_risco(self):
        """Prazo 12 e perfil desconhecido não são rejeitados — não há cálculo."""
        resp = self.client.post(
            self.url,
            _pedido(prazo_emprestimo=99, tipo_mutuario="ESTUDANTES", data_nascimento="nao-e-data"),
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_guarda_o_payload_completo(self):
        self.client.post(self.url, _pedido(), format="json")
        processo = ProcessoOffline.objects.get()
        self.assertEqual(processo.id_bci, "EMOSETESTE0063")
        self.assertEqual(processo.transaction_ref, "TRX-2026-000841")
        self.assertEqual(processo.dados["nome_cliente"], "Raimundo L. Timba")
        self.assertEqual(processo.dados["ap_hiv"], "Sim")
        self.assertEqual(float(processo.premio_pago), 11843.99)
        self.assertEqual(float(processo.comissao), 2426.57)

    def test_certificado_guardado_fora_do_json(self):
        self.client.post(self.url, _pedido(), format="json")
        processo = ProcessoOffline.objects.get()
        self.assertEqual(processo.certificado_apolice, "JVBERi0xLjQKJeLjz9MK...")
        self.assertNotIn("certificado_apolice", processo.dados)

    def test_valores_nao_numericos_nao_rebentam(self):
        resp = self.client.post(
            self.url, _pedido(premio_pago="nao-e-numero", comissao=""), format="json"
        )
        self.assertEqual(resp.status_code, 200)
        processo = ProcessoOffline.objects.get()
        self.assertIsNone(processo.premio_pago)
        self.assertIsNone(processo.comissao)

    def test_transaction_ref_repetida_nao_duplica(self):
        self.client.post(self.url, _pedido(), format="json")
        segundo = self.client.post(self.url, _pedido(premio_pago=999), format="json")
        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(segundo.data, RESPOSTA_ESPERADA)
        self.assertEqual(ProcessoOffline.objects.count(), 1)

    def test_sem_transaction_ref_cada_pedido_e_um_registo(self):
        pedido = _pedido()
        del pedido["transaction_ref"]
        self.client.post(self.url, pedido, format="json")
        self.client.post(self.url, pedido, format="json")
        self.assertEqual(ProcessoOffline.objects.count(), 2)

    def test_guarda_quem_registou(self):
        self.client.post(self.url, _pedido(), format="json")
        self.assertEqual(ProcessoOffline.objects.get().registado_por, self.user)

    def test_funciona_com_e_sem_barra_final(self):
        """Sem as duas rotas, o APPEND_SLASH devolvia 301 e havia clientes a
        perder o corpo do POST no redireccionamento."""
        for rota in (
            "/api/bci/processes/simulate-offline/",
            "/api/bci/processes/simulate-offline",
        ):
            with self.subTest(rota=rota):
                resp = self.client.post(rota, _pedido(), format="json")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.data, RESPOSTA_ESPERADA)

    def test_spec_descreve_a_resposta_real(self):
        """Guarda contra a spec e o stub divergirem."""
        spec = yaml.safe_load(
            b"".join(self.client.get("/api/bci/openapi.yaml").streaming_content)
        )
        rota = spec["paths"]["/processes/simulate-offline/"]["post"]
        documentado = rota["responses"]["200"]["content"]["application/json"]["example"]
        real = self.client.post(self.url, _pedido(), format="json").data
        self.assertEqual(documentado, dict(real))
