from importlib.metadata import requires

from fr_common_utils.logging import get_logger

from yield_report.shared_kernel.infrastructure import codex_cli_client, llm_handler


def test_shared_adapters_use_declared_common_logging_dependency() -> None:
    project_requirements = requires("yield-report-generator") or []

    assert any(
        requirement.lower().startswith("fr-common-utils")
        for requirement in project_requirements
    )
    assert llm_handler.logger is get_logger(llm_handler.__name__)
    assert codex_cli_client.logger is get_logger(codex_cli_client.__name__)
