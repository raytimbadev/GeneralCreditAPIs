# Deploy no Ubuntu — rede interna

Gunicorn em `0.0.0.0:8000`, gerido por systemd. Sem proxy, sem TLS.

> **Só para rede fechada.** Sem TLS, o token de autenticação viaja em claro.
> Se a API for acessível da internet, é preciso pôr um proxy com HTTPS
> à frente (nginx ou Caddy) e fechar a porta 8000 no firewall.

Requer Python 3.10 ou superior (`python3 --version`). O `requirements.txt` usa
Django 5.2 LTS, que corre em 3.10 — o Django 6 exigiria Python 3.12+.

## 1. Servidor

```bash
sudo apt update && sudo apt install -y python3-venv
sudo useradd --system --home /opt/apps/bci_simulacao --shell /usr/sbin/nologin bci
sudo mkdir -p /opt/apps/bci_simulacao /etc/bci-api /var/lib/bci-api
```

## 2. Enviar o código

Se o código já estiver em `/opt/apps/bci_simulacao`, saltar este passo. Caso
contrário, da máquina local (substituir `SERVIDOR` pelo hostname ou IP real):

```bash
rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '*.sqlite3' \
  ./ utilizador@SERVIDOR:/tmp/bci-api/
ssh utilizador@SERVIDOR 'sudo rsync -a --delete /tmp/bci-api/ /opt/apps/bci_simulacao/'
```

## 3. Virtualenv

```bash
sudo python3 -m venv /opt/apps/bci_simulacao/.venv
sudo /opt/apps/bci_simulacao/.venv/bin/pip install -r /opt/apps/bci_simulacao/requirements.txt
sudo chown -R bci:bci /opt/apps/bci_simulacao /var/lib/bci-api
```

## 4. Configuração

```bash
sudo cp /opt/apps/bci_simulacao/deploy/env.example /etc/bci-api/env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # colar no ficheiro
sudo nano /etc/bci-api/env
sudo chown root:bci /etc/bci-api/env && sudo chmod 640 /etc/bci-api/env
```

O `SECRET_KEY` fica só neste ficheiro, nunca no repositório.

## 5. Base de dados e token

```bash
cd /opt/apps/bci_simulacao
# Atalho: corre o manage.py como o utilizador bci, com o /etc/bci-api/env carregado.
run() { sudo -u bci bash -c 'set -a; . /etc/bci-api/env; set +a
  exec /opt/apps/bci_simulacao/.venv/bin/python /opt/apps/bci_simulacao/manage.py "$@"' _ "$@"; }

run test bci                     # 41 testes, confirma que a stack esta ok
run migrate
run shell -c "from django.contrib.auth.models import User; User.objects.create_user('bciapp')"
run drf_create_token bciapp      # imprime o token da API
```

## 6. Arrancar

```bash
sudo cp /opt/apps/bci_simulacao/deploy/bci-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bci-api
sudo systemctl status bci-api
```

Logs: `sudo journalctl -u bci-api -f`

## 7. Confirmar

```bash
curl -X POST http://SERVIDOR:8000/api/bci/processes/quotation \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"tipo_mutuario":"TRABALHADORES","montante_emprestimo":1000000,
       "data_nascimento":"1996-01-01","prazo_emprestimo":5}'
```

---

## Actualizar

```bash
# repetir o passo 2, depois:
sudo /opt/apps/bci_simulacao/.venv/bin/pip install -r /opt/apps/bci_simulacao/requirements.txt
run migrate                      # a app tem modelos; nao saltar
sudo systemctl restart bci-api
```

O `run` e a funcao definida no passo 5. Numa sessao nova, colar outra vez.

## Notas

* Base SQLite: `quotation` e `tarif` não persistem nada. O
  `simulate-offline/` grava — cada venda registada, com o certificado de
  apólice em base64. Contar com isso no plano de backups de
  `/var/lib/bci-api/db.sqlite3`.
* `BCI_AGRAVAMENTO` em `/etc/bci-api/env` (0.10 = 10 %); requer `restart`.
* `--workers 3` no `.service`. Regra prática: `2 × núcleos + 1`.
* Restringir o acesso à porta 8000 à rede interna:
  `sudo ufw allow from 10.0.0.0/8 to any port 8000`
