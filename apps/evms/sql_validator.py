from __future__ import annotations

import re
from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from .schema import allowed_relations


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "EXEC",
    "EXECUTE",
    "MERGE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
}


class SQLValidationError(ValueError):
    """Generated SQL violated the deterministic read-only policy."""


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    tables: tuple[str, ...]
    row_limit: int


def _without_literals_and_comments(sql: str) -> str:
    value = re.sub(
        r"--[^\r\n]*",
        " ",
        sql
    )

    value = re.sub(
        r"/\*.*?\*/",
        " ",
        value,
        flags=re.DOTALL
    )

    return re.sub(
        r"N?'(?:''|[^'])*'",
        "''",
        value,
        flags=re.IGNORECASE
    )


def validate_sql(
    sql: str,
    *,
    max_rows: int = 1000,
    allowed_schemas: tuple[str, ...] = ("dbo",),
) -> ValidatedSQL:
    """Validate one SQL Server SELECT and enforce a server-side row ceiling."""

    if not isinstance(sql, str) or not sql.strip():
        raise SQLValidationError(
            "SQL query is empty."
        )

    max_rows = min(
        max(int(max_rows), 1),
        10_000
    )

    scrubbed = _without_literals_and_comments(sql)

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(
            rf"\b{keyword}\b",
            scrubbed,
            flags=re.IGNORECASE
        ):
            raise SQLValidationError(
                f"Forbidden SQL operation: {keyword}."
            )

    try:
        statements = [
            item
            for item in parse(
                sql,
                read="tsql"
            )
            if item
        ]

    except ParseError as exc:
        raise SQLValidationError(
            "SQL could not be parsed as SQL Server syntax."
        ) from exc

    if len(statements) != 1:
        raise SQLValidationError(
            "Exactly one SQL statement is allowed."
        )

    statement = statements[0]

    if (
        not isinstance(statement, exp.Query)
        or statement.find(exp.Select) is None
    ):
        raise SQLValidationError(
            "Only SELECT queries are allowed."
        )

    prohibited_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Merge,
        exp.Command,
        exp.Into,
    )

    if any(
        statement.find(node_type) is not None
        for node_type in prohibited_nodes
    ):
        raise SQLValidationError(
            "The query contains a non-read-only operation."
        )

    cte_names = {
        cte.alias_or_name.casefold()
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }

    allowlist = allowed_relations()

    schemas = {
        schema.casefold()
        for schema in allowed_schemas
    }

    referenced: set[str] = set()

    for table in statement.find_all(exp.Table):
        name = table.name

        if not name or name.casefold() in cte_names:
            continue

        schema = table.args.get("db")
        catalog = table.args.get("catalog")

        if catalog:
            raise SQLValidationError(
                "Cross-database queries are not allowed."
            )

        schema_name = (
            schema.name
            if schema
            else "dbo"
        )

        if schema_name.casefold() not in schemas:
            raise SQLValidationError(
                f"Schema is not allowed: {schema_name}."
            )

        full_name = (
            f"{schema_name}.{name}"
        ).casefold()

        if full_name not in allowlist:
            raise SQLValidationError(
                f"Unknown or disallowed table/view: "
                f"{schema_name}.{name}."
            )

        referenced.add(
            f"{schema_name}.{name}"
        )

    if not referenced:
        raise SQLValidationError(
            "The query must read from an approved EVMS view."
        )

    effective_limit = max_rows

    existing_limit = statement.args.get("limit")

    if (
        existing_limit
        and isinstance(
            existing_limit.expression,
            exp.Literal
        )
    ):
        try:
            effective_limit = min(
                max_rows,
                int(existing_limit.expression.this)
            )

        except (TypeError, ValueError):
            effective_limit = max_rows

    limited = statement.copy().limit(
        effective_limit
    )

    normalized = limited.sql(
        dialect="tsql",
        pretty=False
    )

    return ValidatedSQL(
        sql=normalized,
        tables=tuple(
            sorted(
                referenced,
                key=str.casefold
            )
        ),
        row_limit=effective_limit,
    )