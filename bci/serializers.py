from datetime import date
from decimal import Decimal

from rest_framework import serializers

from .services import TIPOS_MUTUARIO, normalizar_tipo_mutuario
from .tarifa_capital_decrescente import PRAZO_MAX, PRAZO_MIN


class SimulacaoRequestSerializer(serializers.Serializer):
    tipo_mutuario = serializers.CharField()
    montante_emprestimo = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal("0.01")
    )
    data_nascimento = serializers.DateField(input_formats=["%Y-%m-%d"])
    prazo_emprestimo = serializers.IntegerField(min_value=PRAZO_MIN, max_value=PRAZO_MAX)

    def validate_tipo_mutuario(self, valor):
        tipo = normalizar_tipo_mutuario(valor)
        if tipo not in TIPOS_MUTUARIO:
            raise serializers.ValidationError(
                f"Valor inválido. Use um de: {', '.join(TIPOS_MUTUARIO)}."
            )
        return tipo

    def validate_data_nascimento(self, valor: date):
        if valor >= date.today():
            raise serializers.ValidationError("A data de nascimento tem de ser no passado.")
        return valor


class SimulacaoResponseSerializer(serializers.Serializer):
    """Apenas para documentação (drf-spectacular / browsable API)."""

    montante_emprestimo = serializers.FloatField()
    premio_total = serializers.FloatField()
    premio_simples = serializers.FloatField()
    sobre_taxa = serializers.FloatField()
    selo = serializers.FloatField()
    comissao_bci = serializers.FloatField()
    taxa = serializers.FloatField(help_text="Taxa da tarifa em por mil (‰), por perfil x idade x prazo.")
