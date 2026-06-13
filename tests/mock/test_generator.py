from process_opt.mock.generator import generate_params, generate_results, generate_pair
from process_opt.mock.templates import DEVICE_TEMPLATES


def test_generate_params_returns_all_keys() -> None:
    for device_type in DEVICE_TEMPLATES:
        params = generate_params(device_type)
        expected = set(DEVICE_TEMPLATES[device_type]["params"].keys())
        assert set(params.keys()) == expected


def test_generate_params_values_in_range() -> None:
    for device_type in DEVICE_TEMPLATES:
        for _ in range(50):
            params = generate_params(device_type)
            for name, value in params.items():
                cfg = DEVICE_TEMPLATES[device_type]["params"][name]
                assert cfg["min"] <= value <= cfg["max"], (
                    f"{device_type}.{name}: {value} not in [{cfg['min']}, {cfg['max']}]"
                )


def test_generate_params_respects_precision() -> None:
    for device_type in DEVICE_TEMPLATES:
        for _ in range(50):
            params = generate_params(device_type)
            for name, value in params.items():
                precision = DEVICE_TEMPLATES[device_type]["params"][name]["precision"]
                if precision == 0:
                    assert isinstance(value, int), f"{name} should be int"
                else:
                    multiplier = 10**precision
                    assert abs(round(value * multiplier) / multiplier - value) < 1e-9, (
                        f"{name} precision mismatch"
                    )


def test_generate_params_outlier_rate_roughly_5pc() -> None:
    n = 2000
    device_type = "reflow-oven"
    cfg = DEVICE_TEMPLATES[device_type]["params"]["temperature"]
    mu, sigma = cfg["mu"], cfg["sigma"]
    outliers = 0
    for _ in range(n):
        val = generate_params(device_type)["temperature"]
        if val < mu - 2 * sigma or val > mu + 2 * sigma:
            outliers += 1
    rate = outliers / n
    # Expect ~5% for gauss outside 2 sigma, plus forced 5% random outliers
    assert 0.02 <= rate <= 0.20, f"outlier rate {rate:.3f} outside [0.02, 0.20]"


def test_generate_results_returns_all_keys() -> None:
    for device_type in DEVICE_TEMPLATES:
        params = generate_params(device_type)
        results = generate_results(device_type, params)
        expected = set(DEVICE_TEMPLATES[device_type]["results"].keys())
        assert set(results.keys()) == expected


def test_generate_results_values_pass_fail() -> None:
    for device_type in DEVICE_TEMPLATES:
        for _ in range(50):
            params = generate_params(device_type)
            results = generate_results(device_type, params)
            for name, value in results.items():
                assert value in ("pass", "fail"), f"{name} expected pass/fail, got {value}"


def test_generate_pair_returns_two_dicts() -> None:
    process, inspection = generate_pair("reflow-oven", "B-001")
    assert isinstance(process, dict)
    assert isinstance(inspection, dict)


def test_generate_pair_has_required_fields() -> None:
    process, inspection = generate_pair("reflow-oven", "B-001")
    for field in ("message_id", "barcode", "processed_at", "params"):
        assert field in process, f"process missing {field}"
    for field in ("message_id", "barcode", "inspected_at", "results"):
        assert field in inspection, f"inspection missing {field}"
    assert process["barcode"] == "B-001"
    assert inspection["barcode"] == "B-001"
    assert process["message_id"] == inspection["message_id"]
