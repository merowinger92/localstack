import json
import os
from typing import Optional

import pytest
from _pytest.config import Config, PytestPluginManager
from _pytest.config.argparsing import Parser
from _pytest.fixtures import SubRequest
from _pytest.nodes import Item
from _pytest.reports import TestReport
from _pytest.runner import CallInfo
from pluggy.callers import _Result

from localstack.testing.pytest.fixtures import (  # TODO(!) fix. shouldn't import from a plugin module
    _client,
)
from localstack.testing.snapshots import SnapshotAssertionError, SnapshotSession
from localstack.testing.snapshots.report import render_report
from localstack.testing.snapshots.transformer import RegexTransformer
from localstack.testing.snapshots.transformer_utility import SNAPSHOT_BASIC_TRANSFORMER


def is_aws():
    return os.environ.get("TEST_TARGET", "") == "AWS_CLOUD"


@pytest.hookimpl
def pytest_configure(config: Config):
    config.addinivalue_line("markers", "skip_snapshot_verify")


@pytest.hookimpl
def pytest_addoption(parser: Parser, pluginmanager: PytestPluginManager):
    parser.addoption("--snapshot-update", action="store_true")
    parser.addoption("--snapshot-skip-all", action="store_true")
    parser.addoption("--snapshot-verify", action="store_true")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: CallInfo[None]) -> Optional[TestReport]:
    use_legacy_report = os.environ.get("SNAPSHOT_LEGACY_REPORT", "0") == "1"

    result: _Result = yield
    report: TestReport = result.result

    if call.excinfo is not None and isinstance(call.excinfo.value, SnapshotAssertionError):
        err: SnapshotAssertionError = call.excinfo.value

        if use_legacy_report:
            error_report = ""
            for res in err.result:
                if not res:
                    error_report = f"{error_report}Match failed for '{res.key}':\n{json.dumps(json.loads(res.result.to_json()), indent=2)}\n\n"
            report.longrepr = error_report
        else:
            report.longrepr = "\n".join([str(render_report(r)) for r in err.result if not r])
    return report


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: Item) -> None:
    call: CallInfo = yield  # noqa

    # TODO: extremely dirty... maybe it would be better to find a way to fail the test itself instead?
    sm = item.funcargs.get("snapshot")

    if sm:
        verify = True
        paths = []

        if not is_aws():  # only skip for local tests

            for m in item.iter_markers(name="skip_snapshot_verify"):

                skip_paths = m.kwargs.get("paths", [])

                skip_condition = m.kwargs.get("condition")
                # can optionally include a condition, when this will be skipped
                # a condition must be a Callable returning something truthy/falsey
                if skip_condition:
                    if not callable(skip_condition):
                        raise ValueError("condition must be a callable")

                    if not skip_condition():
                        continue  # don't skip

                # we skip verification if no condition has been specified
                verify = False
                paths.extend(skip_paths)

        sm._assert_all(verify, paths)


@pytest.fixture(name="account_id", scope="session")
def fixture_account_id():
    sts_client = _client("sts")  # TODO: extract client factory from fixtures plugin
    yield sts_client.get_caller_identity()["Account"]


@pytest.fixture(name="region", scope="session")
def fixture_region():
    sts_client = _client("sts")  # TODO: extract client factory from fixtures plugin
    yield sts_client.meta.region_name


@pytest.fixture(name="snapshot", scope="function")
def fixture_snapshot(request: SubRequest, account_id, region):
    update_overwrite = os.environ.get("SNAPSHOT_UPDATE", None) == "1"

    sm = SnapshotSession(
        file_path=os.path.join(
            request.fspath.dirname, f"{request.fspath.purebasename}.snapshot.json"
        ),
        scope_key=request.node.nodeid,
        update=update_overwrite or request.config.option.snapshot_update,
        verify=False if request.config.option.snapshot_skip_all else True,
    )
    sm.add_transformer(RegexTransformer(account_id, "1" * 12), priority=2)
    sm.add_transformer(RegexTransformer(region, "<region>"), priority=2)
    sm.add_transformer(SNAPSHOT_BASIC_TRANSFORMER, priority=2)

    yield sm

    sm._persist_state()
