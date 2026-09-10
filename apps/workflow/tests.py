import json
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from django.test import SimpleTestCase, override_settings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .errors import InvalidChartSpecError, UnapprovedDataError
from .graph import build_graph
from .context import build_analysis_prompt, build_analysis_summary, build_chart_prompt
from .llm import invoke_text
from .nodes.analyze import analyze_confirmed_dataset, analyze_data
from .nodes.chart import (
    generate_chart_spec,
    plan_chart,
    render_chart,
    validate_chart_spec,
)


class ApprovalGuardTests(SimpleTestCase):
    @override_settings(LLM_MAX_DATA_ROWS=10)
    @patch("apps.workflow.nodes.analyze.analyze_confirmed_dataset")
    def test_analysis_cannot_run_when_pending(self, mocked_analysis):
        with self.assertRaises(UnapprovedDataError):
            analyze_data({"confirmation_status": "pending"})
        mocked_analysis.assert_not_called()

    @override_settings(LLM_MAX_DATA_ROWS=10)
    @patch("apps.workflow.nodes.analyze.analyze_confirmed_dataset")
    def test_analysis_cannot_run_when_rejected(self, mocked_analysis):
        with self.assertRaises(UnapprovedDataError):
            analyze_data({"confirmation_status": "rejected"})
        mocked_analysis.assert_not_called()

    def test_invalid_chart_column_is_rejected(self):
        with self.assertRaises(InvalidChartSpecError):
            validate_chart_spec(
                {
                    "chart_type": "line",
                    "x": "DataDate",
                    "y": ["NotAColumn"],
                    "title": "Invalid",
                },
                ["DataDate", "CPI"],
            )

    @patch("apps.workflow.nodes.chart.plan_chart")
    def test_chart_planner_cannot_receive_pending_data(self, mocked_planner):
        with self.assertRaises(UnapprovedDataError):
            generate_chart_spec({"confirmation_status": "pending"})
        mocked_planner.assert_not_called()

    @patch("apps.workflow.nodes.chart.plan_chart")
    def test_chart_planner_cannot_receive_rejected_data(self, mocked_planner):
        with self.assertRaises(UnapprovedDataError):
            generate_chart_spec({"confirmation_status": "rejected"})
        mocked_planner.assert_not_called()

    def test_chart_with_reference_line_renders(self):
        result = render_chart(
            {
                "confirmation_status": "approved",
                "columns": ["DataDate", "EV"],
                "rows": [
                    {"DataDate": "2026-01-01", "EV": 100.0},
                    {"DataDate": "2026-02-01", "EV": 120.0},
                ],
                "chart_spec": {
                    "chart_type": "line",
                    "x": "DataDate",
                    "y": ["EV"],
                    "group_by": None,
                    "title": "Earned Value Trend",
                    "x_label": "DataDate",
                    "y_label": "EV",
                    "reference_lines": [1.0],
                },
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["chart_payload"]["layout"]["shapes"]), 1)

    @patch("apps.workflow.nodes.analyze.build_analysis_prompt")
    def test_analysis_prompt_cannot_be_built_before_approval(self, mocked_builder):
        with self.assertRaises(UnapprovedDataError):
            analyze_confirmed_dataset({"confirmation_status": "pending"})
        mocked_builder.assert_not_called()

    @patch("apps.workflow.nodes.chart.build_chart_prompt")
    def test_chart_prompt_cannot_be_built_before_approval(self, mocked_builder):
        with self.assertRaises(UnapprovedDataError):
            plan_chart({"confirmation_status": "rejected"})
        mocked_builder.assert_not_called()


class DynamicPromptContextTests(SimpleTestCase):
    def test_chart_prompt_contains_metadata_not_row_values(self):
        frame = pd.DataFrame(
            [
                {"ProjectCode": "PROJECT_SECRET_A", "CPI": 0.8},
                {"ProjectCode": "PROJECT_SECRET_B", "CPI": 1.1},
            ]
        )
        prompt = build_chart_prompt("وضعیت CPI پروژه‌ها", frame)
        context = json.loads(prompt.split("\n", 1)[1])

        self.assertNotIn("PROJECT_SECRET_A", prompt)
        self.assertNotIn("PROJECT_SECRET_B", prompt)
        self.assertEqual(
            set(context["available_approved_result_columns"]),
            {"ProjectCode", "CPI"},
        )
        self.assertEqual(
            context["available_approved_result_columns"]["CPI"]["role"],
            "measure",
        )
        self.assertEqual(set(context["relevant_evms_glossary"]), {"CPI"})

    def test_unused_schema_and_glossary_entries_are_excluded(self):
        frame = pd.DataFrame([{"ProjectCode": "A", "CPI": 0.9}])
        prompt = build_chart_prompt("CPI", frame)
        context = json.loads(prompt.split("\n", 1)[1])

        self.assertNotIn("SPI", context["available_approved_result_columns"])
        self.assertNotIn("SPI", context["relevant_evms_glossary"])

    def test_analysis_summary_is_deterministic_and_data_derived(self):
        frame = pd.DataFrame(
            [
                {"ProjectCode": "A", "DataDate": "2026-01-01", "CPI": 0.8, "SPI": 1.1, "CV": -10, "SV": 5, "VAC": -3},
                {"ProjectCode": "A", "DataDate": "2026-02-01", "CPI": 0.9, "SPI": 0.95, "CV": -5, "SV": -2, "VAC": 1},
                {"ProjectCode": "B", "DataDate": "2026-01-01", "CPI": 1.2, "SPI": 0.8, "CV": 5, "SV": -1, "VAC": -2},
                {"ProjectCode": "B", "DataDate": "2026-02-01", "CPI": 1.1, "SPI": 1.05, "CV": 3, "SV": 2, "VAC": 4},
            ]
        )
        first = build_analysis_summary(frame)
        second = build_analysis_summary(frame.copy())

        self.assertEqual(first, second)
        self.assertEqual(first["row_count"], 4)
        self.assertEqual(first["project_count"], 2)
        self.assertEqual(first["numeric_measures"]["CPI"]["average"], 1.0)
        self.assertEqual(first["performance_issue_counts"]["CPI_below_1_count"], 2)
        self.assertEqual(first["performance_issue_counts"]["negative_VAC_count"], 2)
        self.assertEqual(first["reporting_period"]["latest"], "2026-02-01T00:00:00")

    def test_analysis_prompt_excludes_non_summary_row_values(self):
        frame = pd.DataFrame(
            [
                {"ProjectCode": "A", "CPI": 0.8, "SensitiveNote": f"RAW_SECRET_{index}"}
                for index in range(20)
            ]
        )
        prompt = build_analysis_prompt("وضعیت پروژه", frame)

        self.assertNotIn("RAW_SECRET_0", prompt)
        self.assertNotIn("RAW_SECRET_19", prompt)
        self.assertIn('"row_count": 20', prompt)

    @patch("apps.workflow.nodes.chart.invoke_json")
    def test_chart_planner_sends_metadata_instead_of_rows(self, mocked_invoke):
        mocked_invoke.return_value = {
            "chart_type": "bar",
            "x": "ProjectCode",
            "y": ["CPI"],
            "group_by": None,
            "title": "CPI",
            "x_label": None,
            "y_label": None,
            "reference_lines": [1.0],
        }
        result = plan_chart(
            {
                "confirmation_status": "approved",
                "user_prompt": "CPI projects",
                "columns": ["ProjectCode", "CPI"],
                "rows": [{"ProjectCode": "DO_NOT_SEND", "CPI": 0.8}],
            }
        )
        sent_prompt = mocked_invoke.call_args.args[1]

        self.assertEqual(result["chart_type"], "bar")
        self.assertNotIn("DO_NOT_SEND", sent_prompt)
        self.assertNotIn("approved_rows_sample", sent_prompt)
        self.assertIn("available_approved_result_columns", sent_prompt)
        self.assertEqual(mocked_invoke.call_args.kwargs["log_prefix"], "CHART")


class PromptLoggingTests(SimpleTestCase):
    @override_settings(
        LLM_API_KEY="API_KEY_SHOULD_NOT_LOG",
        EVMS_DB_PASSWORD="DB_PASSWORD_SHOULD_NOT_LOG",
    )
    @patch("apps.workflow.llm.get_chat_model")
    def test_prompts_and_raw_responses_are_logged_without_secrets(self, mocked_model):
        mocked_model.return_value = SimpleNamespace(
            invoke=lambda messages: SimpleNamespace(content="raw model response")
        )
        with self.assertLogs("apps.workflow.llm", level="INFO") as captured:
            for prefix in ("SQL_PLANNER", "ANALYSIS", "CHART"):
                invoke_text("exact system prompt", "exact user prompt", log_prefix=prefix)

        logs = "\n".join(captured.output)
        for prefix in ("SQL_PLANNER", "ANALYSIS", "CHART"):
            self.assertIn(f"{prefix}_SYSTEM_PROMPT", logs)
            self.assertIn(f"{prefix}_USER_PROMPT", logs)
            self.assertIn(f"{prefix}_RESPONSE", logs)
        self.assertIn("raw model response", logs)
        self.assertNotIn("API_KEY_SHOULD_NOT_LOG", logs)
        self.assertNotIn("DB_PASSWORD_SHOULD_NOT_LOG", logs)


class LangGraphResumeTests(SimpleTestCase):
    def make_graph(self, calls):
        def classify(state):
            calls.append("classify")
            return {"intent": "trend_analysis"}

        def generate(state):
            calls.append("generate")
            return {"generated_sql": "SELECT safe"}

        def execute(state):
            calls.append("execute")
            return {
                "columns": ["DataDate", "CPI"],
                "rows": [{"DataDate": "2026-01-01", "CPI": 0.91}],
                "row_count": 1,
                "confirmation_status": "pending",
                "status": "waiting_for_confirmation",
            }

        def analyze(state):
            self.assertEqual(state["confirmation_status"], "approved")
            calls.append("analyze")
            return {"analysis": "grounded"}

        def chart_spec(state):
            calls.append("chart_spec")
            return {"chart_spec": {"chart_type": "line"}}

        def render(state):
            calls.append("render")
            return {"chart_payload": {"data": []}, "status": "completed"}

        return build_graph(
            InMemorySaver(),
            {
                "classify_intent": classify,
                "generate_sql": generate,
                "validate_and_execute_sql": execute,
                "analyze_data": analyze,
                "generate_chart_spec": chart_spec,
                "render_chart": render,
            },
        )

    def test_approved_data_resumes_workflow(self):
        calls = []
        graph = self.make_graph(calls)
        config = {"configurable": {"thread_id": "approved-run"}}
        first = graph.invoke(
            {"run_id": "r1", "thread_id": "t1", "user_prompt": "trend"},
            config=config,
        )
        self.assertIn("__interrupt__", first)
        self.assertNotIn("analyze", calls)

        result = graph.invoke(Command(resume={"action": "approved"}), config=config)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(calls[-3:], ["analyze", "chart_spec", "render"])

    def test_rejected_data_finishes_without_analysis(self):
        calls = []
        graph = self.make_graph(calls)
        config = {"configurable": {"thread_id": "rejected-run"}}
        graph.invoke(
            {"run_id": "r2", "thread_id": "t1", "user_prompt": "trend"},
            config=config,
        )
        result = graph.invoke(Command(resume={"action": "rejected"}), config=config)
        self.assertEqual(result["confirmation_status"], "rejected")
        self.assertNotIn("analyze", calls)
