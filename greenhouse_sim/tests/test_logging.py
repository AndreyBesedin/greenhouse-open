"""The simulator logs as a library does (AUDIT.14): through loggers under
its package's, which print nothing until an application configures them."""

import logging

import greenhouse_sim


def test_the_package_prints_nothing_until_an_application_configures_logging() -> None:
    package = logging.getLogger(greenhouse_sim.__name__)

    assert any(isinstance(handler, logging.NullHandler) for handler in package.handlers)
