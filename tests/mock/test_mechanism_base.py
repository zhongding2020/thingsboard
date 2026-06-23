import pytest
from process_opt.mock.mechanism.base import MechanismModel, ParamSpec, ResultSpec
from process_opt.mock.mechanism import get_mechanism, register_mechanism, list_mechanisms
from process_opt.common.schemas import InspectionItem


class _DummyModel(MechanismModel):
    param_spec = {"temp": ParamSpec(key="temp", unit="C", min_val=0, max_val=100, default=50)}
    result_spec = [ResultSpec(name="quality", usl=1.5, lsl=0.5)]

    def simulate(self, params):
        return [InspectionItem(name="quality", value=1.0, usl=1.5, lsl=0.5)]


def test_param_spec_defaults():
    ps = ParamSpec(key="x")
    assert ps.unit == ""
    assert ps.min_val == 0.0
    assert ps.default == 0.0


def test_result_spec_fields():
    rs = ResultSpec(name="y", unit="mm", usl=2.0, lsl=0.5)
    assert rs.name == "y"
    assert rs.usl == 2.0


def test_mechanism_model_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        MechanismModel()  # type: ignore[abstract]


def test_mechanism_model_concrete_works():
    m = _DummyModel()
    result = m.simulate({"temp": 50})
    assert len(result) == 1
    assert result[0].name == "quality"


@pytest.fixture(autouse=True)
def _clear_registry():
    from process_opt.mock import mechanism
    mechanism._registry.clear()
    yield
    mechanism._registry.clear()


def test_registry_empty_raises():
    with pytest.raises(ValueError, match="No mechanism model"):
        get_mechanism("nonexistent")


def test_register_and_get():
    register_mechanism("dummy")(_DummyModel)
    m = get_mechanism("dummy")
    assert isinstance(m, _DummyModel)
    assert m.param_spec["temp"].unit == "C"


def test_list_mechanisms():
    register_mechanism("dummy")(_DummyModel)
    assert "dummy" in list_mechanisms()
