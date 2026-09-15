# API de simulação — Capital Decrescente (Consumo) BCI

App Django/DRF `bci` com o endpoint `POST /api/bci/processes/quotation`.

## Instalação no projecto existente (emose-serviops)

1. Copiar a pasta `bci/` para o projecto (ou, se já existir uma app `bci`,
   juntar `services.py`, `serializers.py`, `tarifa_capital_decrescente.py`,
   a view e a rota).
2. `settings.py`:
   ```python
   INSTALLED_APPS += ["rest_framework", "rest_framework.authtoken", "bci"]
   BCI_AGRAVAMENTO = 0        # agravamento fixo, ex.: 0.10 = 10 %
   ```
3. `urls.py` principal:
   ```python
   path("api/bci/", include("bci.urls")),
   ```
4. Testes: `python manage.py test bci`

## Pedido

```bash
curl -X POST https://emose-serviops.com/api/bci/processes/quotation \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_mutuario": "TRABALHADORES",
    "montante_emprestimo": 1000000,
    "data_nascimento": "1996-01-01",
    "prazo_emprestimo": 5
  }'
```

`tipo_mutuario`: `TRABALHADORES`, `MUTUARIOS` ou `MILITARES`
(aceita minúsculas e acentos — "Mutuários" é normalizado).

## Resposta

```json
{
  "montante_emprestimo": 1000000.0,
  "premio_total": 11843.99,
  "premio_simples": 11555.11,
  "sobre_taxa": 173.33,
  "selo": 115.55,
  "comissao_bci": 2426.57,
  "taxa": 11.843988
}
```

`taxa` é a taxa da tarifa em por mil (‰) usada no cálculo, por perfil × idade
× prazo — devolvida para se poder conferir o resultado.

Os valores dependem da idade à data da simulação, logo variam com a data do
pedido para a mesma `data_nascimento`.

## Documentação

Servida pela própria API, sem autenticação:

| Rota | O quê |
|---|---|
| `GET /api/bci/docs` | Referência em HTML, para ler no browser |
| `GET /api/bci/openapi.yaml` | Especificação OpenAPI 3.0 |

A página é auto-contida — sem CDN e sem JavaScript — para abrir numa rede
fechada. O ficheiro fonte é [`bci/openapi.yaml`](bci/openapi.yaml); importa-se
no Postman (*Import* → *File*) ou cola-se em <https://editor.swagger.io>.

Para esconder ambas as rotas em produção, `BCI_DOCS=0` no ambiente: passam
a 404.

## Regras de cálculo

| Item | Regra |
|---|---|
| Idade | Idade no aniversário mais próximo, à data da simulação |
| Taxa (‰) | Tabela `tarifa_capital_decrescente.py` por perfil × idade (18–70) × prazo (1–7) |
| Prémio total | `montante × taxa / 1000 × (1 + agravamento)` |
| Prémio simples | `prémio total / 1,025` |
| Sobretaxa | 1,5 % do prémio simples |
| Selo | 1 % do prémio simples |
| Comissão BCI | 21 % do prémio simples |

A taxa da tarifa produz o prémio **total** (já com encargos incluídos); o
prémio simples obtém-se por divisão por 1,025 (= 1 + 1,5 % + 1 %). Confere-se
depois que `total = simples + sobretaxa + selo`. Regra e percentagens seguem a
folha `Capital Decrescente Consumo Formulas.xlsx`; constantes em `services.py`.

## Erros

* `401` sem token ou token inválido.
* `400` com erros por campo (validação do serializer).
* `400 {"detail": "Não segurável: idade 67 com prazo de 7 anos (TRABALHADORES)."}`
  para combinações marcadas "A" na tabela ou fora dos limites.

## Registo de vendas offline (stub)

`POST /api/bci/processes/simulate-offline/` — aceite com e sem barra final.

**Não valida nada e não calcula nada.** Guarda o pedido e responde sempre o
mesmo; quem emite a apólice é o RPA INSIS, a jusante.

### Campos de entrada

Os 97 campos que o canal envia numa venda ao balcão. **Nenhum é
obrigatório e nenhum é validado** — o que faltar fica de fora do registo, o que
vier a mais é guardado na mesma, e valores fora da tarifa
(`prazo_emprestimo: 12`) não são rejeitados, porque não há cálculo.

Descrição campo a campo em `GET /api/bci/docs`.

**Identificação do processo** — `id_bci`, `transaction_ref`

**Empréstimo (eco da cotação)** — `tipo_mutuario`, `montante_emprestimo`, `data_nascimento`, `prazo_emprestimo`, `agravamento`

**Cliente** — `nuit`, `nome_cliente`, `apelido`, `tipo_entidade`, `sexo`, `pais`, `nacionalidade`, `lingua`

**Morada** — `tipo_morada`, `provincia`, `regiao`, `bairro`, `morada`

**Contacto** — `tipo_contacto`, `numero_contacto`, `lingua_contacto`

**Dados bancários** — `codigo_banco`, `numero_conta`, `tipo_moeda`

**Apólice** — `tipo_seguro`, `canal_venda`, `data_emissao`, `data_apolice`, `data_inicio_seguro`, `papel`, `quota`, `estado`, `designacao`, `lingua_apolice`, `tipo_pagamento`, `num_prestacoes`, `man_id`, `tipo_segurado`, `capital_seguro`, `premio_pago`, `comissao`, `certificado_apolice`

**Questionário clínico — hábitos** — `altura_cm`, `peso_kg`, `fuma`, `fuma_anos_cigarros`, `bebe_bebidas_alcoolicas`, `bebe_frequencia`, `pratica_desporto`, `tipo_desporto`, `toma_drogas_medicamentos`, `tipo_tempo_medicamentos`

**Antecedentes familiares (af_*)** — `af_diabetes`, `af_colesterol_alto`, `af_doencas_cardiacas`, `af_avc`, `af_hipertensao`, `af_doenca_neurologica_mental`, `af_cancro`, `af_retinite_pigmentosa`, `af_porfiria`, `af_hemofilia`, `af_outra_doenca_hereditaria`, `af_morte_familiar_menos_65`

**Antecedentes pessoais (ap_*)** — `ap_tratamento_cirurgico`, `ap_tratamento_cirurgico_especifique`, `ap_diagnostico_5anos`, `ap_diagnostico_5anos_descreva`, `ap_febre_reumatica_coracao`, `ap_pressao_arterial_avc`, `ap_doenca_pulmonar`, `ap_sistema_digestivo`, `ap_condicoes_rins`, `ap_ansiedade_depressao`, `ap_diabetes_glandular`, `ap_articulacoes_coluna`, `ap_tumores`, `ap_doencas_sangue`, `ap_hiv`, `ap_hiv_indique`, `ap_doenca_sexual`, `ap_deficiencia`, `ap_circunstancias_risco`, `ap_outra_doenca`, `ap_outra_doenca_mencione`

**Saúde feminina (sf_*)** — `sf_esta_gravida`, `sf_gravida_meses`, `sf_esteve_gravida`, `sf_esteve_gravida_detalhes`, `sf_tipo_partos`, `sf_numero_partos_anos`, `sf_aborto_prematuro`, `sf_aborto_meses`, `sf_doenca_ginecologica`, `sf_doenca_ginecologica_mencione`

Cinco campos ficam em colunas próprias do registo — `id_bci`,
`transaction_ref`, `premio_pago`, `comissao` e `certificado_apolice`. Todos os
outros ficam no JSON `dados`, tal como vieram. As respostas do questionário
chegam como texto (`Sim` / `Nao`, com e sem maiúsculas) e não são normalizadas;
os campos `sf_*` só vêm preenchidos quando `sexo` é `F`.

### Pedido

```bash
curl -X POST https://emose-serviops.com/api/bci/processes/simulate-offline/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  --data-binary @venda.json
```

`venda.json`:

```json
{
  "id_bci": "EMOSETESTE0063",
  "transaction_ref": "TRX-2026-000841",
  "tipo_mutuario": "trabalhador",
  "montante_emprestimo": 1000000.0,
  "data_nascimento": "1995-01-21",
  "prazo_emprestimo": 12,
  "agravamento": 0.0,
  "nuit": "125454958",
  "nome_cliente": "Raimundo L. Timba",
  "apelido": "Timba",
  "tipo_entidade": "person",
  "sexo": "M",
  "pais": "Moçambique",
  "nacionalidade": "MZ",
  "lingua": "PORTUGUESE",
  "tipo_morada": "Casa",
  "provincia": "Maputo Cidade",
  "regiao": "Distrito Municipal de KaMpfumo",
  "bairro": "Polana Cimento A",
  "morada": "Av. Julius Nyerere 123",
  "tipo_contacto": "Mobile",
  "numero_contacto": "847527898",
  "lingua_contacto": "Portugues",
  "codigo_banco": "0008",
  "numero_conta": "123456789012",
  "tipo_moeda": "MZN",
  "tipo_seguro": "vida",
  "canal_venda": "balcao",
  "data_emissao": "2026-01-18",
  "data_apolice": "2026-01-18",
  "data_inicio_seguro": "2026-01-18",
  "papel": "tomador",
  "quota": 100.0,
  "estado": "activo",
  "designacao": "Seguro Vida Credito Consumo",
  "lingua_apolice": "Portugues",
  "tipo_pagamento": "debito_conta",
  "num_prestacoes": 1,
  "man_id": "6000035452",
  "tipo_segurado": "principal",
  "capital_seguro": 1000000.0,
  "premio_pago": 11843.99,
  "comissao": 2426.57,
  "certificado_apolice": "JVBERi0xLjQKJeLjz9MK...",
  "altura_cm": 175,
  "peso_kg": 70.0,
  "fuma": "Sim",
  "fuma_anos_cigarros": "12 anos, 5 por dia",
  "bebe_bebidas_alcoolicas": "Sim",
  "bebe_frequencia": "Ao fim-de-semana",
  "pratica_desporto": "Nao",
  "tipo_desporto": "",
  "toma_drogas_medicamentos": "Nao",
  "tipo_tempo_medicamentos": "",
  "af_diabetes": "Sim",
  "af_colesterol_alto": "Nao",
  "af_doencas_cardiacas": "Nao",
  "af_avc": "Sim",
  "af_hipertensao": "Nao",
  "af_doenca_neurologica_mental": "Nao",
  "af_cancro": "Nao",
  "af_retinite_pigmentosa": "Nao",
  "af_porfiria": "Nao",
  "af_hemofilia": "Nao",
  "af_outra_doenca_hereditaria": "Nao",
  "af_morte_familiar_menos_65": "Nao",
  "ap_tratamento_cirurgico": "Sim",
  "ap_tratamento_cirurgico_especifique": "Apendicectomia em 2019",
  "ap_diagnostico_5anos": "Nao",
  "ap_diagnostico_5anos_descreva": "",
  "ap_febre_reumatica_coracao": "Nao",
  "ap_pressao_arterial_avc": "Nao",
  "ap_doenca_pulmonar": "Nao",
  "ap_sistema_digestivo": "Nao",
  "ap_condicoes_rins": "Nao",
  "ap_ansiedade_depressao": "Sim",
  "ap_diabetes_glandular": "Nao",
  "ap_articulacoes_coluna": "Nao",
  "ap_tumores": "Nao",
  "ap_doencas_sangue": "Nao",
  "ap_hiv": "Nao",
  "ap_hiv_indique": "",
  "ap_doenca_sexual": "Nao",
  "ap_deficiencia": "Nao",
  "ap_circunstancias_risco": "Nao",
  "ap_outra_doenca": "Nao",
  "ap_outra_doenca_mencione": "",
  "sf_esta_gravida": "Nao",
  "sf_gravida_meses": "",
  "sf_esteve_gravida": "Nao",
  "sf_esteve_gravida_detalhes": "",
  "sf_tipo_partos": "",
  "sf_numero_partos_anos": "",
  "sf_aborto_prematuro": "Nao",
  "sf_aborto_meses": "",
  "sf_doenca_ginecologica": "Nao",
  "sf_doenca_ginecologica_mencione": ""
}
```

### Resposta

```json
{
  "message": "Cotação aprovada. RPA INSIS iniciado para emissão de apólice.",
  "id_bci": "EMOSETESTE0063",
  "estado_processo": "aprovado"
}
```

`message` e `estado_processo` são constantes. `id_bci` é devolvido tal como
veio no pedido — vazio se não vier. Qualquer corpo JSON serve, incluindo vazio:
só o token é exigido.

Com `transaction_ref` é idempotente — repetir não cria um segundo registo.

É o único endpoint que grava, logo o deploy precisa de `migrate`.
## Deploy

Para correr como serviço próprio num servidor Ubuntu, ver [DEPLOY.md](DEPLOY.md)
(gunicorn + systemd, rede interna). O wrapper Django standalone está em
`config/` e o ficheiro de serviço em `deploy/`.
