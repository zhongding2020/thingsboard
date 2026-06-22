from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from process_opt.agent.nodes.worker import create_worker_node
from process_opt.agent.nodes.supervisor import create_supervisor_node, _has_pending_tool_calls
from process_opt.agent.state import AgentState
from process_opt.agent.tools.analysis_tools import create_analysis_tools
from process_opt.knowledge.loader import KnowledgeLoader

logger = logging.getLogger(__name__)

WORKERS = ["chat", "analyzer", "recommender"]

# Increased from 50 to prevent premature limit hits; each tool call + interpretation
# round-trip consumes ~4 node transitions, so 50 only allows ~12 tool calls.
RECURSION_LIMIT = 150


def build_graph(
    llm: Any,
    llm_with_tools: Any,
    tools: list,
    knowledge_loader: KnowledgeLoader,
):
    supervisor_node = create_supervisor_node(llm)
    chat_node = create_worker_node("chat", llm_with_tools, knowledge_loader)
    analyzer_node = create_worker_node("analyzer", llm_with_tools, knowledge_loader)
    recommender_node = create_worker_node("recommender", llm_with_tools, knowledge_loader)

    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("recommender", recommender_node)
    workflow.add_node("tools", ToolNode(tools))

    workflow.set_entry_point("supervisor")

    for worker in WORKERS:
        workflow.add_edge(worker, "supervisor")
    workflow.add_edge("tools", "supervisor")

    # Routing function: checks for pending tool calls first, then falls back
    # to the supervisor's decision. This provides a safety net even if the
    # supervisor LLM fails to route tools correctly.
    def _route(state: dict) -> str:
        # Safety net: auto-detect pending tool calls
        if _has_pending_tool_calls(state):
            return "tools"
        # Use supervisor's decision, default to FINISH
        return state.get("next", "FINISH")

    workflow.add_conditional_edges(
        "supervisor",
        _route,
        {**{w: w for w in WORKERS}, "tools": "tools", "FINISH": END},
    )

    return workflow.compile()


THINKING_PROMPT = """你是一个工艺参数分析助手的思考过程。请用中文，简洁地分析用户的意图，并规划执行步骤。

要求：
1. 识别用户的核心需求（数据分析？参数推荐？工艺咨询？）
2. 判断是否需要进入工艺调优工作流（5阶段：Define→Explore→Analyze→Optimize→Verify）
3. 列出可能需要调用的工具（最多3-5个）
4. 用2-4句话完成，不要展开细节

用户消息："""


class AgentSession:
    def __init__(self, session_id: str, user_id: str, process_type: str, graph: Any, llm: Any = None) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.process_type = process_type
        self.graph = graph
        self.llm = llm
        self.config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": RECURSION_LIMIT,
        }
        self.state: dict = {
            "messages": [],
            "user_id": user_id,
            "process_type": process_type,
            "intent": "",
            "next": "supervisor",
            "mode": "chat",
            "phase": "",
            "goal": None,
            "baseline": None,
            "recommendation": None,
            "dataset_id": "",
            "experiment_plan_id": 0,
        }
        self.event_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._running = False
        self.last_active = time.monotonic()

    async def send_message(self, text: str) -> None:
        from langchain_core.messages import HumanMessage

        if self._running:
            return

        self.state["messages"].append(HumanMessage(content=text))
        self.state["next"] = "supervisor"
        self._running = True
        asyncio.create_task(self._run_with_thinking(text))

    async def _run_with_thinking(self, text: str) -> None:
        """Generate thinking plan before executing graph."""
        try:
            if self.llm is not None:
                await self.event_queue.put({"type": "thinking.start"})
                full = ""
                async for chunk in self.llm.astream(THINKING_PROMPT + text):
                    content = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if content:
                        full += content
                        await self.event_queue.put({"type": "thinking.delta", "text": content})
                await self.event_queue.put({"type": "thinking.done", "text": full})
        except Exception as e:
            logger.warning("Thinking generation failed: %s", e)
            await self.event_queue.put({"type": "thinking.done", "text": ""})

        await self._run_graph()

    async def _run_graph(self) -> None:
        try:
            async for event in self.graph.astream_events(self.state, self.config, version="v2"):
                await self.event_queue.put(event)
        except Exception as e:
            logger.error("Graph error session %s: %s", self.session_id, e)
            await self.event_queue.put({"type": "error", "message": str(e)})
        finally:
            self._running = False
            await self.event_queue.put({"type": "done"})
            self.last_active = time.monotonic()

    def get_messages(self) -> list[dict]:
        from langchain_core.messages import BaseMessage
        result: list[dict] = []
        for msg in self.state.get("messages", []):
            if isinstance(msg, BaseMessage):
                result.append({
                    "role": getattr(msg, "type", "unknown"),
                    "content": msg.content if hasattr(msg, "content") else str(msg),
                })
        return result


class SessionManager:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def create(self, user_id: str, process_type: str, graph: Any, llm: Any = None) -> AgentSession:
        sid = f"ses_{uuid.uuid4().hex[:20]}"
        session = AgentSession(sid, user_id, process_type, graph, llm=llm)
        async with self._lock:
            self._sessions[sid] = session
        return session

    async def get(self, session_id: str) -> AgentSession | None:
        session = self._sessions.get(session_id)
        if session:
            session.last_active = time.monotonic()
        return session

    async def list_user(self, user_id: str) -> list[dict]:
        results: list[dict] = []
        for s in self._sessions.values():
            if s.user_id == user_id:
                results.append({
                    "session_id": s.session_id,
                    "process_type": s.process_type,
                    "message_count": len(s.state.get("messages", [])),
                })
        return results

    async def expire_stale(self) -> None:
        now = time.monotonic()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_active > self._ttl]
        for sid in expired:
            del self._sessions[sid]
            logger.info("Expired session %s", sid)
