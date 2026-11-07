"""Settings resolution tests: deep merge and per-module YAML overlay."""

import logging

import pytest

from status_bot.config import ModulesConfig
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.modules.manager import ModuleManager, _deep_merge, _load_module_yaml


@pytest.fixture
def config_dir(tmp_path):
    directory = tmp_path / "module-configs"
    directory.mkdir()
    return directory


def _manager(settings=None, config_directory=None):
    config = ModulesConfig(
        directories=[],
        enabled=[],
        settings=settings or {},
        config_directory=config_directory,
    )
    return ModuleManager(config, account=None, db=None)


# --- _deep_merge -------------------------------------------------------------


def test_deep_merge_merges_nested_dicts():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 20, "z": 30}}

    merged = _deep_merge(base, override)

    assert merged == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}


def test_deep_merge_override_wins_on_leaves():
    assert _deep_merge({"k": "old"}, {"k": "new"}) == {"k": "new"}


def test_deep_merge_non_dict_replaces_dict():
    assert _deep_merge({"k": {"nested": True}}, {"k": "flat"}) == {"k": "flat"}


def test_deep_merge_does_not_mutate_base():
    base = {"a": {"x": 1}}
    _deep_merge(base, {"a": {"x": 2}})
    assert base == {"a": {"x": 1}}


# --- _load_module_yaml -------------------------------------------------------


def test_module_yaml_returns_empty_without_config_directory():
    assert _load_module_yaml(None, "foo") == {}


def test_module_yaml_returns_empty_when_file_missing(config_dir):
    assert _load_module_yaml(str(config_dir), "foo") == {}


def test_module_yaml_loads_mapping(config_dir):
    (config_dir / "foo.yaml").write_text("interval: 5\nnested:\n  key: v\n")

    assert _load_module_yaml(str(config_dir), "foo") == {"interval": 5, "nested": {"key": "v"}}


def test_module_yaml_empty_file_is_empty_dict(config_dir):
    (config_dir / "foo.yaml").write_text("")

    assert _load_module_yaml(str(config_dir), "foo") == {}


def test_module_yaml_non_mapping_is_empty_dict(config_dir):
    (config_dir / "foo.yaml").write_text("- one\n- two\n")

    assert _load_module_yaml(str(config_dir), "foo") == {}


# --- _resolve_module_settings ------------------------------------------------


def test_resolve_settings_without_config_directory():
    manager = _manager(settings={"foo": {"a": 1}})

    assert manager._resolve_module_settings("foo") == {"a": 1}


def test_resolve_settings_config_dir_without_yaml_file(config_dir):
    manager = _manager(settings={"foo": {"a": 1}}, config_directory=str(config_dir))

    assert manager._resolve_module_settings("foo") == {"a": 1}


def test_resolve_settings_yaml_only(config_dir):
    (config_dir / "foo.yaml").write_text("a: 2\nb: 3\n")
    manager = _manager(config_directory=str(config_dir))

    assert manager._resolve_module_settings("foo") == {"a": 2, "b": 3}


def test_resolve_settings_deep_merge_yaml_wins(config_dir):
    (config_dir / "foo.yaml").write_text("nested:\n  y: 20\n  z: 30\ninterval: 5\n")
    manager = _manager(
        settings={"foo": {"nested": {"x": 1, "y": 2}, "keep": "yes"}},
        config_directory=str(config_dir),
    )

    resolved = manager._resolve_module_settings("foo")

    assert resolved == {
        "nested": {"x": 1, "y": 20, "z": 30},
        "keep": "yes",
        "interval": 5,
    }


def test_resolve_settings_malformed_yaml_falls_back_to_base(config_dir, caplog):
    (config_dir / "foo.yaml").write_text("invalid: [unclosed\n")
    manager = _manager(settings={"foo": {"a": 1}}, config_directory=str(config_dir))

    with caplog.at_level(logging.ERROR, logger="status_bot.modules.manager"):
        resolved = manager._resolve_module_settings("foo")

    assert resolved == {"a": 1}
    assert any("Invalid module YAML for 'foo'" in record.message for record in caplog.records)


def test_resolve_settings_non_dict_base_is_treated_as_empty(config_dir):
    manager = _manager(settings={"foo": "not-a-dict"}, config_directory=str(config_dir))

    assert manager._resolve_module_settings("foo") == {}


# --- load_modules integration ------------------------------------------------


class StubModule(BaseModule):
    @property
    def module_type(self):
        return {ModuleType.PERIODIC}

    def on_start(self):
        pass

    def execute(self):
        pass

    def on_event(self, message):
        pass


def _stub_manager(settings, config_directory):
    manager = _manager(settings=settings, config_directory=config_directory)
    manager._module_classes["stub"] = StubModule
    manager._modules_config.enabled = ["stub"]
    return manager


def test_load_modules_uses_merged_settings(config_dir):
    (config_dir / "stub.yaml").write_text("interval: 5\nextra: hi\n")
    manager = _stub_manager({"stub": {"interval": 2, "keep": "yes"}}, str(config_dir))

    manager.load_modules()

    module = manager.modules["stub"]
    assert module.ctx.config.interval == 5
    assert module.settings == {"interval": 5, "keep": "yes", "extra": "hi"}


def test_load_modules_survives_malformed_module_yaml(config_dir):
    (config_dir / "stub.yaml").write_text("invalid: [unclosed\n")
    manager = _stub_manager({"stub": {"interval": 2}}, str(config_dir))

    manager.load_modules()

    module = manager.modules["stub"]
    assert module.ctx.config.interval == 2
    assert module.settings == {"interval": 2}
