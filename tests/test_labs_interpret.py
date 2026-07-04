# tests/test_labs_interpret.py
from r6.labs.interpret import LOINC_RANGES, REFERENCES


def test_every_range_has_a_nonempty_source():
    # Principle 4: no un-sourced range may ship.
    for loinc, entry in LOINC_RANGES.items():
        assert entry.get("source"), f"{loinc} ({entry.get('name')}) missing source"
        assert entry["source"] in REFERENCES, f"{loinc} source not in REFERENCES"


def test_core_analytes_present():
    for loinc in ("2823-3", "2951-2", "2345-7", "4548-4", "718-7", "777-3"):
        assert loinc in LOINC_RANGES


from r6.labs.interpret import interpret_observation


def _obs(loinc, value, unit="mmol/L", ref=None):
    o = {"resourceType": "Observation", "status": "final",
         "code": {"coding": [{"system": "http://loinc.org", "code": loinc}]},
         "valueQuantity": {"value": value, "unit": unit}}
    if ref is not None:
        o["referenceRange"] = ref
    return o


def test_normal_potassium_is_N():
    r = interpret_observation(_obs("2823-3", 4.2))
    assert r["flag"] == "N" and r["critical"] is False
    assert r["range_source"] == "table" and r["analyte"] == "Potassium"


def test_high_potassium_is_H():
    assert interpret_observation(_obs("2823-3", 5.6))["flag"] == "H"


def test_critical_high_potassium_is_HH():
    r = interpret_observation(_obs("2823-3", 7.0))
    assert r["flag"] == "HH" and r["critical"] is True


def test_low_and_critical_low():
    assert interpret_observation(_obs("2823-3", 3.0))["flag"] == "L"
    assert interpret_observation(_obs("2823-3", 2.0))["flag"] == "LL"


def test_resource_range_wins_over_table():
    # Value 5.6 is table-high, but the lab's own range makes it normal.
    ref = [{"low": {"value": 3.0}, "high": {"value": 6.0}}]
    r = interpret_observation(_obs("2823-3", 5.6, ref=ref))
    assert r["flag"] == "N" and r["range_source"] == "resource"


def test_unit_mismatch_is_indeterminate():
    r = interpret_observation(_obs("2823-3", 4.2, unit="mg/dL"))
    assert r["flag"] is None and r["range_source"] == "none"
    assert "indeterminate" in r["note"].lower()


def test_unknown_loinc_is_indeterminate():
    r = interpret_observation(_obs("9999-9", 4.2))
    assert r["flag"] is None and r["range_source"] == "none"


def test_missing_value_is_indeterminate():
    o = {"resourceType": "Observation",
         "code": {"coding": [{"system": "http://loinc.org", "code": "2823-3"}]}}
    assert interpret_observation(o)["flag"] is None


def test_sex_specific_hemoglobin():
    female = {"resourceType": "Patient", "gender": "female"}
    male = {"resourceType": "Patient", "gender": "male"}
    # 12.5 g/dL: normal for female (>=12.0), low for male (<13.5)
    assert interpret_observation(_obs("718-7", 12.5, unit="g/dL"), female)["flag"] == "N"
    assert interpret_observation(_obs("718-7", 12.5, unit="g/dL"), male)["flag"] == "L"


def test_component_only_observation_skipped():
    o = {"resourceType": "Observation",
         "code": {"coding": [{"system": "http://loinc.org", "code": "55284-4"}]},
         "component": [{"code": {"coding": [{"code": "8480-6"}]},
                        "valueQuantity": {"value": 138, "unit": "mmHg"}}]}
    assert interpret_observation(o)["range_source"] == "none"
