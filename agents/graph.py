from typing import TypedDict, List, Dict, Any, Annotated
import operator
import os
import time

import streamlit as st
from openai import OpenAI

from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer

from agents.prompts import (
    PLANNER_PROMPT,
    SYNTHESIZER_PROMPT,
    FACT_CHECK_PROMPT,
)
from tools.web_search import web_search
from rag.retriever import retrieve


# ============================================================
# Gemini configuration
# ============================================================

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    MODEL = st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash")
except Exception:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. "
        "Add it to .streamlit/secrets.toml"
    )


client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


# ============================================================
# LangGraph state
# ============================================================

class ResearchState(TypedDict, total=False):
    query: str

    plan: List[str]

    web_results: List[Dict[str, Any]]
    rag_results: List[Dict[str, Any]]

    verification: str

    answer: str
    sources: List[Dict[str, Any]]

    # IMPORTANT:
    # Web Researcher and RAG run in parallel.
    # Each branch contributes its own trace entries.
    trace: Annotated[List[str], operator.add]

    use_web: bool
    use_rag: bool
    verify: bool
    top_k: int


# ============================================================
# Streaming status helper
# ============================================================

def emit_status(
    agent: str,
    status: str,
    message: str,
) -> None:
    """
    Send a custom streaming event to Streamlit.

    Example:
        {
            "agent": "web_researcher",
            "status": "running",
            "message": "Searching the web..."
        }
    """

    writer = get_stream_writer()

    writer(
        {
            "agent": agent,
            "status": status,
            "message": message,
        }
    )


# ============================================================
# Gemini LLM
# ============================================================

def llm(prompt: str) -> str:
    """
    Call Gemini with retries for temporary 429/500/502/503/504 errors.

    Falls back to secondary Flash models if the primary model
    is temporarily unavailable.
    """

    models = [
        MODEL,
        "gemini-3.7-flash",
        "gemini-3.6-flash",
    ]

    last_error = None

    for model in models:
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )

                return response.choices[0].message.content

            except Exception as exc:
                last_error = exc
                error_text = str(exc)

                # Retry temporary server/rate-limit failures.
                if any(
                    code in error_text
                    for code in ["429", "500", "502", "503", "504"]
                ):
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue

                # Don't retry authentication/configuration errors.
                raise

    raise RuntimeError(
        "Gemini is temporarily unavailable after retries. "
        f"Last error: {last_error}"
    )


# ============================================================
# Planner
# ============================================================

def planner_node(state: ResearchState):
    emit_status(
        "planner",
        "running",
        "Decomposing the research question...",
    )

    text = llm(
        PLANNER_PROMPT.format(
            query=state["query"]
        )
    )

    tasks = [
        line.strip("-• ").strip()
        for line in text.splitlines()
        if line.strip()
    ]

    emit_status(
        "planner",
        "complete",
        "Question decomposed.",
    )

    return {
        "plan": tasks[:8],
        "trace": [
            "Planner decomposed the research question."
        ],
    }


# ============================================================
# Web Researcher
# ============================================================

def web_node(state: ResearchState):
    if not state.get("use_web", True):
        emit_status(
            "web_researcher",
            "skipped",
            "Web research disabled.",
        )

        return {
            "web_results": [],
            "trace": [
                "Web research skipped."
            ],
        }

    emit_status(
        "web_researcher",
        "running",
        "Searching the web...",
    )

    results = web_search(
        state["query"],
        max_results=6,
    )

    emit_status(
        "web_researcher",
        "complete",
        f"{len(results)} sources retrieved.",
    )

    return {
        "web_results": results,
        "trace": [
            f"Web researcher collected {len(results)} sources."
        ],
    }


# ============================================================
# Private RAG Researcher
# ============================================================

def rag_node(state: ResearchState):
    if not state.get("use_rag", True):
        emit_status(
            "rag_researcher",
            "skipped",
            "Private-document RAG disabled.",
        )

        return {
            "rag_results": [],
            "trace": [
                "Private-document RAG skipped."
            ],
        }

    emit_status(
        "rag_researcher",
        "running",
        "Searching private documents...",
    )

    results = retrieve(
        state["query"],
        top_k=state.get("top_k", 5),
    )

    emit_status(
        "rag_researcher",
        "complete",
        f"{len(results)} document chunks retrieved.",
    )

    return {
        "rag_results": results,
        "trace": [
            f"RAG retriever returned {len(results)} document chunks."
        ],
    }


# ============================================================
# Fact Checker
# ============================================================

def fact_check_node(state: ResearchState):
    if not state.get("verify", True):
        emit_status(
            "fact_checker",
            "skipped",
            "Fact checking disabled.",
        )

        return {
            "verification": "Fact checking was disabled.",
            "trace": [
                "Fact checking skipped."
            ],
        }

    emit_status(
        "fact_checker",
        "running",
        "Checking claims against retrieved evidence...",
    )

    web_evidence = "\n\n".join(
        (
            f"SOURCE: {x.get('title', '')}\n"
            f"URL: {x.get('url', '')}\n"
            f"TEXT: {x.get('snippet', '')}"
        )
        for x in state.get("web_results", [])
    )

    rag_evidence = "\n\n".join(
        (
            f"DOCUMENT: {x.get('source', '')}\n"
            f"TEXT: {x.get('text', '')}"
        )
        for x in state.get("rag_results", [])
    )

    evidence = (
        web_evidence
        + "\n\n"
        + rag_evidence
    )

    verification = llm(
        FACT_CHECK_PROMPT.format(
            query=state["query"],
            evidence=evidence[:30000],
        )
    )

    emit_status(
        "fact_checker",
        "complete",
        "Evidence checked.",
    )

    return {
        "verification": verification,
        "trace": [
            "Verification agent checked claims against retrieved evidence."
        ],
    }


# ============================================================
# Synthesizer
# ============================================================

def synthesize_node(state: ResearchState):
    emit_status(
        "synthesizer",
        "running",
        "Writing the final research report...",
    )

    web = "\n\n".join(
        (
            f"[WEB {i + 1}] {x.get('title', '')}\n"
            f"URL: {x.get('url', '')}\n"
            f"{x.get('snippet', '')}"
        )
        for i, x in enumerate(
            state.get("web_results", [])
        )
    )

    rag = "\n\n".join(
        (
            f"[DOC {i + 1}] {x.get('source', '')}\n"
            f"{x.get('text', '')}"
        )
        for i, x in enumerate(
            state.get("rag_results", [])
        )
    )

    prompt = SYNTHESIZER_PROMPT.format(
        query=state["query"],
        plan="\n".join(
            f"- {x}"
            for x in state.get("plan", [])
        ),
        web=web[:22000],
        rag=rag[:18000],
        verification=state.get(
            "verification",
            "Not available",
        ),
    )

    answer = llm(prompt)

    sources = []
    seen = set()

    for item in state.get("web_results", []):
        url = item.get("url")

        if url and url not in seen:
            sources.append(item)
            seen.add(url)

    emit_status(
        "synthesizer",
        "complete",
        "Final report ready.",
    )

    return {
        "answer": answer,
        "sources": sources,
        "trace": [
            "Synthesizer produced the grounded final report."
        ],
    }


# ============================================================
# Graph definition
# ============================================================

def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node(
        "planner",
        planner_node,
    )

    graph.add_node(
        "web_researcher",
        web_node,
    )

    graph.add_node(
        "rag_researcher",
        rag_node,
    )

    graph.add_node(
        "fact_checker",
        fact_check_node,
    )

    graph.add_node(
        "synthesizer",
        synthesize_node,
    )

    # --------------------------------------------------------
    # Planner runs first
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "planner",
    )

    # --------------------------------------------------------
    # PARALLEL FAN-OUT
    #
    # Both Web Researcher and RAG start after Planner.
    # --------------------------------------------------------

    graph.add_edge(
        "planner",
        "web_researcher",
    )

    graph.add_edge(
        "planner",
        "rag_researcher",
    )

    # --------------------------------------------------------
    # PARALLEL FAN-IN
    #
    # Fact Checker waits for BOTH branches.
    # --------------------------------------------------------

    graph.add_edge(
        [
            "web_researcher",
            "rag_researcher",
        ],
        "fact_checker",
    )

    # --------------------------------------------------------
    # Final sequential stages
    # --------------------------------------------------------

    graph.add_edge(
        "fact_checker",
        "synthesizer",
    )

    graph.add_edge(
        "synthesizer",
        END,
    )

    return graph.compile()


GRAPH = build_graph()


# ============================================================
# Streaming research entry point
# ============================================================

def stream_research(
    query: str,
    use_web: bool = True,
    use_rag: bool = True,
    verify: bool = True,
    top_k: int = 5,
):
    """
    Stream LangGraph execution events.

    Stream modes:

    - "updates":
        Emits state updates after nodes execute.

    - "custom":
        Emits live status events from emit_status().
    """

    initial: ResearchState = {
        "query": query,
        "use_web": use_web,
        "use_rag": use_rag,
        "verify": verify,
        "top_k": top_k,
        "trace": [],
    }

    yield from GRAPH.stream(
        initial,
        stream_mode=[
            "updates",
            "custom",
        ],
        version="v2",
    )