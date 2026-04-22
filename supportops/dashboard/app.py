"""Operator dashboard.

Reads tickets from the running FastAPI backend (not directly from the database)
so it works the same whether the backend is pointed at Postgres or the
in-memory store.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import altair as alt
import httpx
import pandas as pd
import streamlit as st


API_BASE = os.environ.get("SUPPORTOPS_API", "http://localhost:8000")


st.set_page_config(page_title="support-ops", layout="wide")
st.title("support-ops — triage dashboard")

with st.sidebar:
    st.subheader("Controls")
    auto_refresh = st.toggle("Auto-refresh every 10s", value=False)
    if st.button("Clear cache"):
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=5)
def fetch_tickets(limit: int = 200) -> list[dict[str, Any]]:
    try:
        r = httpx.get(f"{API_BASE}/tickets", params={"limit": limit}, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        st.error(f"Could not reach backend at {API_BASE}: {exc}")
        return []


@st.cache_data(ttl=10)
def fetch_health() -> dict[str, Any]:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return {}


def _duration_minutes(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return (e - s).total_seconds() / 60.0


health = fetch_health()
if health:
    c1, c2, c3 = st.columns(3)
    c1.metric("Backend", "online")
    c2.metric("Mode", "mock" if health.get("mock_mode") else "live")
    c3.metric("Started", health.get("started_at", "")[:19].replace("T", " "))

st.divider()

tickets = fetch_tickets(limit=500)
if not tickets:
    st.warning("No tickets yet. Hit the POST /tickets endpoint or run the simulator.")
    st.stop()

df = pd.DataFrame(tickets)
df["created_at"] = pd.to_datetime(df["created_at"])
if "triaged_at" in df.columns:
    df["triaged_at"] = pd.to_datetime(df["triaged_at"])
if "resolved_at" in df.columns:
    df["resolved_at"] = pd.to_datetime(df["resolved_at"])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total tickets", len(df))
col2.metric("Open backlog", int((df["status"] == "triaged").sum() + (df["status"] == "open").sum()))

triage_latencies = [
    _duration_minutes(str(r["created_at"]), str(r["triaged_at"])) * 60
    for _, r in df.iterrows()
    if pd.notna(r.get("triaged_at"))
]
col3.metric(
    "Median triage latency",
    f"{int(pd.Series(triage_latencies).median())}s" if triage_latencies else "—",
)

resolved = df[df["status"] == "resolved"]
resolve_minutes = [
    _duration_minutes(str(r["created_at"]), str(r["resolved_at"])) for _, r in resolved.iterrows()
]
col4.metric(
    "Median resolution",
    f"{pd.Series(resolve_minutes).median():.1f} min" if resolve_minutes else "—",
)

st.divider()

left, right = st.columns(2)
with left:
    st.subheader("Category mix")
    if "category" in df.columns:
        cat_df = (
            df.dropna(subset=["category"]).groupby("category").size().reset_index(name="count")
        )
        if not cat_df.empty:
            chart = (
                alt.Chart(cat_df)
                .mark_bar()
                .encode(x=alt.X("category:N", sort="-y"), y="count:Q", tooltip=["category", "count"])
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)

with right:
    st.subheader("Priority + sentiment")
    if "priority" in df.columns and "sentiment" in df.columns:
        cross = (
            df.dropna(subset=["priority", "sentiment"])
            .groupby(["priority", "sentiment"])
            .size()
            .reset_index(name="count")
        )
        if not cross.empty:
            chart = (
                alt.Chart(cross)
                .mark_rect()
                .encode(
                    x="priority:N",
                    y="sentiment:N",
                    color=alt.Color("count:Q", scale=alt.Scale(scheme="blues")),
                    tooltip=["priority", "sentiment", "count"],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)

st.subheader("Recent tickets")
display = df[
    [
        c
        for c in ["id", "created_at", "source", "subject", "category", "priority", "sentiment", "status"]
        if c in df.columns
    ]
].head(50)
st.dataframe(display, use_container_width=True, height=400)

with st.expander("Preview the draft response for a ticket"):
    ids = df["id"].tolist()
    if ids:
        pick = st.selectbox("Ticket", ids)
        row = df[df["id"] == pick].iloc[0]
        st.write(f"**Subject:** {row['subject']}")
        st.write(f"**Body:**\n\n{row['body']}")
        st.write("---")
        st.write(f"**Draft:**\n\n{row.get('draft_response') or '(none)'}")
        if row["status"] != "resolved" and st.button(f"Mark ticket {pick} resolved"):
            try:
                httpx.post(f"{API_BASE}/tickets/{pick}/resolve", timeout=5.0).raise_for_status()
                st.cache_data.clear()
                st.success(f"Ticket {pick} marked resolved")
                st.rerun()
            except httpx.HTTPError as exc:
                st.error(f"Resolve failed: {exc}")


if auto_refresh:
    import time
    time.sleep(10)
    st.cache_data.clear()
    st.rerun()
