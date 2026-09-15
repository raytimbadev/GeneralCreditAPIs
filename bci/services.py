"""Cálculo do prémio de Capital Decrescente (Consumo) — BCI.

Fórmula (folha "Capital Decrescente Consumo Formulas.xlsx"):
    premio_total   = montante_emprestimo * taxa / 1000 * (1 + agravamento)
    premio_simples = premio_total / 1.025

A taxa da tarifa produz o prémio TOTAL (já com encargos); o prémio simples
é obtido por divisão, não por multiplicação.

Encargos, todos sobre o prémio simples:
    sobre_taxa   = 1,5 %
    selo         = 1 %
    premio_total = premio_simples + sobre_taxa + selo   (= simples * 1,025)
    comissao_bci = 21 %
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import unicodedata

from django.conf import settings

from .tarifa_capital_decrescente import (
    IDADE_MAX,
    IDADE_MIN,
    PRAZO_MAX,
    PRAZO_MIN,
    TARIFA,
)

# Percentagens fixas dos encargos
# Factor que converte prémio total -> prémio simples (1 + 1,5 % + 1 %)
FACTOR_ENCARGOS = Decimal("1.025")
SOBRE_TAXA_PCT = Decimal("0.015")
SELO_PCT = Decimal("0.01")
COMISSAO_BCI_PCT = Decimal("0.21")

TIPOS_MUTUARIO = tuple(TARIFA.keys())  # ("TRABALHADORES", "MUTUARIOS", "MILITARES")

_CENT = Decimal("0.01")


class TarifaIndisponivel(Exception):
    """Idade/prazo/perfil sem taxa na tarifa (não segurável)."""


def agravamento() -> Decimal:
    """Agravamento fixo, configurado em settings.BCI_AGRAVAMENTO (ex.: 0.10 = 10 %)."""
    return Decimal(str(getattr(settings, "BCI_AGRAVAMENTO", 0)))



def normalizar_tipo_mutuario(valor: str) -> str:
    """'Mutuários' -> 'MUTUARIOS'; aceita maiúsculas/minúsculas e acentos."""
    sem_acentos = unicodedata.normalize("NFKD", valor or "")
    sem_acentos = "".join(c for c in sem_acentos if not unicodedata.combining(c))
    return sem_acentos.strip().upper()


def idade_aniversario_mais_proximo(data_nascimento: date, referencia: date | None = None) -> int:
    """Idade no aniversário mais próximo (age nearest birthday).

    Anos completos; se já passaram 6 meses ou mais desde o último aniversário,
    conta-se mais um ano.
    """
    hoje = referencia or date.today()
    anos = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        anos -= 1
    # aniversário passado (tratando 29/02 como 28/02 em anos não bissextos)
    try:
        ultimo = data_nascimento.replace(year=data_nascimento.year + anos)
    except ValueError:
        ultimo = data_nascimento.replace(year=data_nascimento.year + anos, day=28)
    try:
        proximo = ultimo.replace(year=ultimo.year + 1)
    except ValueError:
        proximo = ultimo.replace(year=ultimo.year + 1, day=28)
    if (hoje - ultimo) >= (proximo - hoje):
        anos += 1
    return anos


def obter_taxa(tipo_mutuario: str, idade: int, prazo: int) -> Decimal:
    tipo = normalizar_tipo_mutuario(tipo_mutuario)
    if tipo not in TARIFA:
        raise TarifaIndisponivel(f"tipo_mutuario inválido. Use um de: {', '.join(TIPOS_MUTUARIO)}.")
    if not (IDADE_MIN <= idade <= IDADE_MAX):
        raise TarifaIndisponivel(f"Idade {idade} fora da tarifa ({IDADE_MIN}–{IDADE_MAX} anos).")
    if not (PRAZO_MIN <= prazo <= PRAZO_MAX):
        raise TarifaIndisponivel(f"Prazo {prazo} fora da tarifa ({PRAZO_MIN}–{PRAZO_MAX} anos).")
    taxa = TARIFA[tipo].get(idade, {}).get(prazo)
    if taxa is None:
        raise TarifaIndisponivel(f"Não segurável: idade {idade} com prazo de {prazo} anos ({tipo}).")
    return Decimal(str(taxa))


def tabela_tarifa(tipo_mutuario: str | None = None) -> dict:
    """Tarifa completa, pronta a renderizar como tabela.

    Sem ``tipo_mutuario`` devolve os três perfis. As combinações idade x prazo
    não seguráveis ("A" na tabela de origem) vêm a ``null``, para a grelha
    ficar rectangular.
    """
    if tipo_mutuario:
        tipo = normalizar_tipo_mutuario(tipo_mutuario)
        if tipo not in TARIFA:
            raise TarifaIndisponivel(
                f"tipo_mutuario inválido. Use um de: {', '.join(TIPOS_MUTUARIO)}."
            )
        tipos = [tipo]
    else:
        tipos = list(TIPOS_MUTUARIO)

    prazos = list(range(PRAZO_MIN, PRAZO_MAX + 1))
    linhas = [
        {
            "tipo_mutuario": t,
            "idade": idade,
            "taxas": {str(pz): TARIFA[t].get(idade, {}).get(pz) for pz in prazos},
        }
        for t in tipos
        for idade in range(IDADE_MIN, IDADE_MAX + 1)
    ]
    return {
        "tipos_mutuario": tipos,
        "idade_min": IDADE_MIN,
        "idade_max": IDADE_MAX,
        "prazos": prazos,
        "tarifas": linhas,
    }


def _arredondar(valor: Decimal) -> float:
    return float(valor.quantize(_CENT, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class ResultadoSimulacao:
    montante_emprestimo: float
    premio_total: float
    premio_simples: float
    sobre_taxa: float
    selo: float
    comissao_bci: float
    # informação auxiliar
    idade: int
    taxa: float
    agravamento: float

    def resposta(self) -> dict:
        return {
            "montante_emprestimo": self.montante_emprestimo,
            "premio_total": self.premio_total,
            "premio_simples": self.premio_simples,
            "sobre_taxa": self.sobre_taxa,
            "selo": self.selo,
            "comissao_bci": self.comissao_bci,
            "taxa": self.taxa,
        }


def simular(
    montante_emprestimo: Decimal,
    data_nascimento: date,
    prazo_emprestimo: int,
    tipo_mutuario: str,
    referencia: date | None = None,
) -> ResultadoSimulacao:
    idade = idade_aniversario_mais_proximo(data_nascimento, referencia)
    taxa = obter_taxa(tipo_mutuario, idade, prazo_emprestimo)
    agr = agravamento()

    # A taxa da tarifa dá o prémio TOTAL; o simples sai por divisão.
    premio_total_bruto = montante_emprestimo * taxa / Decimal(1000) * (Decimal(1) + agr)
    premio_simples = (premio_total_bruto / FACTOR_ENCARGOS).quantize(_CENT, rounding=ROUND_HALF_UP)
    sobre_taxa = (premio_simples * SOBRE_TAXA_PCT).quantize(_CENT, rounding=ROUND_HALF_UP)
    selo = (premio_simples * SELO_PCT).quantize(_CENT, rounding=ROUND_HALF_UP)
    comissao = (premio_simples * COMISSAO_BCI_PCT).quantize(_CENT, rounding=ROUND_HALF_UP)
    total = premio_simples + sobre_taxa + selo

    return ResultadoSimulacao(
        montante_emprestimo=float(montante_emprestimo),
        premio_total=_arredondar(total),
        premio_simples=_arredondar(premio_simples),
        sobre_taxa=_arredondar(sobre_taxa),
        selo=_arredondar(selo),
        comissao_bci=_arredondar(comissao),
        idade=idade,
        taxa=float(taxa),
        agravamento=float(agr),
    )
