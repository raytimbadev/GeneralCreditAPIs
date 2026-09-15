from django.urls import include, path

urlpatterns = [
    path("api/bci/", include("bci.urls")),
]
