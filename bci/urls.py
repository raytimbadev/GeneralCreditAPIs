from django.urls import path

from .views import (
    DocumentacaoView,
    EspecificacaoView,
    SimularOfflineView,
    SimularProcessoView,
    TarifaView,
)

# Incluir no urls.py principal:
#   path("api/bci/", include("bci.urls")),
urlpatterns = [
    path("processes/quotation", SimularProcessoView.as_view(), name="bci-quotation"),
    path("processes/tarif", TarifaView.as_view(), name="bci-tarif"),
    # Venda fechada ao balcao (ver SimularOfflineView). Aceite com e sem
    # barra final: sem os dois, o APPEND_SLASH do Django responde 301 a um
    # POST e ha clientes que perdem o corpo do pedido no redireccionamento.
    path(
        "processes/simulate-offline/",
        SimularOfflineView.as_view(),
        name="bci-simulate-offline",
    ),
    path(
        "processes/simulate-offline",
        SimularOfflineView.as_view(),
        name="bci-simulate-offline-sem-barra",
    ),
    # Documentação, aberta (ver BCI_DOCS).
    path("docs", DocumentacaoView.as_view(), name="bci-docs"),
    path("openapi.yaml", EspecificacaoView.as_view(), name="bci-openapi"),
]
