from django.contrib import admin
from django.urls import include, path

from apps.chat.views import dashboard


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("api/", include("apps.chat.urls")),
    path("admin/", admin.site.urls),
]
