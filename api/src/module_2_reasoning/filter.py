"""Step 1 — ClinicalFilter: rule-based extraction, no LLM."""

from __future__ import annotations

from .schemas import FilteredTestResult, FlaggedParameter


def _flag_row(row: dict) -> list[FlaggedParameter]:
    """
    Return a list of FlaggedParameter objects for a single row dict.
    A row may have 'value', or 'left'/'right', or neither.
    Returns empty list if the row is within all norms.
    """
    parameter = row.get("parameter", "")
    unit = row.get("unit")
    norm = row.get("norm")
    asym_pct = row.get("asymmetry_percent")
    asym_norm_max = row.get("asymmetry_norm_max")

    flagged: list[FlaggedParameter] = []

    # --- rows with a single 'value' ---
    if row.get("value") is not None:
        value = row["value"]

        if norm:
            norm_min, norm_max = norm[0], norm[-1]
            if value < norm_min:
                flagged.append(
                    FlaggedParameter(
                        parameter=parameter,
                        value=value,
                        unit=unit,
                        norm=norm,
                        flag_reason="below_norm",
                    )
                )
            elif value > norm_max:
                flagged.append(
                    FlaggedParameter(
                        parameter=parameter,
                        value=value,
                        unit=unit,
                        norm=norm,
                        flag_reason="above_norm",
                    )
                )
        else:
            # No norm — include as informational
            flagged.append(
                FlaggedParameter(
                    parameter=parameter,
                    value=value,
                    unit=unit,
                    flag_reason="no_norm",
                )
            )

    # --- rows with 'left' / 'right' (bilateral tests) ---
    elif "left" in row or "right" in row:
        left = row.get("left")
        right = row.get("right")

        # Check each side against norm independently
        if norm:
            norm_min, norm_max = norm[0], norm[-1]
            for side, side_val in (("left", left), ("right", right)):
                if side_val is None:
                    continue
                if side_val < norm_min:
                    flagged.append(
                        FlaggedParameter(
                            parameter=f"{parameter} ({side})",
                            value=side_val,
                            left=left if side == "left" else None,
                            right=right if side == "right" else None,
                            unit=unit,
                            norm=norm,
                            flag_reason="below_norm",
                        )
                    )
                elif side_val > norm_max:
                    flagged.append(
                        FlaggedParameter(
                            parameter=f"{parameter} ({side})",
                            value=side_val,
                            left=left if side == "left" else None,
                            right=right if side == "right" else None,
                            unit=unit,
                            norm=norm,
                            flag_reason="above_norm",
                        )
                    )

        # Check asymmetry regardless of norm
        if asym_pct is not None and asym_norm_max is not None:
            if asym_pct > asym_norm_max:
                # Only append if not already flagged for norm violation
                already_flagged_params = {f.parameter for f in flagged}
                base_param = parameter
                if base_param not in already_flagged_params:
                    flagged.append(
                        FlaggedParameter(
                            parameter=parameter,
                            left=left,
                            right=right,
                            unit=unit,
                            norm=norm,
                            asymmetry_percent=asym_pct,
                            asymmetry_norm_max=asym_norm_max,
                            flag_reason="asymmetry",
                        )
                    )
                else:
                    # Enrich existing entries with asymmetry info
                    for fp in flagged:
                        if fp.parameter.startswith(base_param):
                            fp.asymmetry_percent = asym_pct
                            fp.asymmetry_norm_max = asym_norm_max

        # If no norm and no asymmetry violation — include as no_norm
        if not flagged and not norm and (left is not None or right is not None):
            flagged.append(
                FlaggedParameter(
                    parameter=parameter,
                    left=left,
                    right=right,
                    unit=unit,
                    flag_reason="no_norm",
                )
            )

    return flagged


def filter_test_result(test_result: dict) -> FilteredTestResult:
    """Extract clinically significant rows from one test result dict."""
    test_name = test_result.get("test_name", "unknown")
    interpretation = test_result.get("interpretation")
    recommendations = test_result.get("recommendations")

    results = test_result.get("results", {})
    tables = results.get("tables", [])

    flagged_params: list[FlaggedParameter] = []
    has_norm_data = False

    for table in tables:
        for row in table.get("rows", []):
            if row.get("norm") or row.get("asymmetry_norm_max") is not None:
                has_norm_data = True
            flagged_params.extend(_flag_row(row))

    # For tests with no norm data at all — clear flagged_params but keep text
    if not has_norm_data:
        flagged_params = []

    return FilteredTestResult(
        test_name=test_name,
        flagged_params=flagged_params,
        interpretation_uk=interpretation,
        recommendations_uk=recommendations,
        has_norm_data=has_norm_data,
    )


def filter_patient_data(module1_json: dict) -> list[FilteredTestResult]:
    """Apply filter_test_result to every test_result in the Module 1 export."""
    return [filter_test_result(tr) for tr in module1_json.get("test_results", [])]
