from typing import Any

from scripts.check_pr_risk import (
    KEPT_DATA_FOLDERS,
    ROOT,
    SENSITIVE_FILES,
    _risk_reasons,
    acknowledged,
    approved,
)

HEAD = "b" * 40
EARLIER = "a" * 40


def _review(
    state: str, commit: str = HEAD, user: str = "maintainer", association: str = "OWNER"
) -> dict[str, Any]:
    return {"user": user, "state": state, "commit_id": commit, "author_association": association}


def test_every_sensitive_path_exists() -> None:
    """A sensitive file that moves must take its entry with it. Otherwise the
    gate silently stops flagging changes to it."""
    missing = sorted(path for path in SENSITIVE_FILES if not (ROOT / path).exists())
    assert not missing, f"sensitive paths that no longer exist: {missing}"


def test_every_kept_data_folder_exists() -> None:
    assert [folder for folder in KEPT_DATA_FOLDERS if not (ROOT / folder).is_dir()] == []


def test_a_change_to_the_gate_or_another_script_asks_for_review() -> None:
    for path in ("scripts/check_pr_risk.py", "scripts/dependabot_auto_merge.py"):
        reasons = _risk_reasons([path], 3)

        assert any("sensitive repository boundary" in reason for reason in reasons)


def test_a_change_where_truth_or_uploads_pass_asks_for_review() -> None:
    reasons = _risk_reasons(["greenhouse_sim/greenhouse_sim/services/sensors.py"], 3)

    assert any("sensitive repository boundary" in reason for reason in reasons)


def test_kept_data_asks_for_review_and_is_not_counted_in_lines() -> None:
    golden = "greenhouse_sim/tests/fixtures/reference_replay.json"
    opening = "greenhouse_sim/greenhouse_sim/scenarios/openings/reference_greenhouse.json.gz"

    reasons = _risk_reasons([golden, opening], 0)

    assert reasons == [f"kept simulation data changed: {opening}, {golden}"]
    many = [f"greenhouse_sim/web/public/scenes/scene_{n}.json" for n in range(20)]
    assert not any("files changed" in reason for reason in _risk_reasons(many, 0))


def test_the_acknowledgement_is_the_item_ticked_on_its_own_line() -> None:
    item = "- [x] I manually reviewed the complete diff (required only when ...)"

    assert acknowledged(f"## Review\n\n{item}\n")
    assert acknowledged("- [X] I manually reviewed the complete diff")
    assert not acknowledged("- [ ] I manually reviewed the complete diff")
    assert not acknowledged(f"<!-- the template:\n{item}\n-->")
    assert not acknowledged(f"Say `{item}` once you have.")


def test_small_single_package_change_is_normal_risk() -> None:
    assert (
        _risk_reasons(["greenhouse_sim/greenhouse_sim/biology/tomato/simple/growth.py"], 80) == []
    )


def test_large_change_requires_manual_review() -> None:
    reasons = _risk_reasons(["greenhouse_sim/greenhouse_sim/foo.py"], 501)
    assert any("> 500" in reason for reason in reasons)


def test_protocol_change_requires_manual_review() -> None:
    reasons = _risk_reasons(["greenhouse_protocol/greenhouse_protocol/observation.py"], 20)
    assert "shared protocol/package contract changed" in reasons


def test_cross_package_change_requires_manual_review() -> None:
    reasons = _risk_reasons(
        [
            "greenhouse_sim/greenhouse_sim/engine.py",
            "greenhouse_adapters/greenhouse_adapters/cli.py",
        ],
        30,
    )
    assert any("multiple publishable packages" in reason for reason in reasons)


def test_ci_change_requires_manual_review() -> None:
    reasons = _risk_reasons([".github/workflows/ci.yml"], 10)
    assert "GitHub CI/review automation changed" in reasons


def test_a_maintainers_approval_of_the_latest_commit_acknowledges_it() -> None:
    assert approved([_review("APPROVED")], HEAD)
    assert approved([_review("APPROVED", association="COLLABORATOR")], HEAD)


def test_without_an_approval_there_is_no_acknowledgement() -> None:
    assert not approved([], HEAD)
    assert not approved([_review("COMMENTED")], HEAD)


def test_an_approval_of_an_earlier_commit_does_not_cover_a_later_push() -> None:
    assert not approved([_review("APPROVED", commit=EARLIER)], HEAD)


def test_anyone_but_a_maintainer_approves_for_nothing() -> None:
    for association in ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "NONE"):
        assert not approved([_review("APPROVED", association=association)], HEAD)


def test_a_later_verdict_withdraws_an_approval_and_a_comment_does_not() -> None:
    assert not approved([_review("APPROVED"), _review("CHANGES_REQUESTED")], HEAD)
    assert not approved([_review("DISMISSED")], HEAD)
    assert approved([_review("APPROVED"), _review("COMMENTED")], HEAD)
    assert approved([_review("CHANGES_REQUESTED"), _review("APPROVED")], HEAD)


def test_one_maintainers_approval_is_enough() -> None:
    reviews = [_review("COMMENTED", user="other"), _review("APPROVED")]
    assert approved(reviews, HEAD)
