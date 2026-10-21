import pytest

from module_2_reasoning.filter import filter_patient_data, filter_test_result


def result(*rows, **extra):
    return {
        "test_name": "Synthetic measurement",
        "results": {"tables": [{"rows": list(rows)}]},
        **extra,
    }


@pytest.mark.parametrize(
    "value,reason",
    [
        (9.99, "below_norm"),
        (10, None),
        (15, None),
        (20, None),
        (20.01, "above_norm"),
        (None, None),
    ],
)
def test_scalar_thresholds(value, reason):
    filtered = filter_test_result(
        result({"parameter": "ROM", "value": value, "norm": [10, 20]})
    )
    assert [p.flag_reason for p in filtered.flagged_params] == (
        [reason] if reason else []
    )


def test_bilateral_values_and_asymmetry_are_preserved():
    filtered = filter_test_result(
        result(
            {
                "parameter": "Strength",
                "left": 9,
                "right": 21,
                "norm": [10, 20],
                "asymmetry_percent": 30,
                "asymmetry_norm_max": 10,
            }
        )
    )
    assert [(p.parameter, p.flag_reason) for p in filtered.flagged_params] == [
        ("Strength (left)", "below_norm"),
        ("Strength (right)", "above_norm"),
        ("Strength", "asymmetry"),
    ]
    assert filtered.flagged_params[-1].asymmetry_percent == 30


@pytest.mark.parametrize("asymmetry,count", [(0, 0), (10, 0), (10.01, 1)])
def test_asymmetry_threshold_without_absolute_norm(asymmetry, count):
    filtered = filter_test_result(
        result(
            {
                "parameter": "Strength",
                "left": 20,
                "right": 21,
                "asymmetry_percent": asymmetry,
                "asymmetry_norm_max": 10,
            }
        )
    )
    assert filtered.has_norm_data
    # An in-range bilateral row without an absolute norm is informational.
    assert sum(p.flag_reason == "asymmetry" for p in filtered.flagged_params) == count


def test_zero_asymmetry_limit_is_a_valid_threshold():
    filtered = filter_test_result(
        result(
            {
                "parameter": "Strength",
                "left": 1,
                "right": 2,
                "asymmetry_percent": 1,
                "asymmetry_norm_max": 0,
            }
        )
    )
    assert filtered.flagged_params[0].flag_reason == "asymmetry"


def test_null_scalar_does_not_hide_present_bilateral_value():
    filtered = filter_test_result(
        result(
            {
                "parameter": "Strength",
                "value": None,
                "left": None,
                "right": 30,
                "norm": [10, 20],
            }
        )
    )
    assert [(p.parameter, p.value) for p in filtered.flagged_params] == [
        ("Strength (right)", 30)
    ]


def test_missing_measurements_do_not_invent_findings():
    filtered = filter_test_result(
        result(
            {"parameter": "Missing", "norm": [0, 10]},
            {"parameter": "Missing too", "left": None, "right": None},
        )
    )
    assert filtered.flagged_params == []


def test_text_only_result_keeps_interpretation_without_numeric_flags():
    filtered = filter_test_result(
        result(
            {"parameter": "Info", "value": 2},
            interpretation="Synthetic observation",
            recommendations="Synthetic recommendation",
        )
    )
    assert not filtered.has_norm_data
    assert not filtered.flagged_params
    assert filtered.interpretation_uk == "Synthetic observation"
    assert filtered.recommendations_uk == "Synthetic recommendation"


def test_mixed_table_keeps_information_rows_and_units():
    filtered = filter_test_result(
        result(
            {"parameter": "ROM", "value": 11, "norm": [0, 10], "unit": "deg"},
            {"parameter": "Other", "value": 2},
        )
    )
    assert [p.flag_reason for p in filtered.flagged_params] == ["above_norm", "no_norm"]
    assert filtered.flagged_params[0].unit == "deg"


def test_empty_patient_and_tables():
    assert filter_patient_data({}) == []
    assert filter_patient_data({"test_results": []}) == []
    assert filter_test_result({"test_name": "Empty"}).flagged_params == []
    assert len(filter_patient_data({"test_results": [result(), result()]})) == 2
