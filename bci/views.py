from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views import View
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

APP_DIR = Path(__file__).resolve().parent

from .models import ProcessoOffline
from .serializers import SimulacaoRequestSerializer
from .services import TarifaIndisponivel, simular, tabela_tarifa


class SimularProcessoView(APIView):
    """POST /api/bci/processes/quotation

    Simula o prémio do seguro de Capital Decrescente (Consumo) para um
    empréstimo BCI. Não persiste nada.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = SimulacaoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        try:
            resultado = simular(
                montante_emprestimo=dados["montante_emprestimo"],
                data_nascimento=dados["data_nascimento"],
                prazo_emprestimo=dados["prazo_emprestimo"],
                tipo_mutuario=dados["tipo_mutuario"],
            )
        except TarifaIndisponivel as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado.resposta(), status=status.HTTP_200_OK)


class TarifaView(APIView):
    """GET /api/bci/processes/tarif?tipo_mutuario=TRABALHADORES

    Devolve a tabela de tarifas (taxas em ‰) por idade e prazo. Sem o
    parâmetro ``tipo_mutuario`` devolve os três perfis.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            tabela = tabela_tarifa(request.query_params.get("tipo_mutuario"))
        except TarifaIndisponivel as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(tabela, status=status.HTTP_200_OK)


# Resposta fixa do stub. A decisão real é do RPA INSIS, a jusante.
MENSAGEM_OFFLINE = "Cotação aprovada. RPA INSIS iniciado para emissão de apólice."
ESTADO_OFFLINE = "aprovado"


class SimularOfflineView(APIView):
    """POST /api/bci/processes/simulate-offline/

    Stub. Não valida o risco, não calcula prémio, não decide nada: guarda o
    pedido e responde sempre aprovado. Quem emite a apólice é o RPA INSIS.

    A resposta é constante, tirando ``id_bci``, que é devolvido tal como veio
    no pedido.

    Qualquer corpo JSON é aceite — o canal envia dados pessoais, morada,
    contactos, dados bancários e questionário clínico, e nada disso é validado
    aqui. Fica tudo em ``ProcessoOffline.dados``.

    Quando vem ``transaction_ref``, é idempotente: repetir não duplica.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        dados = request.data if hasattr(request.data, "get") else {}
        id_bci = str(dados.get("id_bci") or "")
        referencia = str(dados.get("transaction_ref") or "").strip() or None

        processo = None
        if referencia is not None:
            processo = ProcessoOffline.objects.filter(transaction_ref=referencia).first()

        if processo is None:
            ProcessoOffline.objects.create(
                transaction_ref=referencia,
                id_bci=id_bci[:64],
                premio_pago=_decimal_ou_none(dados.get("premio_pago")),
                comissao=_decimal_ou_none(dados.get("comissao")),
                certificado_apolice=str(dados.get("certificado_apolice") or ""),
                dados=_payload_bruto(dados),
                registado_por=request.user if request.user.is_authenticated else None,
            )

        return Response(
            {
                "message": MENSAGEM_OFFLINE,
                "id_bci": id_bci,
                "estado_processo": ESTADO_OFFLINE,
            },
            status=status.HTTP_200_OK,
        )


def _decimal_ou_none(valor):
    """Guarda o número se for um número; um valor estranho não faz falhar o stub."""
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _payload_bruto(dados) -> dict:
    """O pedido tal como veio, menos o certificado (já guardado à parte)."""
    if not hasattr(dados, "items"):
        return {}
    return {k: v for k, v in dados.items() if k != "certificado_apolice"}


def _documentacao_activa() -> bool:
    """A documentação pode ser desligada em produção com BCI_DOCS=0."""
    return bool(getattr(settings, "BCI_DOCS", True))


class DocumentacaoView(View):
    """GET /api/bci/docs

    Referência dos endpoints, em HTML. Página auto-contida: sem CDN, sem
    JavaScript, para poder ser lida numa rede fechada.

    Aberta, sem token — de outro modo o browser não conseguia abri-la. Não
    expõe dados, só o contrato da API; quem não quiser publicá-la desliga com
    BCI_DOCS=0.
    """

    def get(self, request, *args, **kwargs):
        if not _documentacao_activa():
            raise Http404
        return HttpResponse(
            (APP_DIR / "docs.html").read_bytes(), content_type="text/html; charset=utf-8"
        )


class EspecificacaoView(View):
    """GET /api/bci/openapi.yaml

    A especificação OpenAPI 3.0, para importar no Postman ou gerar clientes.
    """

    def get(self, request, *args, **kwargs):
        if not _documentacao_activa():
            raise Http404
        return FileResponse(
            (APP_DIR / "openapi.yaml").open("rb"),
            content_type="application/yaml; charset=utf-8",
        )
