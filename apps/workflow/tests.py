from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .errors import InvalidChartSpecError, UnapprovedDataError
from .graph import build_graph
from .nodes.analyze import analyze_data
from .nodes.chart import generate_chart_spec, validate_chart_spec


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
