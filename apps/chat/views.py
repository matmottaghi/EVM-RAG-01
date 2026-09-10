from __future__ import annotations

import math
from typing import Any

from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workflow.errors import CheckpointMissingError, InvalidWorkflowTransition

from .models import ChatMessage, ChatThread, DatasetSnapshot, WorkflowRun
from .serializers import QuerySerializer, RejectSerializer
from .services import approve_workflow, public_error, reject_workflow, start_workflow


@ensure_csrf_cookie
def dashboard(request):
    return render(request, "dashboard.html")


def dataset_payload(snapshot: DatasetSnapshot, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    page_size = min(max(page_size, 1), 200)
    total_pages = max(1, math.ceil(snapshot.row_count / page_size))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * page_size
    return {
        "columns": snapshot.columns_json,
        "rows": snapshot.rows_json[start : start + page_size],
        "row_count": snapshot.row_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "approved": snapshot.approved,
    }


def run_payload(run: WorkflowRun, *, include_dataset: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": str(run.id),
        "thread_id": str(run.thread_id),
        "status": run.status,
        "confirmation_status": run.confirmation_status,
        "analysis": run.analysis or None,
        "chart": run.chart_payload,
        "error": run.error_message or None,
    }
    if include_dataset and hasattr(run, "dataset_snapshot"):
        payload["dataset"] = dataset_payload(run.dataset_snapshot)
    return payload


def failed_response(run: WorkflowRun) -> Response:
    code = "workflow_error"
    http_status = status.HTTP_502_BAD_GATEWAY
    if "تنظیمات" in run.error_message:
        code, http_status = "configuration_error", status.HTTP_503_SERVICE_UNAVAILABLE
    elif "فقط‌خواندنی" in run.error_message or "داده‌ای برنگرداند" in run.error_message:
        code, http_status = "invalid_query_result", status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = run_payload(run, include_dataset=True)
    payload["code"] = code
    return Response(payload, status=http_status)


class QueryView(APIView):
    def post(self, request: Request) -> Response:
        serializer = QuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread_id = serializer.validated_data.get("thread_id")
        if thread_id:
            thread = get_object_or_404(ChatThread, pk=thread_id)
        else:
            thread = ChatThread.objects.create()

        pending = thread.workflow_runs.filter(
            status=WorkflowRun.Status.WAITING,
            confirmation_status=WorkflowRun.Confirmation.PENDING,
        ).first()
        if pending:
            return Response(
                {
                    "code": "pending_confirmation",
                    "error": "ابتدا دادهٔ پرس‌وجوی قبلی را تأیید یا رد کنید.",
                    "run_id": str(pending.id),
                    "thread_id": str(thread.id),
                },
                status=status.HTTP_409_CONFLICT,
            )

        previous = thread.workflow_runs.filter(
            status=WorkflowRun.Status.REJECTED
        ).first()
        correction_context = None
        if previous:
            correction_context = f"Previous question: {previous.user_prompt}"

        message = serializer.validated_data["message"]
        ChatMessage.objects.create(
            thread=thread,
            role=ChatMessage.Role.USER,
            content=message,
        )
        thread.save(update_fields=["updated_at"])
        run = WorkflowRun.objects.create(thread=thread, user_prompt=message)
        run = start_workflow(run, correction_context=correction_context)
        if run.status == WorkflowRun.Status.FAILED:
            return failed_response(run)
        return Response(run_payload(run, include_dataset=True), status=status.HTTP_201_CREATED)


class ApproveView(APIView):
    def post(self, request: Request, run_id) -> Response:
        run = get_object_or_404(WorkflowRun, pk=run_id)
        try:
            run = approve_workflow(run)
        except (CheckpointMissingError, InvalidWorkflowTransition) as exc:
            code, message = public_error(exc)
            return Response(
                {"code": code, "error": message},
                status=status.HTTP_409_CONFLICT,
            )
        if run.status == WorkflowRun.Status.FAILED:
            return failed_response(run)
        return Response(run_payload(run))


class RejectView(APIView):
    def post(self, request: Request, run_id) -> Response:
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = get_object_or_404(WorkflowRun, pk=run_id)
        try:
            run = reject_workflow(run, reason=serializer.validated_data["reason"])
        except (CheckpointMissingError, InvalidWorkflowTransition) as exc:
            code, message = public_error(exc)
            return Response(
                {"code": code, "error": message},
                status=status.HTTP_409_CONFLICT,
            )
        if run.status == WorkflowRun.Status.FAILED:
            return failed_response(run)
        return Response(run_payload(run))


class StatusView(APIView):
    def get(self, request: Request, run_id) -> Response:
        run = get_object_or_404(WorkflowRun, pk=run_id)
        return Response(run_payload(run))


class DatasetView(APIView):
    def get(self, request: Request, run_id) -> Response:
        snapshot = get_object_or_404(DatasetSnapshot, workflow_run_id=run_id)
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 100))
        except (TypeError, ValueError):
            return Response(
                {"error": "page و page_size باید عدد صحیح باشند."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(dataset_payload(snapshot, page=page, page_size=page_size))


class ChartView(APIView):
    def get(self, request: Request, run_id) -> Response:
        run = get_object_or_404(WorkflowRun, pk=run_id)
        if run.confirmation_status != WorkflowRun.Confirmation.APPROVED:
            return Response(
                {"error": "نمودار فقط برای داده تأییدشده در دسترس است."},
                status=status.HTTP_409_CONFLICT,
            )
        if not run.chart_payload:
            return Response(
                {"error": "نمودار هنوز تولید نشده است."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"run_id": str(run.id), "chart": run.chart_payload})
