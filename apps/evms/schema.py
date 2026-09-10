from __future__ import annotations

import json


# Replace or extend this controlled semantic view definition to match the
# organization's reporting layer. Raw transactional tables must not be added.
EVMS_SCHEMA: dict[str, dict[str, object]] = {
    "dbo.vw_EVMS_Project_Monthly": {
        "description": "Monthly project EVMS performance",
        "columns": {

            "ProjectCode": {
                "description": "Project identifier",
                "type": "string",
                "role": "dimension",
            },

            "ProjectName": {
                "description": "Project name",
                "type": "string",
                "role": "dimension",
            },

            "DataDate": {
                "description": "Reporting date",
                "type": "date",
                "role": "time",
            },

            "PV": {
                "description": "Planned Value",
                "type": "number",
                "role": "measure",
            },

            "EV": {
                "description": "Earned Value",
                "type": "number",
                "role": "measure",
            },

            "AC": {
                "description": "Actual Cost",
                "type": "number",
                "role": "measure",
            },

            "BAC": {
                "description": "Budget at Completion",
                "type": "number",
                "role": "measure",
            },

            "CV": {
                "description": "Cost Variance",
                "type": "number",
                "role": "measure",
            },

            "SV": {
                "description": "Schedule Variance",
                "type": "number",
                "role": "measure",
            },

            "CPI": {
                "description": "Cost Performance Index",
                "type": "number",
                "role": "measure",
            },

            "SPI": {
                "description": "Schedule Performance Index",
                "type": "number",
                "role": "measure",
            },

            "EAC": {
                "description": "Estimate at Completion",
                "type": "number",
                "role": "measure",
            },

            "ETC": {
                "description": "Estimate to Complete",
                "type": "number",
                "role": "measure",
            },

            "VAC": {
                "description": "Variance at Completion",
                "type": "number",
                "role": "measure",
            },
        },
    }
}


def allowed_relations() -> set[str]:
    return {name.casefold() for name in EVMS_SCHEMA}


def semantic_schema_text() -> str:
    """Return deterministic JSON suitable for the SQL-planning prompt."""

    return json.dumps(EVMS_SCHEMA, ensure_ascii=False, indent=2)
