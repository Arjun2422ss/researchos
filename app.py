import streamlit as st

from agents.graph import stream_research
from rag.ingestion import ingest_files
from rag.store import get_collection_stats


# ============================================================
# Page configuration
# ============================================================

st.set_page_config(
    page_title="ResearchOS",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Existing styling
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    .small-muted {
        color: #6b7280;
        font-size: 0.9rem;
    }

    .agent-card {
        padding: 0.8rem 1rem;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        margin-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Session state
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "sources" not in st.session_state:
    st.session_state.sources = []


# ============================================================
# Header
# ============================================================

st.title("🔬 ResearchOS")

st.caption(
    "Multi-agent GenAI research assistant with web research, "
    "RAG, verification, and citations."
)


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:

    st.header("Knowledge Base")

    uploads = st.file_uploader(
        "Upload PDF/TXT/MD files",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )

    if st.button(
        "📥 Index documents",
        use_container_width=True,
    ):
        if not uploads:
            st.warning(
                "Upload at least one document first."
            )
        else:
            with st.spinner(
                "Indexing documents..."
            ):
                result = ingest_files(uploads)

            st.success(
                f"Indexed {result['chunks']} chunks "
                f"from {result['files']} file(s)."
            )

    stats = get_collection_stats()

    st.caption(
        f"Indexed chunks: {stats}"
    )

    st.divider()

    st.header("Research settings")

    use_web = st.checkbox(
        "🌐 Web research",
        value=True,
    )

    use_rag = st.checkbox(
        "📚 Private-document RAG",
        value=True,
    )

    verify = st.checkbox(
        "✅ Fact checking",
        value=True,
    )

    top_k = st.slider(
        "RAG top-k",
        2,
        10,
        5,
    )

    st.divider()

    # Updated for Gemini.
    # No stale OPENAI_API_KEY reference.
    st.caption(
        "Required: GEMINI_API_KEY"
    )

    st.caption(
        "Optional for web research: TAVILY_API_KEY"
    )


# ============================================================
# Research question
# ============================================================

st.subheader(
    "What do you want to research?"
)

query = st.text_area(
    "Research question",
    placeholder=(
        "Example: Compare the EU AI Act and the US AI "
        "regulatory approach for startups. Identify major "
        "differences, evidence, and practical implications."
    ),
    height=120,
    label_visibility="collapsed",
)


# ============================================================
# Research button
# ============================================================

col1, col2 = st.columns(
    [1, 5]
)

with col1:
    run = st.button(
        "🚀 Research",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# Pipeline rendering
# ============================================================

def render_pipeline(
    statuses,
    placeholder,
):
    """
    Render the current state of every agent.

    This updates the same Streamlit placeholder
    rather than creating a new block on every event.
    """

    agent_order = [
        "planner",
        "web_researcher",
        "rag_researcher",
        "fact_checker",
        "synthesizer",
    ]

    icons = {
        "waiting": "○",
        "running": "◉",
        "complete": "✓",
        "skipped": "–",
        "error": "✕",
    }

    lines = []

    for agent in agent_order:

        item = statuses[agent]

        icon = icons.get(
            item["status"],
            "○",
        )

        lines.append(
            f"{icon} **{item['label']}** — "
            f"{item['message']}"
        )

    placeholder.markdown(
        "\n\n".join(lines)
    )


# ============================================================
# Research execution
# ============================================================

if run:

    if not query.strip():
        st.error(
            "Enter a research question."
        )
        st.stop()

    # --------------------------------------------------------
    # Initial pipeline state
    # --------------------------------------------------------

    statuses = {

        "planner": {
            "label": "Planner",
            "status": "waiting",
            "message": "Waiting",
        },

        "web_researcher": {
            "label": "Web Researcher",
            "status": (
                "waiting"
                if use_web
                else "skipped"
            ),
            "message": (
                "Waiting"
                if use_web
                else "Web research disabled."
            ),
        },

        "rag_researcher": {
            "label": "Private RAG",
            "status": (
                "waiting"
                if use_rag
                else "skipped"
            ),
            "message": (
                "Waiting"
                if use_rag
                else "Private-document RAG disabled."
            ),
        },

        "fact_checker": {
            "label": "Fact Checker",
            "status": (
                "waiting"
                if verify
                else "skipped"
            ),
            "message": (
                "Waiting"
                if verify
                else "Fact checking disabled."
            ),
        },

        "synthesizer": {
            "label": "Synthesizer",
            "status": "waiting",
            "message": "Waiting",
        },
    }

    # --------------------------------------------------------
    # Placeholder for live pipeline
    # --------------------------------------------------------

    pipeline = st.empty()

    render_pipeline(
        statuses,
        pipeline,
    )

    # --------------------------------------------------------
    # We'll reconstruct the final graph state from updates.
    # --------------------------------------------------------

    final_state = {}

    try:

        for chunk in stream_research(
            query=query.strip(),
            use_web=use_web,
            use_rag=use_rag,
            verify=verify,
            top_k=top_k,
        ):

            # =================================================
            # CUSTOM EVENTS
            #
            # These are emitted immediately by each node:
            #
            #   running
            #   complete
            #   skipped
            # =================================================

            if chunk["type"] == "custom":

                event = chunk["data"]

                agent = event["agent"]

                statuses[agent]["status"] = (
                    event["status"]
                )

                statuses[agent]["message"] = (
                    event["message"]
                )

                render_pipeline(
                    statuses,
                    pipeline,
                )

            # =================================================
            # STATE UPDATES
            #
            # These arrive after a node returns its state.
            # =================================================

            elif chunk["type"] == "updates":

                updates = chunk["data"]

                for node_name, update in updates.items():

                    # -----------------------------------------
                    # Accumulate final state
                    # -----------------------------------------

                    for key, value in update.items():

                        if key == "trace":

                            existing_trace = (
                                final_state.get(
                                    "trace",
                                    [],
                                )
                            )

                            final_state["trace"] = (
                                existing_trace
                                + value
                            )

                        else:
                            final_state[key] = value

                    # -----------------------------------------
                    # Safety: reflect completion even if
                    # custom event ordering is unusual.
                    # -----------------------------------------

                    if node_name == "planner":

                        statuses["planner"][
                            "status"
                        ] = "complete"

                        statuses["planner"][
                            "message"
                        ] = "Question decomposed."

                    elif node_name == "web_researcher":

                        if use_web:

                            count = len(
                                update.get(
                                    "web_results",
                                    [],
                                )
                            )

                            statuses[
                                "web_researcher"
                            ]["status"] = "complete"

                            statuses[
                                "web_researcher"
                            ]["message"] = (
                                f"{count} sources retrieved."
                            )

                    elif node_name == "rag_researcher":

                        if use_rag:

                            count = len(
                                update.get(
                                    "rag_results",
                                    [],
                                )
                            )

                            statuses[
                                "rag_researcher"
                            ]["status"] = "complete"

                            statuses[
                                "rag_researcher"
                            ]["message"] = (
                                f"{count} document chunks retrieved."
                            )

                    elif node_name == "fact_checker":

                        if verify:

                            statuses[
                                "fact_checker"
                            ]["status"] = "complete"

                            statuses[
                                "fact_checker"
                            ]["message"] = (
                                "Evidence checked."
                            )

                    elif node_name == "synthesizer":

                        statuses[
                            "synthesizer"
                        ]["status"] = "complete"

                        statuses[
                            "synthesizer"
                        ]["message"] = (
                            "Final report ready."
                        )

                    render_pipeline(
                        statuses,
                        pipeline,
                    )

        # =====================================================
        # Final report
        # =====================================================

        st.markdown(
            "## 📑 Research report"
        )

        st.markdown(
            final_state["answer"]
        )

        # =====================================================
        # Sources
        # =====================================================

        if final_state.get("sources"):

            st.markdown(
                "## 📚 Sources"
            )

            for i, source in enumerate(
                final_state["sources"],
                1,
            ):

                title = source.get(
                    "title",
                    "Source",
                )

                url = source.get(
                    "url",
                    "",
                )

                snippet = source.get(
                    "snippet",
                    "",
                )

                if url:

                    st.markdown(
                        f"**[{i}] "
                        f"[{title}]({url})**"
                    )

                else:

                    st.markdown(
                        f"**[{i}] {title}**"
                    )

                if snippet:

                    st.caption(
                        snippet[:600]
                    )

        # =====================================================
        # Verification
        # =====================================================

        if final_state.get(
            "verification"
        ):

            with st.expander(
                "🔎 Verification details"
            ):

                st.markdown(
                    final_state[
                        "verification"
                    ]
                )

        # =====================================================
        # Agent trace
        # =====================================================

        with st.expander(
            "🧠 Agent trace"
        ):

            for step in final_state.get(
                "trace",
                [],
            ):

                st.markdown(
                    f"- {step}"
                )

    except Exception as exc:

        # Update visible pipeline
        # instead of only showing a generic spinner error.

        st.error(
            "Research failed."
        )

        st.exception(
            exc
        )


# ============================================================
# Footer
# ============================================================

st.divider()

st.caption(
    "ResearchOS is a portfolio/demo system. "
    "Always verify high-stakes claims against primary sources."
)