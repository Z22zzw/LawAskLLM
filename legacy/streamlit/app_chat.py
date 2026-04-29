from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from app.core import config
from app.experiments.design import EVALUATION_DIMENSIONS, SAMPLE_SET_SUGGESTION, get_experiment_by_id, list_experiment_options
from app.experiments.logger import append_experiment_turn, build_turn_record, export_session_replay
from app.rag import service as rag_service
from ui_styles import inject_chat_css, inject_kb_css
from legacy.streamlit.memory_store import InMemoryChatStore, MySQLMemoryStore
from legacy.streamlit.rag_display import (
    format_retrieval_summary_markdown,
    pack_assistant_content,
    strip_assistant_for_llm,
    unpack_assistant_content,
)

_EXAMPLE_QUESTIONS = [
    ("📝 司考题", "合同的撤销", "下列关于可撤销合同的表述，哪一项是正确的？请结合选项说明考点。"),
    ("⚖️ 罪名判断", "盗窃与量刑", "被告人盗窃他人财物数额较大，又主动退赃，可能涉及哪些罪名与量刑情节？"),
    ("🔍 知识检索", "故意伤害 vs 正当防卫", "刑法中关于故意伤害罪的规定在实务中如何与正当防卫区分？"),
]


def _get_store():
    try:
        store = MySQLMemoryStore()
        store.ensure_tables()
        return store
    except Exception:
        return InMemoryChatStore()


def _load_session_into_state(session_uuid: str):
    rows = st.session_state.store.get_messages(session_uuid)
    st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in rows]
    st.session_state.long_term_summary = st.session_state.store.get_session_summary(session_uuid)
    user_turns = sum(1 for m in st.session_state.messages if m["role"] == "user")
    st.session_state.user_turn_count = user_turns
    st.session_state.user_turns_at_last_summary = user_turns if st.session_state.long_term_summary else 0


def _ensure_state():
    if "store" not in st.session_state:
        st.session_state.store = _get_store()
    if st.session_state.get("create_new_session_request"):
        new_sid = st.session_state.store.create_session()
        st.session_state.active_session_uuid = new_sid
        st.session_state.loaded_session_uuid = None
        st.session_state.create_new_session_request = False
    if "active_session_uuid" not in st.session_state:
        st.session_state.active_session_uuid = st.session_state.store.create_session()
    if "messages" not in st.session_state or st.session_state.get("loaded_session_uuid") != st.session_state.active_session_uuid:
        _load_session_into_state(st.session_state.active_session_uuid)
        st.session_state.loaded_session_uuid = st.session_state.active_session_uuid
    if "last_rag_result" not in st.session_state:
        st.session_state.last_rag_result = None
    if "active_experiment_id" not in st.session_state:
        st.session_state.active_experiment_id = "system_full"


def _chat_history_as_pairs() -> List[Tuple[str, str]]:
    pairs = []
    cur_user = None
    for m in st.session_state.messages:
        if m["role"] == "user":
            cur_user = m["content"]
        elif m["role"] == "assistant" and cur_user is not None:
            pairs.append((cur_user, strip_assistant_for_llm(m["content"])))
            cur_user = None
    return pairs


# ── 右侧面板：命中知识 ──
_RELEVANCE_BADGE = {"strong": "🟢 强相关", "weak": "🟡 弱相关", "unrelated": "⚪ 无关"}


def _render_knowledge_tab(r: Dict[str, Any]) -> None:
    cites = r.get("citations") or []
    stats = r.get("citation_stats") or {}
    total = stats.get("total", len(cites))
    jec_n = stats.get("jec_qa", 0)
    cail_n = stats.get("cail2018", 0)

    rs = r.get("retrieval_summary") or {}
    intent = (rs.get("intent") if isinstance(rs, dict) else "") or ""

    if total > 0:
        st.markdown(f"共命中 **{total}** 条证据（JEC-QA {jec_n} 条、CAIL2018 {cail_n} 条）")
    else:
        if intent == "non_legal":
            st.info("本轮问题被判定为非法律问题，未进行知识库检索。")
        else:
            st.info("本轮未命中知识库中的内容。可能原因：问题与知识库覆盖范围差异较大、向量库未构建、或嵌入模型不一致。")
        return

    qa = rs.get("query_analysis") or {} if isinstance(rs, dict) else {}
    all_kw = list(qa.get("specific_terms") or []) + list(qa.get("broad_topics") or [])

    for c in cites:
        ds = c.get("dataset") or ""
        badge = "📚 JEC-QA" if ds == config.DATASET_JEC_QA else "⚖️ CAIL2018" if ds == config.DATASET_CAIL2018 else "📄 证据"
        ld_c = c.get("legal_domain") or ""
        ld_label = config.LEGAL_DOMAIN_LABELS.get(ld_c, ld_c) if ld_c else ""
        sub = c.get("subject") or ""
        snippet = c.get("snippet", "")

        rel_label = c.get("relevance")
        if rel_label and rel_label in _RELEVANCE_BADGE:
            relevance = _RELEVANCE_BADGE[rel_label]
        else:
            hit_count = sum(1 for kw in all_kw if kw and kw in snippet) if all_kw else 0
            relevance = "🟢 高" if hit_count >= 2 else "🟡 中" if hit_count >= 1 else "⚪ 低"

        with st.container(border=True):
            header_parts = [f"**{badge}**"]
            if ld_label:
                header_parts.append(f"「{ld_label}」")
            if sub:
                header_parts.append(f"科目/罪名：{sub}")
            header_parts.append(f"相关度：{relevance}")
            st.markdown(" · ".join(header_parts))
            st.caption(snippet[:200] + ("…" if len(snippet) > 200 else ""))


# ── 右侧面板：思考过程 ──
def _render_thinking_tab(r: Dict[str, Any]) -> None:
    trace = r.get("chain_trace") or []
    if not trace:
        st.caption("暂无思考过程记录。")
        return

    for i, step in enumerate(trace, start=1):
        step_text = str(step)
        with st.expander(f"第 {i} 步：{step_text[:50]}{'…' if len(step_text) > 50 else ''}", expanded=(i <= 2)):
            st.write(step_text)


# ── 右侧面板：检索分析 ──
def _render_analysis_tab(r: Dict[str, Any]) -> None:
    rs = r.get("retrieval_summary") or {}
    qa = rs.get("query_analysis") or {} if isinstance(rs, dict) else {}
    bridge = rs.get("bridge_context") or "" if isinstance(rs, dict) else ""

    qt = (qa.get("query_type") or "").strip()
    if qt:
        color_map = {"概念解释": "blue", "案例分析": "green", "法条适用": "orange", "对比辨析": "red"}
        color = color_map.get(qt, "gray")
        st.markdown(f"**问题类型**：:{color}[{qt}]")

    terms = qa.get("specific_terms") or []
    topics = qa.get("broad_topics") or []

    if terms:
        st.markdown("**提取的具体术语**")
        st.write(" ".join([f"`{t}`" for t in terms]))
    if topics:
        st.markdown("**识别的宏观主题**")
        st.write(" ".join([f"`{t}`" for t in topics]))

    if not terms and not topics:
        st.caption("本轮未提取到关键词。")

    if bridge:
        st.divider()
        st.markdown("**证据关系分析**")
        st.write(bridge)

    if isinstance(rs, dict) and rs:
        st.divider()
        rp = rs.get("runtime_prefs") or {}
        st.markdown("**实验配置快照**")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("实验预设", rp.get("active_experiment_preset") or "custom")
            st.metric("实际检索策略", rs.get("effective_source_mode") or "—")
            st.metric("知识库覆盖", rs.get("coverage") or "—")
        with c2:
            st.metric("证据总数", (rs.get("citation_stats") or {}).get("total", rs.get("evidence_count", 0)))
            st.metric("是否执行检索", "是" if rs.get("vector_retrieval_ran") else "否")
            st.metric("是否跳过检索", "是" if rs.get("skipped_retrieval") else "否")

        flags = [
            f"MMR={'开' if rp.get('use_mmr') else '关'}",
            f"RRF={'开' if rp.get('use_rrf', True) else '关'}",
            f"证据标注={'开' if rp.get('use_evidence_labels', True) else '关'}",
            f"Agent={'开' if rp.get('use_agent_default') else '关'}",
            f"仅LLM直答={'开' if rp.get('force_direct_llm') else '关'}",
            f"Agent回退={'开' if rp.get('enable_agent_fallback', True) else '关'}",
        ]
        st.caption(" | ".join(flags))

    if isinstance(rs, dict) and rs:
        with st.expander("完整检索摘要", expanded=False):
            st.markdown(format_retrieval_summary_markdown(rs))


# ── 右侧面板入口 ──
def _render_last_result_panel():
    with st.container(border=True):
        st.markdown('<div class="kb-panel-title">检索结果</div>', unsafe_allow_html=True)
        r = st.session_state.last_rag_result
        if not r:
            st.markdown(
                '<div class="kb-empty">'
                '<div class="kb-empty-icon">◎</div>'
                '发送问题后，这里将展示命中的<br/>知识点和思考过程。'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        tab_know, tab_think, tab_analysis = st.tabs(["命中知识", "思考过程", "检索分析"])
        with tab_know:
            _render_knowledge_tab(r)
        with tab_think:
            _render_thinking_tab(r)
        with tab_analysis:
            _render_analysis_tab(r)


def _current_experiment() -> Dict[str, Any]:
    exp_id = st.session_state.get("active_experiment_id", "system_full")
    return get_experiment_by_id(exp_id)


# ── 消息气泡下方的折叠式证据摘要 ──
def _render_rag_expanders(bundle: Optional[Dict[str, Any]], show_rag: bool) -> None:
    if not bundle:
        return
    cites = bundle.get("citations") or []
    if cites:
        n = len(cites)
        with st.expander(f"本条回答基于 {n} 条知识库证据（点击展开）", expanded=False):
            for c in cites:
                ds = c.get("dataset") or ""
                badge = "📚" if ds == config.DATASET_JEC_QA else "⚖️" if ds == config.DATASET_CAIL2018 else "📄"
                sub = c.get("subject") or ""
                snippet = (c.get("snippet") or "")[:120]
                st.caption(f"{badge} {sub}：{snippet}{'…' if len(c.get('snippet', '')) > 120 else ''}")

    if show_rag:
        rs = bundle.get("retrieval_summary")
        if rs:
            with st.expander("检索技术详情", expanded=False):
                st.markdown(format_retrieval_summary_markdown(rs))


def main():
    st.set_page_config(page_title="法律RAG智能问答", layout="wide", initial_sidebar_state="expanded")
    inject_chat_css(st)
    inject_kb_css(st)
    _ensure_state()
    pending = st.session_state.pop("pending_user_msg", None)

    # ── 侧边栏 ──
    st.sidebar.title("法律智能问答")

    st.sidebar.subheader("法律领域")
    domain_codes = [c for c, _ in config.LEGAL_DOMAIN_CHOICES]
    domain_labels = {c: lab for c, lab in config.LEGAL_DOMAIN_CHOICES}
    legal_domain = st.sidebar.selectbox(
        "选择领域",
        options=domain_codes,
        format_func=lambda c: domain_labels.get(c, c),
        key="chat_legal_domain",
        help="选择「综合」则不限领域；选具体领域可缩小检索范围、提高相关性。",
    )

    if st.sidebar.button("新建对话", type="primary"):
        st.session_state.create_new_session_request = True
        st.session_state.last_rag_result = None
        st.rerun()

    st.sidebar.subheader("实验模式")
    exp_options = list_experiment_options()
    exp_ids = [x["id"] for x in exp_options]
    current_exp = st.session_state.get("active_experiment_id", "system_full")
    if current_exp not in exp_ids:
        current_exp = "system_full"
        st.session_state.active_experiment_id = current_exp
    selected_exp = st.sidebar.selectbox(
        "实验预设",
        options=exp_ids,
        index=exp_ids.index(current_exp) if current_exp in exp_ids else 0,
        format_func=lambda eid: next((x["label"] for x in exp_options if x["id"] == eid), eid),
        key="chat_experiment_preset",
        help="用于一键切换基线/策略/消融配置，支持论文实验复现。",
    )
    if selected_exp != st.session_state.active_experiment_id:
        st.session_state.active_experiment_id = selected_exp

    exp_info = _current_experiment()
    if exp_info.get("description"):
        st.sidebar.caption(exp_info["description"])
    with st.sidebar.expander("实验样本与评分建议", expanded=False):
        st.markdown(
            f"- 样本规模：JEC-QA {SAMPLE_SET_SUGGESTION['jec_qa_count']} + "
            f"CAIL2018 {SAMPLE_SET_SUGGESTION['cail2018_count']} + "
            f"边界样本 {SAMPLE_SET_SUGGESTION['boundary_count']}"
        )
        st.markdown(f"- 边界样本类型：`{'` `'.join(SAMPLE_SET_SUGGESTION['boundary_types'])}`")
        st.markdown("**评分维度（0-5分）**")
        for dim in EVALUATION_DIMENSIONS:
            st.markdown(f"- {dim['name']}：{dim['desc']}")

    sessions = st.session_state.store.list_sessions(limit=20)
    session_id_list = [s["session_uuid"] for s in sessions if s.get("session_uuid")]
    if not session_id_list:
        new_sid = st.session_state.store.create_session()
        st.session_state.active_session_uuid = new_sid
        st.session_state.loaded_session_uuid = None
        sessions = st.session_state.store.list_sessions(limit=20)
        session_id_list = [s["session_uuid"] for s in sessions if s.get("session_uuid")]

    if st.session_state.active_session_uuid not in session_id_list and session_id_list:
        st.session_state.active_session_uuid = session_id_list[0]
        st.session_state.loaded_session_uuid = None

    session_label_map: Dict[str, str] = {}
    for s in sessions:
        sid = s.get("session_uuid")
        if sid:
            session_label_map[sid] = (s.get("session_name") or "新对话").strip() or "新对话"

    selected_sid = st.sidebar.selectbox(
        "对话列表",
        options=session_id_list,
        index=session_id_list.index(st.session_state.active_session_uuid) if st.session_state.active_session_uuid in session_id_list else 0,
        format_func=lambda sid: session_label_map.get(sid, sid),
    )

    if selected_sid and selected_sid != st.session_state.active_session_uuid:
        st.session_state.active_session_uuid = selected_sid
        st.session_state.loaded_session_uuid = None
        st.session_state.last_rag_result = None
        st.rerun()

    # 对话管理（折叠）
    with st.sidebar.expander("管理对话", expanded=False):
        try:
            current_name = st.session_state.store.get_session_name(st.session_state.active_session_uuid) or "新对话"
        except Exception:
            current_name = "新对话"

        new_name = st.text_input("对话名称", value=current_name, key="rename_input")
        if st.button("保存名称"):
            name_stripped = (new_name or "").strip()
            if not name_stripped:
                st.error("名称不能为空。")
            else:
                existing_names = {v for k, v in session_label_map.items() if k != st.session_state.active_session_uuid}
                if name_stripped in existing_names:
                    st.error(f"名称「{name_stripped}」已被其他对话使用，请换一个。")
                else:
                    try:
                        st.session_state.store.update_session_name(st.session_state.active_session_uuid, name_stripped)
                        st.session_state.loaded_session_uuid = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存失败：{e}")

        st.divider()
        st.caption("输入「删除」并点击按钮以删除当前对话。")
        delete_confirm = st.text_input("确认", value="", key="delete_confirm")
        if st.button("删除对话", type="secondary", disabled=delete_confirm.strip() != "删除"):
            try:
                st.session_state.store.delete_session(st.session_state.active_session_uuid)
                sessions2 = st.session_state.store.list_sessions(limit=20)
                ids2 = [s["session_uuid"] for s in sessions2 if s.get("session_uuid")]
                st.session_state.active_session_uuid = ids2[0] if ids2 else st.session_state.store.create_session()
                st.session_state.loaded_session_uuid = None
                st.session_state.last_rag_result = None
                st.rerun()
            except Exception as e:
                st.error(f"删除失败：{e}")

        st.divider()
        if st.button("导出会话复盘（jsonl）", type="secondary"):
            try:
                path = export_session_replay(
                    st.session_state.active_session_uuid,
                    st.session_state.messages,
                )
                st.success(f"已导出：{path}")
            except Exception as e:
                st.error(f"导出失败：{e}")

    # 技术细节开关（放在侧边栏最底部）
    show_rag = st.sidebar.toggle(
        "显示技术细节",
        value=False,
        key="chat_show_rag_trace",
        help="开启后在回复下方额外展示检索技术详情。",
    )

    # ── 主内容区 ──
    st.markdown(
        '<div class="rag-hero">'
        '<h1>法律智能问答</h1>'
        '<p>基于 RAG 检索增强生成：系统会先从知识库中检索相关法律知识，再结合大模型生成专业回答。</p>'
        '<div class="rag-hero-chips">'
        '<span class="rag-hero-chip">RAG 检索增强</span>'
        '<span class="rag-hero-chip">法律领域知识库</span>'
        '<span class="rag-hero-chip">多路召回 · 证据标注</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    col_chat, col_side = st.columns([1.7, 1.0], gap="large")

    with col_side:
        _render_last_result_panel()

    chat_area = None
    active_tab_chat = None
    with col_chat:
        tab_chat, tab_hints = st.tabs(["对话", "快速示例"])

        with tab_hints:
            st.markdown("点击下方卡片，会自动发送对应的示例问题。")
            for i, (icon_label, title, question) in enumerate(_EXAMPLE_QUESTIONS):
                with st.container(border=True):
                    st.markdown(f"**{icon_label}　{title}**")
                    st.caption(question[:60])
                    if st.button("发送这个问题", key=f"ex_{i}"):
                        st.session_state.pending_user_msg = question
                        st.rerun()

        with tab_chat:
            active_tab_chat = tab_chat
            chat_area = st.container()
            if not st.session_state.messages:
                st.info("你好！请在下方输入法律问题开始问答。左侧可选择法律领域以缩小检索范围。")

            with chat_area:
                for m in st.session_state.messages:
                    with st.chat_message(m["role"]):
                        if m["role"] == "assistant":
                            vis, bundle = unpack_assistant_content(m["content"])
                            st.markdown(vis)
                            _render_rag_expanders(bundle, show_rag)
                        else:
                            st.markdown(m["content"])

    user_input = pending or st.chat_input("请输入你的法律问题（建议描述具体情境）")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with col_chat:
        with active_tab_chat:
            if chat_area is None:
                chat_area = st.container()
            with chat_area:
                with st.chat_message("user"):
                    st.markdown(user_input)

                with st.chat_message("assistant"):
                    with st.status("正在分析问题并检索知识库…", expanded=True) as chain_status:
                        chain_status.write("正在识别问题意图…")
                        result = rag_service.answer_question(
                            user_input,
                            chat_history=_chat_history_as_pairs(),
                            top_k=config.RETRIEVAL_TOP_K,
                            long_term_summary=st.session_state.long_term_summary,
                            legal_domain=legal_domain,
                            runtime_overrides=_current_experiment().get("overrides") or {},
                        )
                        for step in result.get("chain_trace") or []:
                            chain_status.write(step)
                        n_cites = len(result.get("citations") or [])
                        if n_cites > 0:
                            chain_status.update(label=f"检索完成，命中 {n_cites} 条知识", state="complete")
                        else:
                            chain_status.update(label="分析完成", state="complete")

                    answer = result.get("answer", "")
                    st.markdown(answer)
                    rag_bundle = {
                        "citations": result.get("citations") or [],
                        "retrieval_summary": result.get("retrieval_summary"),
                        "chain_trace": result.get("chain_trace") or [],
                    }
                    _render_rag_expanders(rag_bundle, show_rag)

    st.session_state.last_rag_result = result
    assistant_stored = pack_assistant_content(answer, rag_bundle)
    st.session_state.messages.append({"role": "assistant", "content": assistant_stored})

    try:
        st.session_state.store.save_message(st.session_state.active_session_uuid, "user", user_input)
        st.session_state.store.save_message(st.session_state.active_session_uuid, "assistant", assistant_stored)
    except Exception:
        pass

    try:
        exp_record = build_turn_record(
            session_uuid=st.session_state.active_session_uuid,
            question=user_input,
            legal_domain=legal_domain,
            result=result,
            experiment=_current_experiment(),
        )
        append_experiment_turn(exp_record)
    except Exception:
        pass

    try:
        st.session_state.user_turn_count += 1
        need_update = (
            st.session_state.user_turn_count >= 4
            and (st.session_state.user_turn_count - st.session_state.user_turns_at_last_summary) >= 4
        )
        if need_update:
            pairs = _chat_history_as_pairs()
            summary = rag_service.summarize_for_memory(pairs[-8:], max_turns=8)
            if summary and summary.strip():
                st.session_state.store.update_session_summary(st.session_state.active_session_uuid, summary)
                st.session_state.long_term_summary = summary
                st.session_state.user_turns_at_last_summary = st.session_state.user_turn_count
                try:
                    cur_name = st.session_state.store.get_session_name(st.session_state.active_session_uuid) or "新对话"
                    if cur_name.strip() == "新对话":
                        title = summary.strip().splitlines()[0].strip()[:20]
                        if title:
                            existing_names = set()
                            try:
                                for s in st.session_state.store.list_sessions(limit=50):
                                    n = (s.get("session_name") or "").strip()
                                    if n and s.get("session_uuid") != st.session_state.active_session_uuid:
                                        existing_names.add(n)
                            except Exception:
                                pass
                            if title not in existing_names:
                                st.session_state.store.update_session_name(st.session_state.active_session_uuid, title)
                except Exception:
                    pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
