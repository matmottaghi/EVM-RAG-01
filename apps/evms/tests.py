from django.test import SimpleTestCase

from .sql_validator import SQLValidationError, validate_sql


class SQLValidatorTests(SimpleTestCase):
    safe_view = "dbo.vw_EVMS_Project_Monthly"

    def test_blocks_delete(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(f"DELETE FROM {self.safe_view}")

    def test_blocks_drop(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("DROP VIEW dbo.vw_EVMS_Project_Monthly")

    def test_allows_safe_select_and_applies_top(self):
        result = validate_sql(
            f"SELECT ProjectCode, CPI FROM {self.safe_view}",
            max_rows=125,
        )
        self.assertIn("SELECT TOP 125", result.sql.upper())
        self.assertEqual(result.row_limit, 125)

    def test_rejects_unknown_table(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("SELECT * FROM dbo.Users")

    def test_rejects_multiple_statements(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                f"SELECT * FROM {self.safe_view}; SELECT * FROM {self.safe_view}"
            )

    def test_preserves_a_smaller_top_limit(self):
        result = validate_sql(
            f"SELECT TOP (10) * FROM {self.safe_view}",
            max_rows=1000,
        )
        self.assertEqual(result.row_limit, 10)
        self.assertIn("TOP 10", result.sql.upper())

    def test_allows_cte_over_safe_view(self):
        result = validate_sql(
            "WITH metrics AS (SELECT ProjectCode, CPI "
            f"FROM {self.safe_view}) SELECT * FROM metrics"
        )
        self.assertEqual(result.tables, ("dbo.vw_EVMS_Project_Monthly",))

    def test_rejects_select_into(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                f"SELECT * INTO dbo.CopyOfData FROM {self.safe_view}"
            )

    def test_rejects_cross_database_reference(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                "SELECT * FROM OtherDatabase.dbo.vw_EVMS_Project_Monthly"
            )
