import logging
import time
import subprocess
import uuid
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from ..agents.agentic_critic import AgenticCriticAgent, SYSTEM_PROMPT as AGENTIC_SYSTEM_PROMPT
from ..agents.detection import Detector
from ..agents.retrieval import Retriever
from ..artifact.schema import (
    RunArtifact,
    AgentLLMMetrics,
    AgentRetrievalMetrics,
    AgentsMetrics,
    CandidateSmell,
)
from ..artifact.validator import MalformedOutputError, parse_critic_output
from ..llm.base import LLMResponse, cache_tokens_from_langchain_usage
from ..orchestrator.retry import with_retry, MaxRetriesExceeded

logger = logging.getLogger(__name__)

SMELL_SCOPE = {
    "single_segment_namespace": "ns_form",
    "implicit_namespace_dependencies": "ns_form",
    "excessive_refers": "ns_form",
    "namespace_load_side_effects": "file",
    "relying_on_load_time_side_effects": "file",
    "monolithic_namespace_split": "file"
}


class PipelineState(TypedDict, total=False):
    """Shared state threaded through the graph. Every node reads what it
    needs and returns only the keys it updates — LangGraph merges the rest
    forward unchanged."""
    code: str
    file_path: str
    search_root: Optional[str]
    run_id: str

    filtered_catalog: dict
    candidates: list[CandidateSmell]
    det_response: object
    det_prompt: str
    det_sys: str
    no_candidates: bool
    detection_retries: int

    candidate_contexts: dict[str, str]

    # agentic judge only — the agent ⇄ tools conversation
    messages: Annotated[list, add_messages]
    critic_attempt: int
    tool_rounds: int
    judge_start_time: float
    agentic_judge_done: bool

    verdicts: list
    crit_response: object
    crit_prompt: str
    crit_sys: str
    tool_calls: int
    tool_latency_ms: float
    tool_transcript: str
    critic_retries: int


class Orchestrator:
    """
    Coordinates the full Detection → Retrieval → Critic pipeline as ONE
    LangGraph graph. In agentic mode, the tool-calling cycle (agent ⇄ tools)
    is wired directly into this same StateGraph(PipelineState) — not a
    second, separately-compiled graph invoked from a node. AgenticCriticAgent
    supplies the bound model, tools, and prompt building/parsing; this class
    owns the entire graph topology, including the one cycle in the system.

    An earlier version kept AgenticCriticAgent's loop as its own graph,
    invoked from a judge_agentic node — functionally equivalent, but two
    graph objects instead of one. See ARCHITECTURE_DECISIONS.md for why this
    version replaced it.
    """

    def __init__(
        self,
        detector: Detector,
        retriever: Retriever,
        critic,
        vectordb_name: str = "mock",
        max_retries: int = 3,
        timeout_s: int = 120,
        mode: str = "rag",
        catalog: dict | None = None,
    ):
        """
        mode="rag" (default): unchanged pipeline — Retriever pre-fetches
            evidence from vectordb before Critic judges.
        mode="agentic": Retriever.run() is skipped entirely; `critic` must be
            an AgenticCriticAgent — its tools/model are wired straight into
            this graph. `catalog` is required in this mode.
        """
        if mode not in ("rag", "agentic"):
            raise ValueError(f"Unknown orchestrator mode: '{mode}'. Use 'rag' or 'agentic'.")
        if mode == "agentic" and catalog is None:
            raise ValueError("mode='agentic' requires the `catalog` argument.")

        self.detector = detector
        self.retriever = retriever
        self.critic = critic
        self.vectordb_name = vectordb_name
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self.mode = mode
        self.catalog = catalog

        # kept for any external code/tests that read these attribute names
        self.detection = detector
        self.retrieval = retriever

        self._graph = self._build_graph()

    # ── Nodes shared by both modes ──────────────────────────────────────

    def _node_pre_filter(self, state: PipelineState) -> dict:
        return {"filtered_catalog": self.detector.filter_catalog(state["code"])}

    def _node_detect(self, state: PipelineState) -> dict:
        logger.info("[Detection] Starting...")

        @with_retry(self.max_retries)
        def _run():
            return self.detector.run(
                state["code"], timeout=self.timeout_s, catalog=state["filtered_catalog"],
            )

        try:
            candidates, det_response, det_prompt, det_sys = _run()
        except MaxRetriesExceeded as exc:
            logger.error("[Detection] Failed after retries: %s", exc)
            raise

        if det_response.cache_read_tokens or det_response.cache_write_tokens:
            logger.info(
                "[Detection][cache] prompt_tokens=%d cached_tokens=%d "
                "cache_write_tokens=%d (%.0f%% of prompt served from cache).",
                det_response.prompt_tokens, det_response.cache_read_tokens,
                det_response.cache_write_tokens,
                (100.0 * det_response.cache_read_tokens / det_response.prompt_tokens)
                if det_response.prompt_tokens else 0.0,
            )
        logger.info("[Detection] Found %d candidate(s).", len(candidates))
        return {
            "candidates": candidates,
            "det_response": det_response,
            "det_prompt": det_prompt,
            "det_sys": det_sys,
            "no_candidates": not candidates,
            "detection_retries": _run.retries_used,
        }

    @staticmethod
    def _route_after_detect(state: PipelineState) -> str:
        return "no_candidates" if state.get("no_candidates") else "extract"

    def _node_extract(self, state: PipelineState) -> dict:
        logger.info("[Extraction] Extracting contexts for candidates...")
        code, file_path = state["code"], state["file_path"]
        candidates = state["candidates"]
        candidate_contexts: dict[str, str] = {}

        for cand in candidates:
            scope = SMELL_SCOPE.get(cand.smell_id, "function")
            key = f"{cand.smell_id}::{cand.element_name}"

            if scope == "file":
                candidate_contexts[key] = "__FILE_SCOPE__"
                cand.snippet = code
                continue

            extract_mode = "ns_form" if scope == "ns_form" else "function"
            args = ["bb", "src/extractor/extract.clj", extract_mode, file_path]
            if extract_mode == "function":
                if not cand.element_name:
                    logger.warning(f"No element_name for {key}, falling back to full file.")
                    candidate_contexts[key] = code
                    cand.snippet = code
                    continue
                args.append(cand.element_name)

            try:
                res = subprocess.run(args, capture_output=True, text=True, check=True)
                extracted = res.stdout.strip()
                candidate_contexts[key] = extracted if extracted else code
                if not extracted:
                    logger.warning(f"Extraction returned empty for {key}, falling back.")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.strip() or e.stdout.strip()
                logger.warning(f"Extraction failed for {key}: {err_msg}. Falling back to full file.")
                candidate_contexts[key] = code
            except FileNotFoundError:
                logger.warning("Extraction failed: 'bb' (Babashka) not found in PATH. Falling back to full file.")
                candidate_contexts[key] = code

            cand.snippet = candidate_contexts[key]

        return {"candidate_contexts": candidate_contexts, "candidates": candidates}

    @staticmethod
    def _node_no_candidates(state: PipelineState) -> dict:
        logger.info("[Orchestrator] No candidates found. Skipping Retrieval and Critic.")
        return {}

    # ── rag-mode judge ───────────────────────────────────────────────────

    def _node_judge_rag(self, state: PipelineState) -> dict:
        candidates = state["candidates"]
        logger.info("[Retrieval] Querying for %d candidate(s)...", len(candidates))
        context_packages, retrieval_latency_ms = self.retriever.run(candidates)
        logger.info("[Retrieval] Done in %.0f ms.", retrieval_latency_ms)

        logger.info("[Critic] Starting judgment...")

        @with_retry(self.max_retries)
        def _run():
            return self.critic.run(
                state["candidate_contexts"], candidates, context_packages, timeout=self.timeout_s,
            )

        try:
            verdicts, crit_response, crit_prompt, crit_sys = _run()
        except MaxRetriesExceeded as exc:
            logger.error("[Critic] Failed after retries: %s", exc)
            raise

        logger.info("[Critic] Produced %d verdict(s).", len(verdicts))
        return {
            "verdicts": verdicts, "crit_response": crit_response,
            "crit_prompt": crit_prompt, "crit_sys": crit_sys,
            "tool_calls": len(candidates), "tool_latency_ms": retrieval_latency_ms,
            "tool_transcript": "", "critic_retries": _run.retries_used,
        }

    # ── agentic-mode judge: agent ⇄ tools cycle lives directly in THIS graph ─

    def _node_prepare_agentic(self, state: PipelineState) -> dict:
        logger.info("[AgenticCritic] Starting judgment (tool-driven retrieval)...")
        self.critic.reset_run(
            file_path=state["file_path"], search_root=state.get("search_root"),
            run_id=state.get("run_id"),
        )
        messages, user_prompt = self.critic.build_initial_messages(
            state["candidate_contexts"], state["candidates"], self.catalog,
        )
        return {
            "messages": messages,
            "crit_prompt": user_prompt,
            "crit_sys": AGENTIC_SYSTEM_PROMPT,
            "critic_attempt": 0,
            "tool_rounds": 0,
            "judge_start_time": time.time(),
        }

    @staticmethod
    def _log_cache_usage(round_label: str, response) -> None:
        """D13 observability: log what the provider reported about prompt
        caching for this call, so cache hits/misses can be checked
        empirically instead of assumed. `cached_tokens`/`cache_read` is what
        was served from cache (reused prefix); `cache_write_tokens`/
        `cache_creation` is what was newly written to cache this call.
        `usage_metadata` is None for providers/errors that don't report
        usage — logged as such rather than skipped silently."""
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            logger.info("[AgenticCritic][cache] %s: no usage_metadata reported.", round_label)
            return
        cache_read, cache_write = cache_tokens_from_langchain_usage(response)
        prompt_tokens = usage.get("input_tokens", 0) or 0
        logger.info(
            "[AgenticCritic][cache] %s: prompt_tokens=%d cached_tokens=%d "
            "cache_write_tokens=%d (%.0f%% of prompt served from cache).",
            round_label, prompt_tokens, cache_read, cache_write,
            (100.0 * cache_read / prompt_tokens) if prompt_tokens else 0.0,
        )

    def _node_agent(self, state: PipelineState) -> dict:
        round_num = state.get("tool_rounds", 0) + 1
        messages = self.critic.with_cache_breakpoint(state["messages"])
        response = self.critic.llm_with_tools.invoke(messages, **self.critic.invoke_kwargs())
        self._log_cache_usage(f"round {round_num}", response)
        self.critic.record_cache_usage(response)
        self.critic.record_cost(response)
        return {
            "messages": [response],
            "tool_rounds": round_num,
        }

    def _route_agent(self, state: PipelineState) -> str:
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return "finalize_agentic"
        max_tool_rounds = getattr(self.critic, "max_tool_rounds", 6)
        if state.get("tool_rounds", 0) >= max_tool_rounds:
            logger.warning(
                "[AgenticCritic] Hit the %d-round tool-call budget with more tool "
                "calls still requested — forcing a final answer from what's "
                "been gathered so far instead of looping further.",
                max_tool_rounds,
            )
            return "force_finalize"
        return "tools"

    def _node_force_finalize(self, state: PipelineState) -> dict:
        """Reached only when the model still wants to call tools after
        exhausting its round budget. Ask for a final answer with tools
        unbound (self.critic._llm, not llm_with_tools) so the model can't
        just request another round — it's structurally unable to."""
        messages = state["messages"] + [HumanMessage(content=(
            "You've used all available tool-call rounds for this candidate "
            "set. Do not call any more tools. Based only on the evidence "
            "already gathered above, respond now with your final JSON "
            "object containing the \"verdicts\" array — one verdict per "
            "candidate, even where the evidence is incomplete (reflect that "
            "in confidence, not by omitting the candidate)."
        ))]
        # No with_cache_breakpoint() here on purpose: this call uses
        # self.critic._llm (tools unbound), a structurally different
        # request shape than llm_with_tools's — it can never hit the cache
        # built up over the tool-bound rounds, and it's this run's last
        # call, so nothing would ever read back a fresh write either.
        # Marking it would just pay the cache-write premium for nothing.
        response = self.critic._llm.invoke(messages, **self.critic.invoke_kwargs())
        self._log_cache_usage("force_finalize", response)
        self.critic.record_cache_usage(response)
        self.critic.record_cost(response)
        return {"messages": [response]}

    def _node_finalize_agentic(self, state: PipelineState) -> dict:
        content = AgenticCriticAgent.extract_final_text(state["messages"])
        attempt = state.get("critic_attempt", 0)

        try:
            verdicts = parse_critic_output(content)
        except MalformedOutputError as exc:
            if attempt >= self.max_retries:
                logger.error("[AgenticCritic] Failed after retries: %s", exc)
                raise MaxRetriesExceeded(
                    f"Exhausted {self.max_retries} retries on agentic critic output. Last error: {exc}"
                ) from exc
            logger.warning(
                "[AgenticCritic] Malformed final output (attempt %d/%d): %s — asking the model to retry.",
                attempt + 1, self.max_retries, str(exc)[:150],
            )
            return {
                "critic_attempt": attempt + 1,
                "agentic_judge_done": False,
                "messages": [HumanMessage(content=(
                    "Your previous response was not valid JSON matching the required "
                    "schema. Respond again with ONLY a valid JSON object containing "
                    "a \"verdicts\" array — no markdown, no extra text."
                ))],
            }

        prompt_tokens, completion_tokens = AgenticCriticAgent.token_usage(state["messages"])
        latency_ms = (time.time() - state.get("judge_start_time", time.time())) * 1000
        crit_response = LLMResponse(
            content=content, model=self.critic.model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens, latency_ms=latency_ms,
        )
        transcript = AgenticCriticAgent.build_transcript(state["messages"])

        logger.info(
            "[AgenticCritic] Made %d tool call(s) (%.0f ms).",
            self.critic.tool_calls, self.critic.tool_latency_ms,
        )
        logger.info("[Critic] Produced %d verdict(s).", len(verdicts))
        return {
            "agentic_judge_done": True,
            "verdicts": verdicts, "crit_response": crit_response,
            "tool_calls": self.critic.tool_calls, "tool_latency_ms": self.critic.tool_latency_ms,
            "tool_transcript": transcript, "critic_retries": attempt,
        }

    @staticmethod
    def _route_after_finalize(state: PipelineState) -> str:
        return END if state["agentic_judge_done"] else "agent"

    # ── Graph assembly ───────────────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("pre_filter", self._node_pre_filter)
        graph.add_node("detect", self._node_detect)
        graph.add_node("extract", self._node_extract)
        graph.add_node("no_candidates", self._node_no_candidates)

        graph.set_entry_point("pre_filter")
        graph.add_edge("pre_filter", "detect")
        graph.add_conditional_edges("detect", self._route_after_detect)
        graph.add_edge("no_candidates", END)

        if self.mode == "rag":
            graph.add_node("judge_rag", self._node_judge_rag)
            graph.add_edge("extract", "judge_rag")
            graph.add_edge("judge_rag", END)
        else:
            graph.add_node("prepare_agentic", self._node_prepare_agentic)
            graph.add_node("agent", self._node_agent)
            graph.add_node("tools", ToolNode(self.critic.tools))
            graph.add_node("force_finalize", self._node_force_finalize)
            graph.add_node("finalize_agentic", self._node_finalize_agentic)

            graph.add_edge("extract", "prepare_agentic")
            graph.add_edge("prepare_agentic", "agent")
            graph.add_conditional_edges("agent", self._route_agent)
            graph.add_edge("tools", "agent")
            graph.add_edge("force_finalize", "finalize_agentic")
            graph.add_conditional_edges("finalize_agentic", self._route_after_finalize)

        return graph.compile()

    # ── Public API ───────────────────────────────────────────────────────

    def run(self, code: str, file_path: str, search_root: Optional[str] = None) -> tuple[RunArtifact, dict]:
        """`search_root`: directory to also search for cross-file function
        lookups in agentic mode (get_function_source). Ignored in rag mode."""
        pipeline_start = time.time()
        run_id = str(uuid.uuid4())

        # This is now a pure safety net, not the real cap: _route_agent
        # forces the agent to `finalize` once `tool_rounds` hits
        # `max_tool_rounds`, so the graph should never actually reach this
        # limit anymore. Kept generous (+ a few steps of slack for
        # force_finalize/retry transitions) so a bug in that enforcement
        # fails loud via GraphRecursionError rather than silently truncating
        # a normal run.
        max_tool_rounds = getattr(self.critic, "max_tool_rounds", 6)
        recursion_limit = 12 + max_tool_rounds * 2 + self.max_retries * 4

        final_state = self._graph.invoke(
            {"code": code, "file_path": file_path, "search_root": search_root, "run_id": run_id},
            config={"recursion_limit": recursion_limit},
        )

        total_latency_ms = (time.time() - pipeline_start) * 1000
        det_response = final_state["det_response"]
        detection_retries = final_state.get("detection_retries", 0)
        detection_metrics = AgentLLMMetrics(
            model=det_response.model,
            prompt_tokens=det_response.prompt_tokens,
            completion_tokens=det_response.completion_tokens,
            total_tokens=det_response.total_tokens,
            latency_ms=det_response.latency_ms,
            retries_used=detection_retries,
            cache_read_tokens=det_response.cache_read_tokens,
            cache_write_tokens=det_response.cache_write_tokens,
            cost=det_response.cost,
        )

        if final_state.get("no_candidates"):
            trace = {
                "detection": {
                    "system_prompt": final_state["det_sys"],
                    "user_prompt": final_state["det_prompt"],
                    "raw_response": det_response.content,
                },
                "critic": {
                    "system_prompt": "SKIPPED",
                    "user_prompt": "SKIPPED",
                    "raw_response": "SKIPPED",
                },
            }
            artifact = RunArtifact(
                run_id=run_id,
                file=file_path,
                agents=AgentsMetrics(
                    detection=detection_metrics,
                    retrieval=AgentRetrievalMetrics(
                        vector_db=self.vectordb_name if self.mode == "rag" else "agentic-tool",
                        calls=0, latency_ms=0.0,
                    ),
                    critic=AgentLLMMetrics(model="skipped", prompt_tokens=0, completion_tokens=0, total_tokens=0, latency_ms=0.0, retries_used=0),
                ),
                total_latency_ms=total_latency_ms,
                retries=detection_retries,
                smell_summary={},
                candidate_smells=[],
                verdicts=[],
            )
            return artifact, trace

        crit_response = final_state["crit_response"]
        critic_retries = final_state.get("critic_retries", 0)
        critic_metrics = AgentLLMMetrics(
            model=crit_response.model,
            prompt_tokens=crit_response.prompt_tokens,
            completion_tokens=crit_response.completion_tokens,
            total_tokens=crit_response.total_tokens,
            latency_ms=crit_response.latency_ms,
            retries_used=critic_retries,
            # D13: 0 for rag mode / non-openrouter providers, since only the
            # agentic OpenRouter path tracks this. Not read from
            # `final_state` — accumulated directly on the critic instance by
            # `record_cache_usage()`, one call per tool-call round.
            cache_read_tokens=getattr(self.critic, "cache_read_tokens", 0),
            cache_write_tokens=getattr(self.critic, "cache_write_tokens", 0),
            cost=getattr(self.critic, "cost", None),
        )
        retrieval_metrics = AgentRetrievalMetrics(
            vector_db=self.vectordb_name if self.mode == "rag" else "agentic-tool",
            calls=final_state["tool_calls"],
            latency_ms=final_state["tool_latency_ms"],
        )

        trace = {
            "detection": {
                "system_prompt": final_state["det_sys"],
                "user_prompt": final_state["det_prompt"],
                "raw_response": det_response.content,
            },
            "critic": {
                "system_prompt": final_state["crit_sys"],
                "user_prompt": final_state["crit_prompt"],
                "raw_response": crit_response.content,
                **({"tool_transcript": final_state["tool_transcript"]} if self.mode == "agentic" else {}),
            },
        }

        verdicts = final_state["verdicts"]
        smell_summary: dict[str, int] = {}
        for v in verdicts:
            if v.confirmed:
                smell_summary[v.smell_id] = smell_summary.get(v.smell_id, 0) + 1

        artifact = RunArtifact(
            run_id=run_id,
            file=file_path,
            agents=AgentsMetrics(detection=detection_metrics, retrieval=retrieval_metrics, critic=critic_metrics),
            total_latency_ms=total_latency_ms,
            retries=detection_retries + critic_retries,
            smell_summary=smell_summary,
            candidate_smells=final_state["candidates"],
            verdicts=verdicts,
        )
        return artifact, trace
