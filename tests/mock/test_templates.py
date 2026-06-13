from process_opt.mock.templates import DEVICE_TEMPLATES


PARAM_FIELDS = {"min", "max", "mu", "sigma", "precision"}


def test_device_templates_defined() -> None:
    assert isinstance(DEVICE_TEMPLATES, dict)


def test_reflow_oven_exists() -> None:
    assert "reflow-oven" in DEVICE_TEMPLATES


def test_injection_molder_exists() -> None:
    assert "injection-molder" in DEVICE_TEMPLATES


def test_each_template_has_params_and_results() -> None:
    for name, template in DEVICE_TEMPLATES.items():
        assert "params" in template, f"{name} missing params"
        assert "results" in template, f"{name} missing results"


def test_each_param_has_required_fields() -> None:
    for name, template in DEVICE_TEMPLATES.items():
        for param_name, config in template["params"].items():
            assert isinstance(config, dict), f"{name}.params.{param_name} not a dict"
            missing = PARAM_FIELDS - set(config.keys())
            assert not missing, f"{name}.params.{param_name} missing {missing}"
            for key in ("min", "max", "mu", "sigma"):
                assert isinstance(config[key], (int, float)), (
                    f"{name}.params.{param_name}.{key} not numeric"
                )
            assert isinstance(config["precision"], int), (
                f"{name}.params.{param_name}.precision not int"
            )


def test_each_result_is_string_or_dict() -> None:
    for name, template in DEVICE_TEMPLATES.items():
        for result_name, config in template["results"].items():
            assert isinstance(config, (str, dict)), (
                f"{name}.results.{result_name} not str or dict"
            )
