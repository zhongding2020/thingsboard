from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from process_opt.agent.nodes.analyzer import create_analyzer_node
from process_opt.agent.nodes.chat import create_chat_node
from process_opt.agent.nodes.recommender import create_recommender_node
from process_opt.agent.nodes.supervisor import create_supervisor_node
from process_opt.agent.state import AgentState
from process_opt.agent.tools.analysis_tools import create_analysis_tools
from process_opt.knowledge.loader import KnowledgeLoader

logger = logging.getLogger(__name__)

WORKERS = ["chat", "analyzer", "recommender"]


def build_graph(
    llm: Any,
    llm_with_tools: Any,
    tools: list,
    knowledge_loader: KnowledgeLoader,
):
    supervisor_node = create_supervisor_node(llm)
    chat_node = create_chat_node(llm_with_tools, knowledge_loader)
    analyzer_node = create_analyzer_node(llm_with_tools, knowledge_loader)
    recommender_node = create_recommender_node(llm_with_tools, knowledge_loader)

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

    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state.get("next", "FINISH"),
        {**{w: w for w in WORKERS}, "tools": "tools", "FINISH": END},
    )

    return workflow.compile()


class AgentSession:
    def __init__(self, session_id: str, user_id: str, process_type: str, graph: Any) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.process_type = process_type
        self.graph = graph
        self.config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 50,
        }
        self.state: dict = {
            "messages": [],
            "user_id": user_id,
            "process_type": process_type,
            "intent": "",
            "next": "supervisor",
        }
        self.event_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._running = False
        self.last_active = time.monotonic()

    async def send_message(self, text: str) -> None:
        from langchain_core.messages import HumanMessage
        self.state["messages"].append(HumanMessage(content=text))
        self.state["next"] = "supervisor"
        self._running = True
        asyncio.create_task(self._run_graph())

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

    async def create(self, user_id: str, process_type: str, graph: Any) -> AgentSession:
        sid = f"ses_{uuid.uuid4().hex[:20]}"
        session = AgentSession(sid, user_id, process_type, graph)
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
