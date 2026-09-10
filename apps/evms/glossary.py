from collections.abc import Iterable


EVMS_GLOSSARY: dict[str, str] = {
    "PV": "Planned Value",
    "EV": "Earned Value",
    "AC": "Actual Cost",
    "BAC": "Budget at Completion",
    "CV": "Cost Variance = EV - AC",
    "SV": "Schedule Variance = EV - PV",
    "CPI": "Cost Performance Index = EV / AC",
    "SPI": "Schedule Performance Index = EV / PV",
    "EAC": "Estimate at Completion",
    "ETC": "Estimate to Complete",
    "VAC": "Variance at Completion = BAC - EAC",
}


def glossary_text() -> str:
    return "\n".join(f"{key}: {value}" for key, value in EVMS_GLOSSARY.items())


def get_relevant_glossary(columns: Iterable[str]) -> dict[str, str]:
    """Return glossary entries whose metric is an actual result column."""

    returned = {str(column).casefold() for column in columns}
    return {
        metric: meaning
        for metric, meaning in EVMS_GLOSSARY.items()
        if metric.casefold() in returned
    }
