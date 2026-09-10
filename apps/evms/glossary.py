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
