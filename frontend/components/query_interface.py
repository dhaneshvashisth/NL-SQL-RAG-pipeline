
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime


def render_role_badge(role: str) -> str:
    """Returns colored role badge HTML."""
    colors = {
        "admin":      "#e74c3c",
        "supervisor": "#f39c12",
        "agent":      "#27ae60"
    }
    color = colors.get(role, "#666")
    return f"""
    <span style='
        background-color: {color};
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    '>{role.upper()}</span>
    """


def render_metric_card(label: str, value: str, delta: str = None):
    """Renders a styled metric card."""
    st.metric(label=label, value=value, delta=delta)


def render_sidebar(api_client) -> None:
    """
    Sidebar shows:
    - Logged in user + role
    - System status
    - Sample questions for the role
    - Logout button
    """
    with st.sidebar:
        st.markdown("### 👤 Logged In As")
        st.markdown(
            render_role_badge(st.session_state.role),
            unsafe_allow_html=True
        )
        st.markdown(f"**{st.session_state.full_name}**")
        st.divider()

        st.markdown("### 🔌 System Status")
        health = api_client.health_check()
        if health["success"]:
            st.success("✅ API Online")
            cache_status = health["data"].get("cache_status", "unknown")
            if cache_status == "healthy":
                st.success("✅ Redis Cache")
            else:
                st.warning("⚠️ Redis Cache")
        else:
            st.error("❌ API Offline")

        st.divider()

        st.markdown("### 💡 Try These Questions")
        role = st.session_state.role

        if role == "admin":
            samples = [
                "how many total transactions this week",
                "show total deposits by platform",
                "which agent has the most transactions",
                "compare completed vs pending transactions",
                "show daily transaction summary for last 7 days",
                "which platform has highest failure rate",
            ]
        elif role == "supervisor":
            samples = [
                "show my team's total transactions",
                "which of my agents has most deposits",
                "show pending transactions for my team",
                "compare my agents performance",
                "total withdrawal amount for my team",
            ]
        else:  # agent
            samples = [
                "show all my transactions",
                "what is my total deposit amount",
                "show my pending transactions",
                "how many transactions did I process",
                "show my transactions for 4RABET platform",
            ]

        for sample in samples:
            if st.button(
                f"💬 {sample}",
                key=f"sample_{sample[:20]}",
                use_container_width=True
            ):
                st.session_state.pending_question = sample
                st.rerun()

        st.divider()

        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            api_client.clear_token()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def render_chat_message(role: str, content: str, metadata: dict = None):
    """
    Renders a single chat message.
    role = "user" or "assistant"
    metadata = SQL, timing, cache info etc.
    """
    with st.chat_message(role):
        st.markdown(content)

        if metadata and role == "assistant":
            if metadata.get("generated_sql"):
                with st.expander("🔍 Generated SQL", expanded=False):
                    st.code(metadata["generated_sql"], language="sql")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                cache_icon = "⚡" if metadata.get("was_cache_hit") else "🔄"
                cache_text = "Cache Hit" if metadata.get("was_cache_hit") else "Pipeline Run"
                st.caption(f"{cache_icon} {cache_text}")
            with col2:
                st.caption(f"⏱️ {metadata.get('execution_time_ms', 0)}ms")
            with col3:
                st.caption(f"📊 {metadata.get('row_count', 0)} rows")
            with col4:
                st.caption(f"🔐 {metadata.get('role', '').upper()}")


def render_query_interface(api_client) -> None:
    """
    Main query interface — chat + history + analytics.
    """
    render_sidebar(api_client)

    col_title, col_role = st.columns([3, 1])
    with col_title:
        st.title("ARGUS | NL-SQL RAG Agent")
        st.caption("Ask questions in plain English — get SQL-powered answers")
    with col_role:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            render_role_badge(st.session_state.role),
            unsafe_allow_html=True
        )

    tab_chat, tab_history, tab_about = st.tabs([
        "💬 Ask Questions",
        "📜 Query History",
        "🏗️ How It Works"
    ])

    with tab_chat:

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        if not st.session_state.chat_history:
            with st.chat_message("assistant"):
                st.markdown(f"""
                👋 Welcome **{st.session_state.username}**!

                You're logged in as **{st.session_state.role.upper()}**.
                {_get_role_description(st.session_state.role)}

                Ask me anything about your transaction data!
                """)

        for message in st.session_state.chat_history:
            render_chat_message(
                role=message["role"],
                content=message["content"],
                metadata=message.get("metadata")
            )

        pending = st.session_state.pop("pending_question", None)

        user_input = st.chat_input(
            "Ask a question about your data...",
            key="chat_input"
        )

        question = pending or user_input

        if question:
            st.session_state.chat_history.append({
                "role": "user",
                "content": question
            })

            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("🔄 Running pipeline..."):
                    result = api_client.query(question)

                if result["success"]:
                    data = result["data"]
                    answer = data["answer"]
                    metadata = {
                        "generated_sql":    data.get("generated_sql"),
                        "was_cache_hit":    data.get("was_cache_hit", False),
                        "execution_time_ms": data.get("execution_time_ms", 0),
                        "row_count":        data.get("row_count", 0),
                        "role":             data.get("role", "")
                    }

                    st.markdown(answer)

                    if metadata["generated_sql"]:
                        with st.expander("🔍 Generated SQL", expanded=False):
                            st.code(
                                metadata["generated_sql"],
                                language="sql"
                            )

                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        cache_icon = "⚡ Cache Hit" if metadata["was_cache_hit"] else "🔄 Live Query"
                        st.caption(cache_icon)
                    with m2:
                        st.caption(f"⏱️ {metadata['execution_time_ms']}ms")
                    with m3:
                        st.caption(f"📊 {metadata['row_count']} rows returned")
                    with m4:
                        st.caption(f"🔐 {metadata['role'].upper()}")

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "metadata": metadata
                    })

                else:
                    error_msg = f"❌ {result['error']}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg
                    })

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat", use_container_width=False):
                st.session_state.chat_history = []
                st.rerun()

    with tab_history:
        st.subheader("📜 Recent Query History")

        col_refresh, col_limit = st.columns([1, 1])
        with col_limit:
            limit = st.selectbox("Show last", [10, 25, 50], index=0)

        with col_refresh:
            refresh = st.button("🔄 Refresh", use_container_width=True)

        history_result = api_client.get_history(limit=limit)

        if history_result["success"]:
            history = history_result["data"].get("history", [])

            if not history:
                st.info("No query history yet. Ask some questions!")
            else:
                df = pd.DataFrame(history)

                if len(df) >= 3:
                    st.subheader("📊 Pipeline Analytics")

                    chart_col1, chart_col2 = st.columns(2)

                    with chart_col1:
                        if "was_cache_hit" in df.columns:
                            cache_counts = df["was_cache_hit"].value_counts()
                            labels = ["Cache Hit" if v else "Pipeline Run"
                                     for v in cache_counts.index]
                            fig_cache = go.Figure(data=[
                                go.Pie(
                                    labels=labels,
                                    values=cache_counts.values,
                                    hole=0.4,
                                    marker_colors=["#27ae60", "#3498db"]
                                )
                            ])
                            fig_cache.update_layout(
                                title="Cache Hit Rate",
                                showlegend=True,
                                height=300,
                                margin=dict(t=40, b=0, l=0, r=0)
                            )
                            st.plotly_chart(
                                fig_cache,
                                use_container_width=True
                            )

                    with chart_col2:
                        if "execution_time_ms" in df.columns:
                            fig_time = px.bar(
                                df.head(10),
                                x=df.head(10).index,
                                y="execution_time_ms",
                                title="Response Time (ms) — Last 10 Queries",
                                color="was_cache_hit" if "was_cache_hit" in df.columns else None,
                                color_discrete_map={
                                    True: "#27ae60",
                                    False: "#3498db"
                                },
                                labels={
                                    "execution_time_ms": "Time (ms)",
                                    "was_cache_hit": "Cache Hit"
                                }
                            )
                            fig_time.update_layout(
                                height=300,
                                margin=dict(t=40, b=0, l=0, r=0)
                            )
                            st.plotly_chart(
                                fig_time,
                                use_container_width=True
                            )

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Total Queries", len(df))
                with m2:
                    if "was_cache_hit" in df.columns:
                        hit_rate = df["was_cache_hit"].mean() * 100
                        st.metric("Cache Hit Rate", f"{hit_rate:.0f}%")
                with m3:
                    if "execution_time_ms" in df.columns:
                        avg_time = df["execution_time_ms"].mean()
                        st.metric("Avg Response Time", f"{avg_time:.0f}ms")
                with m4:
                    if "row_count" in df.columns:
                        total_rows = df["row_count"].sum()
                        st.metric("Total Rows Returned", int(total_rows))

                st.divider()

                st.subheader("Query Log")

                display_cols = [
                    c for c in [
                        "username", "role",
                        "natural_language_query",
                        "was_cache_hit",
                        "execution_time_ms",
                        "row_count",
                        "created_at"
                    ] if c in df.columns
                ]

                st.dataframe(
                    df[display_cols],
                    use_container_width=True,
                    column_config={
                        "natural_language_query": st.column_config.TextColumn(
                            "Question", width="large"
                        ),
                        "was_cache_hit": st.column_config.CheckboxColumn(
                            "Cache Hit"
                        ),
                        "execution_time_ms": st.column_config.NumberColumn(
                            "Time (ms)"
                        ),
                        "row_count": st.column_config.NumberColumn(
                            "Rows"
                        ),
                    },
                    hide_index=True
                )

                st.subheader("Generated SQL Details")
                for i, row in df.head(5).iterrows():
                    q = row.get("natural_language_query", "")[:50]
                    sql = row.get("generated_sql", "No SQL recorded")
                    with st.expander(f"Q: {q}..."):
                        st.code(sql or "No SQL", language="sql")

        else:
            st.error(f"Could not load history: {history_result['error']}")

    with tab_about:
        st.subheader("🏗️ System Architecture")

        st.markdown("""
        This system converts natural language questions into role-scoped
        PostgreSQL queries using a 5-node LangGraph pipeline.
        """)

        st.markdown("### Pipeline Flow")
        st.code("""
User Question: "show me pending transactions"
        ↓
[Node 1] Schema Retrieval
  → Embed question with text-embedding-3-small
  → Search Qdrant for relevant table schemas (top-3)
  → Retrieved: transactions_table, users_table
        ↓
[Node 2] SQL Generation
  → GPT-4o-mini + schema context + few-shot examples
  → temperature=0 for deterministic output
  → Generated: SELECT t.id, t.amount... FROM transactions t...
        ↓
[Node 3] SQL Validation + RBAC
  → Check for forbidden keywords (DROP, DELETE, etc.)
  → Verify SELECT only
  → Inject role-based WHERE clause:
    Admin      → no filter
    Supervisor → AND agent_id IN (SELECT id FROM users WHERE parent_id=2)
    Agent      → AND agent_id = 4
        ↓
[Node 4] SQL Execution
  → asyncpg connection pool
  → Non-blocking PostgreSQL query
  → Returns rows as list of dicts
        ↓
[Node 5] Response Formatting
  → GPT-4o-mini formats raw rows into natural language
  → "There are 3 pending transactions totaling $2,318.51"
        ↓
Final Response → User
        """, language="text")

        st.markdown("### 🛠️ Tech Stack")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            | Component | Technology |
            |-----------|-----------|
            | Pipeline  | LangGraph StateGraph |
            | LLM       | GPT-4o-mini |
            | Embeddings | text-embedding-3-small |
            | Vector DB | Qdrant |
            | Cache     | Redis (semantic) |
            """)

        with col2:
            st.markdown("""
            | Component | Technology |
            |-----------|-----------|
            | Database  | PostgreSQL 16 |
            | DB Driver | asyncpg |
            | API       | FastAPI |
            | Auth      | OAuth2 + JWT |
            | Frontend  | Streamlit |
            """)

        # RBAC explanation
        st.markdown("### 🔐 Role-Based Access Control")
        st.markdown("""
        Access is enforced at the **SQL query level**, not just the UI:

        | Role | Data Access | WHERE Clause Injected |
        |------|------------|----------------------|
        | Admin | All transactions, all agents | None (full access) |
        | Supervisor | Their team's transactions only | `agent_id IN (SELECT id FROM users WHERE parent_id = supervisor_id)` |
        | Agent | Own transactions only | `agent_id = agent_id` |

        Even if a user crafts a malicious prompt, the validation node
        enforces access rules before any SQL reaches the database.
        """)


def _get_role_description(role: str) -> str:
    """Returns role-specific description for welcome message."""
    descriptions = {
        "admin": "You have **full access** to all transactions, agents, and platforms.",
        "supervisor": "You can see transactions for **your team's agents** only.",
        "agent": "You can query **your own transactions** only."
    }
    return descriptions.get(role, "")