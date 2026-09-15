"""Registo de vendas fechadas fora do sistema (canal offline).

O ``simulate-offline`` é, para já, um stub: não valida o risco nem calcula
prémio. Aceita o que o canal enviar, guarda tudo, e responde sempre aprovado —
quem emite a apólice é o RPA INSIS, a jusante.

O que se guarda aqui é o registo do que foi recebido, para haver rasto quando
a lógica real entrar.
"""
from django.conf import settings
from django.db import models


class ProcessoOffline(models.Model):
    # Referência da transacção no sistema de origem. Chave de idempotência
    # quando vem; a null para os pedidos que não a trazem (nulls não colidem
    # em índices unique).
    transaction_ref = models.CharField(max_length=100, unique=True, null=True, blank=True)
    id_bci = models.CharField(max_length=64, db_index=True, blank=True)

    # Valores da venda, tal como vieram do canal. Sem cálculo nem conferência.
    premio_pago = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    comissao = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Certificado de apólice, base64 tal como recebido.
    certificado_apolice = models.TextField(blank=True)

    # Payload completo, para não se perder nada do que o canal enviou.
    dados = models.JSONField(default=dict, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    registado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processos_offline",
    )

    class Meta:
        verbose_name = "processo offline"
        verbose_name_plural = "processos offline"
        ordering = ("-criado_em",)

    def __str__(self):
        return f"{self.transaction_ref or 'sem ref'} ({self.id_bci or 'sem id_bci'})"
