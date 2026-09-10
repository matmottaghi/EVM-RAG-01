from __future__ import annotations

import json


# Replace or extend this controlled semantic view definition to match the
# organization's reporting layer. Raw transactional tables must not be added.
EVMS_SCHEMA: dict[str, dict[str, object]] = {
    "vw_EVMS_Project_Monthly": {
        "description": "Monthly project EVMS performance",
        "columns": {
            "ProjectCode": "Project identifier",
            "ProjectName": "Project name",
            "DataDate": "Reporting date",
            "PV": "Planned Value",
            "EV": "Earned Value",
            "AC": "Actual Cost",
            "BAC": "Budget at Completion",
            "CPI": "Cost Performance Index",
            "SPI": "Schedule Performance Index",
            "EAC": "Estimate at Completion",
            "ETC": "Estimate to Complete",
            "VAC": "Variance at Completion",
        },
    }
}


def allowed_relations() -> set[str]:
    return {name.casefold() for name in EVMS_SCHEMA}


def semantic_schema_text() -> str:
    """Return deterministic JSON suitable for the SQL-planning prompt."""

    return json.dumps(EVMS_SCHEMA, ensure_ascii=False, indent=2)
