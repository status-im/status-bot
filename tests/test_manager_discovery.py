"""Discovery tests for ModuleManager: single-file and directory modules."""

import logging
import textwrap

import pytest

from status_bot.config import ModulesConfig
from status_bot.modules.manager import ModuleManager


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


MODULE_TEMPLATE = """\
    from status_bot.modules.base import BaseModule, ModuleType

    class SampleModule(BaseModule):
        MARKER = "{marker}"

        @property
        def module_type(self):
            return {{ModuleType.PERIODIC}}

        def on_start(self):
            pass

        def execute(self):
            pass

        def on_event(self, message):
            pass
"""


@pytest.fixture
def modules_dir(tmp_path):
    directory = tmp_path / "modules"
    directory.mkdir()
    return directory


@pytest.fixture
def manager(tmp_path):
    config = ModulesConfig(directories=[str(tmp_path / "modules")], enabled=[], settings={})
    return ModuleManager(config, account=None, db=None)


def test_single_file_module_is_discovered(manager, modules_dir):
    _write(modules_dir / "foo.py", MODULE_TEMPLATE.format(marker="file"))

    manager._discover_from_directory(str(modules_dir))

    assert "foo" in manager._module_classes
    assert manager._module_classes["foo"].MARKER == "file"


def test_private_and_framework_files_are_ignored(manager, modules_dir):
    for name in ("_private", "base", "manager", "utils"):
        _write(modules_dir / f"{name}.py", MODULE_TEMPLATE.format(marker=name))

    manager._discover_from_directory(str(modules_dir))

    assert manager._module_classes == {}


def test_directory_module_with_plain_sibling_import(manager, modules_dir):
    _write(modules_dir / "plainmod" / "helpers.py", 'MARKER = "plain"')
    _write(
        modules_dir / "plainmod" / "main.py",
        """\
        import helpers

        from status_bot.modules.base import BaseModule, ModuleType

        class SampleModule(BaseModule):
            MARKER = helpers.MARKER

            @property
            def module_type(self):
                return {ModuleType.PERIODIC}

            def on_start(self):
                pass

            def execute(self):
                pass

            def on_event(self, message):
                pass
        """,
    )

    manager._discover_from_directory(str(modules_dir))

    assert "plainmod" in manager._module_classes
    assert manager._module_classes["plainmod"].MARKER == "plain"


def test_directory_module_with_relative_sibling_import(manager, modules_dir):
    _write(modules_dir / "relmod" / "relhelpers.py", 'MARKER = "relative"')
    _write(
        modules_dir / "relmod" / "main.py",
        """\
        from .relhelpers import MARKER as _MARKER

        from status_bot.modules.base import BaseModule, ModuleType

        class SampleModule(BaseModule):
            MARKER = _MARKER

            @property
            def module_type(self):
                return {ModuleType.PERIODIC}

            def on_start(self):
                pass

            def execute(self):
                pass

            def on_event(self, message):
                pass
        """,
    )

    manager._discover_from_directory(str(modules_dir))

    assert "relmod" in manager._module_classes
    assert manager._module_classes["relmod"].MARKER == "relative"


def test_file_and_directory_conflict_prefers_directory(manager, modules_dir, caplog):
    _write(modules_dir / "twins.py", MODULE_TEMPLATE.format(marker="file"))
    _write(modules_dir / "twins" / "main.py", MODULE_TEMPLATE.format(marker="dir"))

    with caplog.at_level(logging.WARNING, logger="status_bot.modules.manager"):
        manager._discover_from_directory(str(modules_dir))

    assert manager._module_classes["twins"].MARKER == "dir"
    assert any(
        "'twins' exists both as a file and a directory" in record.message
        for record in caplog.records
    )


def test_directory_without_main_py_is_ignored(manager, modules_dir):
    _write(modules_dir / "noentry" / "helpers.py", "MARKER = 1")

    manager._discover_from_directory(str(modules_dir))

    assert "noentry" not in manager._module_classes


def test_builtin_modules_are_still_discovered(tmp_path):
    config = ModulesConfig(directories=[], enabled=[], settings={})
    manager = ModuleManager(config, account=None, db=None)

    manager.discover_modules()

    assert {
        "messaging",
        "receiver",
        "community_monitoring",
        "engagement",
        "api_server",
    } <= set(manager._module_classes.keys())
