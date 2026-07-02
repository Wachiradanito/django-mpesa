from django.urls import include, path

urlpatterns = [
    path("mpesa/", include("django_mpesa.urls")),
]
