from greenhouse_protocol.enums import ActionExecutorType, SourceType


def test_source_type_has_expected_members() -> None:
    assert {member.value for member in SourceType} == {
        "SIMULATION",
        "REAL_SENSORS",
        "EXTERNAL_API",
        "IMPORTED_DATA",
    }


def test_action_executor_type_has_expected_members() -> None:
    assert {member.value for member in ActionExecutorType} == {"SIMULATED_OPERATOR"}
