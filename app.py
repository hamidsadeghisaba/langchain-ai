import streamlit as st

from langgraph.types import Command

from workflow import build_graph


st.set_page_config(
    page_title="AI Development Workflow",
    page_icon="🤖",
    layout="wide",
)


# ============================================================
# Session State
# ============================================================

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()

if "config" not in st.session_state:
    st.session_state.config = {
        "configurable": {
            "thread_id": "task-001"
        }
    }

if "result" not in st.session_state:
    st.session_state.result = None

if "running" not in st.session_state:
    st.session_state.running = False


# ============================================================
# Header
# ============================================================

st.title("🤖 AI Development Workflow")

st.caption(
    "LangGraph + Codex + Graphify"
)


# ============================================================
# Story
# ============================================================

story = st.text_area(
    "Story",
    height=150,
    placeholder="Enter the development story...",
)


# ============================================================
# Run Analyzer
# ============================================================

if st.button(
    "▶ Run Analyzer",
    type="primary",
    disabled=not story.strip(),
):

    st.session_state.running = True

    with st.spinner("Analyzer is working..."):

        result = st.session_state.graph.invoke(
            {
                "story": story,
                "analysis": "",
                "development_result": "",
            },
            st.session_state.config,
        )

        st.session_state.result = result
        st.session_state.running = False

    st.rerun()


# ============================================================
# Analyzer Result
# ============================================================

result = st.session_state.result

if result:

    st.divider()

    st.subheader("🔎 Analyzer")

    analysis = result.get(
        "analysis",
        "",
    )

    st.markdown(analysis)


    # ========================================================
    # Human Review
    # ========================================================

    if result.get("__interrupt__"):

        st.divider()

        st.subheader("👤 Human Review")

        st.info(
            "The Analyzer has finished. "
            "Review the analysis before continuing."
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "✅ Approve",
                use_container_width=True,
            ):

                with st.spinner(
                    "Developer is working..."
                ):

                    result = (
                        st.session_state.graph.invoke(
                            Command(
                                resume="approve"
                            ),
                            st.session_state.config,
                        )
                    )

                    st.session_state.result = result

                st.rerun()


        with col2:

            if st.button(
                "❌ Reject",
                use_container_width=True,
            ):

                st.session_state.result = None

                st.error(
                    "Analysis rejected."
                )

                st.rerun()


    # ========================================================
    # Development Result
    # ========================================================

    development_result = result.get(
        "development_result",
        "",
    )

    if development_result:

        st.divider()

        st.subheader("👨‍💻 Developer")

        st.markdown(
            development_result
        )

        st.success(
            "Workflow finished."
        )