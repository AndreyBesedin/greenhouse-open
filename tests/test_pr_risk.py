from scripts.check_pr_risk import ROOT, SENSITIVE_FILES, _risk_reasons


def test_every_sensitive_path_exists() -> None:
    """A sensitive file that moves must take its entry with it. Otherwise the
    gate silently stops flagging changes to it."""
    missing = sorted(path for path in SENSITIVE_FILES if not (ROOT / path).exists())
    assert not missing, f"sensitive paths that no longer exist: {missing}"


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
