import pytest
from process_opt.mock.mechanism import get_mechanism, list_mechanisms
from process_opt.mock.mechanism.base import MechanismModel


MODELS = ["reflow-oven", "injection-molder", "oven-curing", "cnc-drill", "coating-machine"]

# Import to trigger @register_mechanism decorators
import process_opt.mock.mechanism.reflow_oven       # noqa: F401
import process_opt.mock.mechanism.injection_molder  # noqa: F401
import process_opt.mock.mechanism.oven_curing       # noqa: F401
import process_opt.mock.mechanism.cnc_drill         # noqa: F401
import process_opt.mock.mechanism.coating_machine   # noqa: F401


@pytest.mark.parametrize("device_type", MODELS)
def test_model_is_registered(device_type: str):
    assert device_type in list_mechanisms()


@pytest.mark.parametrize("device_type", MODELS)
def test_model_is_mechanism_instance(device_type: str):
    assert isinstance(get_mechanism(device_type), MechanismModel)


@pytest.mark.parametrize("device_type", MODELS)
def test_model_has_param_spec(device_type: str):
    m = get_mechanism(device_type)
    assert len(m.param_spec) >= 3, f"{device_type} should have >= 3 params"


@pytest.mark.parametrize("device_type", MODELS)
def test_model_has_result_spec(device_type: str):
    m = get_mechanism(device_type)
    assert len(m.result_spec) == 2, f"{device_type} should have 2 results"


@pytest.mark.parametrize("device_type", MODELS)
def test_simulate_returns_inspection_items(device_type: str):
    m = get_mechanism(device_type)
    defaults = {k: v.default for k, v in m.param_spec.items()}
    results = m.simulate(defaults)
    assert len(results) == len(m.result_spec)
    for ri in results:
        assert ri.name in {rs.name for rs in m.result_spec}
        assert ri.result in ("pass", "fail")
        assert isinstance(ri.value, (int, float))


@pytest.mark.parametrize("device_type", MODELS)
def test_simulate_varying_params_gives_different_results(device_type: str):
    m = get_mechanism(device_type)
    defaults = {k: v.default for k, v in m.param_spec.items()}
    low = {k: v.min_val for k, v in m.param_spec.items()}
    high = {k: v.max_val for k, v in m.param_spec.items()}
    r_def = m.simulate(defaults)
    r_low = m.simulate(low)
    r_high = m.simulate(high)
    values_def = [ri.value for ri in r_def]
    values_low = [ri.value for ri in r_low]
    values_high = [ri.value for ri in r_high]
    # At least one result should differ between extremes
    any_diff = any(vl != vh for vl, vh in zip(values_low, values_high))
    assert any_diff, f"{device_type}: simulating min vs max params should produce different results"
