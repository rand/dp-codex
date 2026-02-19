from importlib import import_module


def test_dp_packages_are_importable() -> None:
    modules = ("dp", "dp.cli", "dp.core", "dp.enforcement", "dp.providers")

    for module_name in modules:
        assert import_module(module_name) is not None
