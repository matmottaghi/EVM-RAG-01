from django.urls import path

from .views import (
    ApproveView,
    ChartView,
    DatasetView,
    QueryView,
    RejectView,
    StatusView,
)


app_name = "chat"
urlpatterns = [
    path("chat/query/", QueryView.as_view(), name="query"),
    path("workflow/<uuid:run_id>/approve/", ApproveView.as_view(), name="approve"),
    path("workflow/<uuid:run_id>/reject/", RejectView.as_view(), name="reject"),
    path("workflow/<uuid:run_id>/status/", StatusView.as_view(), name="status"),
    path("workflow/<uuid:run_id>/dataset/", DatasetView.as_view(), name="dataset"),
    path("workflow/<uuid:run_id>/chart/", ChartView.as_view(), name="chart"),
]
