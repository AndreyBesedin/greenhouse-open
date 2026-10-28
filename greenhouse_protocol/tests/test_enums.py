from greenhouse_protocol.enums import SourceType


def test_source_type_has_expected_members() -> None:
    assert {member.value for member in SourceType} == {
        "SIMULATION",
        "REAL_SENSORS",
        "EXTERNAL_API",
        "IMPORTED_DATA",
    }
