import pytest
from unittest.mock import MagicMock, patch, DEFAULT
from process_opt.agent.deep_agent import create_process_agent


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_tool_pool():
    async def query_records(**kwargs):
        return "mock result"
    async def run_spc(**kwargs):
        return "spc result"
    return {
        "query_records": query_records,
        "run_spc": run_spc,
    }


@pytest.fixture
def mock_registry():
    return {
        "adhesive_curing": {
            "name": "adhesive_curing",
            "display_name": "点胶固化",
            "type": "process",
            "tools": ["query_records", "run_spc"],
            "system_prompt": "## 工艺参数\n\n测试正文",
        },
        "spc-monitoring": {
            "name": "spc-monitoring",
            "type": "capability",
            "tools": ["run_spc"],
            "system_prompt": "## SPC 监控",
        },
    }


class TestCreateProcessAgent:
    def test_raises_for_unknown_process_type(self, mock_llm, mock_tool_pool, mock_registry):
        with patch("process_opt.agent.deep_agent.SKILL_REGISTRY", mock_registry):
            with pytest.raises(ValueError, match="Unknown process type"):
                import asyncio
                asyncio.run(create_process_agent(
                    mock_llm, "nonexistent", mock_tool_pool,
                ))

    def test_merges_process_and_capability_tools(self, mock_llm, mock_tool_pool, mock_registry):
        with patch("process_opt.agent.deep_agent.SKILL_REGISTRY", mock_registry):
            with patch("process_opt.agent.deep_agent.get_capability_skills") as mock_get_cap:
                with patch.multiple(
                    "process_opt.agent.deep_agent",
                    create_deep_agent=DEFAULT,
                    FilesystemMiddleware=DEFAULT,
                    SummarizationMiddleware=DEFAULT,
                ) as mocks:
                    mock_get_cap.return_value = [
                        s for s in mock_registry.values() if s.get("type") == "capability"
                    ]

                    import asyncio
                    asyncio.run(create_process_agent(
                        mock_llm, "adhesive_curing", mock_tool_pool,
                    ))

                    call_kwargs = mocks["create_deep_agent"].call_args.kwargs
                    # Should include tools from both process + capability
                    tool_names = {t.__name__ for t in call_kwargs["tools"]}
                    assert "query_records" in tool_names
                    assert "run_spc" in tool_names

    def test_system_prompt_from_skill_body(self, mock_llm, mock_tool_pool, mock_registry):
        with patch("process_opt.agent.deep_agent.SKILL_REGISTRY", mock_registry):
            with patch("process_opt.agent.deep_agent.get_capability_skills") as mock_get_cap:
                with patch.multiple(
                    "process_opt.agent.deep_agent",
                    create_deep_agent=DEFAULT,
                    FilesystemMiddleware=DEFAULT,
                    SummarizationMiddleware=DEFAULT,
                ) as mocks:
                    mock_get_cap.return_value = []

                    import asyncio
                    asyncio.run(create_process_agent(
                        mock_llm, "adhesive_curing", mock_tool_pool,
                    ))

                    call_kwargs = mocks["create_deep_agent"].call_args.kwargs
                    assert call_kwargs["system_prompt"] == "## 工艺参数\n\n测试正文"
