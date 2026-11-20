from importlib import import_module


def test_project_environment_and_existing_entrypoint(capsys):
    for name in ("numpy", "pandas", "scipy", "matplotlib", "yaml"):
        import_module(name)

    package = import_module("adaptive_ramp_metering")
    package.main()
    assert capsys.readouterr().out == "Hello from adaptive-ramp-metering!\n"
