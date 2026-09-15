# Integrar a app `bci` no backend emose-serviops

Alternativa ao `DEPLOY.md`, que descreve um serviço à parte. Aqui a app entra
no projecto Django que já corre em `/home/Emose_Serviops/backend`, e reaproveita
a base de dados, os tokens e o nginx que já lá estão.

## 0. Antes de tudo: o que já ocupa `/api/bci/`

O servidor já responde em `/api/bci/processes/simulate-offline/`. Saber de onde
vem, antes de montar rotas por cima:

```bash
cd /home/Emose_Serviops/backend
source venv/bin/activate
python manage.py shell -c "
from django.urls import get_resolver
for p in get_resolver().url_patterns:
    for s in getattr(p, 'url_patterns', [p]):
        r = str(p.pattern) + str(s.pattern)
        if 'bci' in r: print(f'{r:55} -> {s.callback.__module__}.{s.callback.__qualname__}')
"
```

Três cenários:

* **Nada em `/api/bci/processes/`** — seguir os passos abaixo tal e qual.
* **Rotas de `bci_credit` com outros nomes** — seguir abaixo; convivem.
* **`bci_credit` já tem `quotation` / `tarif` / `simulate-offline`** — parar.
  É substituição, não adição: essas views correm a fórmula antiga, que
  multiplicava por `(1 + agravamento)` em vez de dividir por 1,025 e
  inflacionava todos os valores em 2,5 %. Decidir primeiro o que fica e o que
  sai, e se há registos já emitidos com os valores errados.

## 1. Copiar a app

Só a pasta `bci/`. O `manage.py`, `config/`, `deploy/`, `requirements.txt` e os
`settings_*.py` são do serviço standalone e **não** vão.

```bash
rsync -av --exclude '__pycache__' \
  ./bci/ utilizador@servidor:/tmp/bci-app/
ssh utilizador@servidor 'sudo rsync -a --delete /tmp/bci-app/ /home/Emose_Serviops/backend/bci/'
```

Conteúdo que tem de chegar lá:

```
bci/__init__.py
bci/models.py                       ProcessoOffline
bci/migrations/__init__.py
bci/migrations/0001_initial.py
bci/serializers.py
bci/services.py                     cálculo do prémio
bci/tarifa_capital_decrescente.py   tabela de taxas
bci/urls.py
bci/views.py
bci/tests.py
bci/openapi.yaml                    servido em /openapi.yaml
bci/docs.html                       servido em /docs
```

`openapi.yaml` e `docs.html` não são estáticos do Django — são lidos do disco
pelas views, com `Path(__file__).parent`. Não precisam de `collectstatic`, mas
têm de ir na cópia ou o `/docs` dá 500.

## 2. `backend/settings.py`

`rest_framework` e `rest_framework.authtoken` já lá estão. Falta:

```python
INSTALLED_APPS = [
    ...
    "bci",
]

# Agravamento fixo aplicado ao prémio (0.10 = 10 %).
BCI_AGRAVAMENTO = float(os.environ.get("BCI_AGRAVAMENTO", "0"))

# Documentação em /api/bci/docs e /api/bci/openapi.yaml, sem autenticação.
# BCI_DOCS=0 esconde ambas (404).
BCI_DOCS = os.environ.get("BCI_DOCS", "1") not in ("0", "false", "False")
```

As views declaram a sua própria autenticação (`TokenAuthentication` +
`IsAuthenticated`), logo não dependem do `DEFAULT_AUTHENTICATION_CLASSES` do
projecto nem são afectadas pela paginação que lá está configurada.

## 3. `backend/urls.py`

```python
path("api/bci/", include("bci.urls")),
```

Se `bci_credit` já monta alguma coisa em `api/bci/`, usar outro prefixo para
não colidir — e actualizar os clientes:

```python
path("api/bci-seguro/", include("bci.urls")),
```

Rotas que a app passa a servir sob esse prefixo:

| Rota | Método | Auth |
|---|---|---|
| `processes/quotation` | POST | token |
| `processes/tarif` | GET | token |
| `processes/simulate-offline` e `simulate-offline/` | POST | token |
| `docs` | GET | aberta |
| `openapi.yaml` | GET | aberta |

As rotas **não têm barra final**, excepto `simulate-offline`, que aceita as duas
formas de propósito: sem ambas, o `APPEND_SLASH` responde 301 a um POST e há
clientes que perdem o corpo do pedido.

## 4. Migrar

A app tem modelo (`ProcessoOffline`), logo a migração não é opcional:

```bash
cd /home/Emose_Serviops/backend
source venv/bin/activate
python manage.py test bci        # 41 testes
python manage.py migrate bci
```

Cria a tabela `bci_processooffline` na base que já lá está. Não toca em mais nada.

## 5. Reiniciar e confirmar

```bash
sudo systemctl restart site-backend
```

```bash
TOKEN=<token existente>
BASE=https://emose-serviops.com/api/bci

curl -X POST $BASE/processes/quotation \
  -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
  -d '{"tipo_mutuario":"TRABALHADORES","montante_emprestimo":1000000,
       "data_nascimento":"1996-01-01","prazo_emprestimo":5}'
```

Confirmar que `premio_total = montante × taxa / 1000`. Com a fórmula antiga o
`premio_simples` vinha com esse valor — se for o caso, a app velha ainda está a
responder.

```bash
curl "$BASE/processes/tarif?tipo_mutuario=TRABALHADORES" -H "Authorization: Token $TOKEN"
curl $BASE/docs          # sem token
```

## Backups

`quotation` e `tarif` não persistem nada. O `simulate-offline` grava cada venda,
com o certificado de apólice em base64 dentro da linha. A base cresce, e passa a
ter dados pessoais e clínicos — entra no plano de backups e de retenção.

## Antes de considerar isto terminado

Três coisas vistas no traceback de produção, independentes desta integração:

* **`DEBUG = True`.** A página de erro é pública e mostra apps, middleware,
  caminhos, `ALLOWED_HOSTS`, servidor SMTP e IPs internos. Pôr a `False`.
* **`runserver` como root.** `SERVER_SOFTWARE: WSGIServer/0.2`, `USER: root`.
  É servidor de desenvolvimento. Devia ser gunicorn atrás do nginx, com
  utilizador dedicado.
* **`SECURE_PROXY_SSL_HEADER` a `None`** com o proxy a mandar
  `X-Forwarded-Proto: https`. O Django julga que o pedido é HTTP, e
  `request.is_secure()` devolve falso. Corrigir com
  `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
