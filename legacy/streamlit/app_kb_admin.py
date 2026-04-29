import traceback

import streamlit as st

from app.core import config
from app.knowledge.kb_update import update_vector_store_from_cail2018, update_vector_store_from_jec_qa
from app.rag.prefs import load_rag_prefs, save_rag_prefs
from ui_styles import inject_kb_css


def _count_vector_db():
    """返回向量库大致状态：(是否存在, 文件大小MB)"""
    db_dir = config.VECTOR_DB_DIR
    if not db_dir.exists():
        return False, 0
    sqlite_path = db_dir / "chroma.sqlite3"
    if not sqlite_path.exists():
        return False, 0
    size_mb = round(sqlite_path.stat().st_size / (1024 * 1024), 1)
    return True, size_mb


def _count_dataset_lines(path, max_scan=50000):
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for _ in f:
            count += 1
            if count >= max_scan:
                return count
    return count


def main():
    st.set_page_config(page_title="知识库构建", layout="wide")
    inject_kb_css(st)

    st.markdown(
        '<div style="background:linear-gradient(120deg,#0f3d5c,#1a5f8a);color:#fff;'
        'padding:1.15rem 1.3rem;border-radius:12px;margin-bottom:1rem;">'
        "<h2 style='margin:0 0 .25rem 0;color:#fff;'>知识库构建</h2>"
        "<p style='margin:0;opacity:.92;font-size:.95rem;'>"
        "选择数据集并构建向量知识库，构建完成后即可在对话页进行法律问答检索。</p></div>",
        unsafe_allow_html=True,
    )

    # ── 向量库状态 ──
    db_exists, db_size = _count_vector_db()
    st.subheader("当前向量库状态")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("状态", "已构建" if db_exists else "未构建")
    with c2:
        st.metric("数据库大小", f"{db_size} MB" if db_exists else "—")
    with c3:
        st.metric("嵌入模型", "text-embedding-v3")

    if not db_exists:
        st.warning("向量库尚未构建，请在下方选择数据集后点击「全量构建」。")
    else:
        st.info(
            f"向量库已存在（{db_size} MB）。如需更换嵌入模型或重新入库，请点击「全量构建」（会清空旧数据）。"
        )

    st.divider()

    # ── 数据集选择 ──
    st.subheader("选择要入库的数据集")

    # JEC-QA
    with st.container(border=True):
        st.markdown("**📚 JEC-QA — 司法考试题库**")
        st.caption("包含司法考试风格的选择题，涵盖刑法、民法、行政法等多个法律领域。每道题有题干和选项。")

        jec_files = {
            "0_train.json": "训练集（题型0）",
            "1_train.json": "训练集（题型1）",
            "0_test.json": "测试集（题型0）",
            "1_test.json": "测试集（题型1）",
        }
        use_jec = st.checkbox("入库 JEC-QA 数据集", value=True, key="use_jec")

        if use_jec:
            st.markdown("选择要入库的文件：")
            jec_selected = []
            cols = st.columns(4)
            for i, (fn, label) in enumerate(jec_files.items()):
                fp = config.JEC_QA_DIR / fn
                exists = fp.exists()
                line_count = _count_dataset_lines(fp, 50000) if exists else 0
                with cols[i]:
                    checked = st.checkbox(
                        f"{label}",
                        value=exists,
                        disabled=not exists,
                        key=f"jec_{fn}",
                        help=f"文件：{fn}，约 {line_count} 条" if exists else f"{fn} 不存在",
                    )
                    if exists:
                        st.caption(f"约 {line_count} 条")
                    if checked and exists:
                        jec_selected.append(fn)

            jec_max = st.number_input(
                "每个文件最多入库条数（0 = 不限制）",
                min_value=0, step=500, value=0, key="jec_max",
                help="设为 500 可快速试验；设为 0 则全量入库。",
            )
        else:
            jec_selected = []
            jec_max = 0

    # CAIL2018
    with st.container(border=True):
        st.markdown("**⚖️ CAIL2018 — 刑事案情与罪名**")
        st.caption("中国AI与法律挑战赛数据集，包含真实刑事案情摘要及对应罪名标签。")

        cail_files = {
            "train.txt": "训练集",
            "dev.txt": "验证集",
            "test.txt": "测试集",
        }
        use_cail = st.checkbox("入库 CAIL2018 数据集", value=False, key="use_cail")

        if use_cail:
            st.markdown("选择要入库的文件：")
            cail_selected = []
            cols = st.columns(3)
            for i, (fn, label) in enumerate(cail_files.items()):
                fp = config.CAIL_2018_DIR / fn
                exists = fp.exists()
                line_count = _count_dataset_lines(fp, 50000) if exists else 0
                with cols[i]:
                    checked = st.checkbox(
                        f"{label}",
                        value=exists and fn != "test.txt",
                        disabled=not exists,
                        key=f"cail_{fn}",
                        help=f"文件：{fn}，约 {line_count} 条" if exists else f"{fn} 不存在",
                    )
                    if exists:
                        st.caption(f"约 {line_count} 条")
                    if checked and exists:
                        cail_selected.append(fn)

            cail_max = st.number_input(
                "每个文件最多入库条数（0 = 不限制）",
                min_value=0, step=500, value=0, key="cail_max",
                help="CAIL 数据量较大，建议先设 1000 试验。",
            )
        else:
            cail_selected = []
            cail_max = 0

    st.divider()

    # ── 高级设置（折叠） ──
    with st.expander("检索参数（高级）", expanded=False):
        st.caption("以下参数影响对话页的检索行为，一般保持默认即可。")
        cur = load_rag_prefs()

        adv_c1, adv_c2, adv_c3 = st.columns(3)
        with adv_c1:
            src_opts = {
                "balanced": "双源均衡（推荐）",
                "auto": "自动识别",
                "jec_only": "仅检索 JEC-QA",
                "cail_only": "仅检索 CAIL2018",
            }
            cur_src = cur.get("source_mode", "balanced")
            pref_source = st.selectbox(
                "检索数据源策略",
                options=list(src_opts.keys()),
                index=list(src_opts.keys()).index(cur_src) if cur_src in src_opts else 0,
                format_func=lambda x: src_opts[x],
                key="adv_source_mode",
            )
        with adv_c2:
            pref_mmr = st.toggle(
                "去除重复证据（MMR）",
                value=bool(cur.get("use_mmr", False)),
                key="adv_mmr",
                help="开启后检索结果会去掉高度重复的片段，提高证据多样性。",
            )
        with adv_c3:
            pref_agent = st.toggle(
                "Agent 模式",
                value=bool(cur.get("use_agent_default", False)),
                key="adv_agent",
                help="开启后模型会自主决定是否及何时检索知识库（实验性功能）。",
            )

        if st.button("保存检索参数"):
            save_rag_prefs({"source_mode": pref_source, "use_mmr": pref_mmr, "use_agent_default": pref_agent})
            st.success("检索参数已保存。")

    st.divider()

    # ── 操作区 ──
    st.subheader("开始构建")

    op_c1, op_c2 = st.columns(2)
    with op_c1:
        st.markdown(
            "**全量构建**：清空旧向量库后重新入库。首次使用或更换嵌入模型后必须选此项。"
        )
        do_rebuild = st.button("全量构建", type="primary", key="btn_rebuild")
    with op_c2:
        st.markdown(
            "**增量添加**：在已有向量库基础上追加数据（可能产生重复，建议仅用于补充新数据）。"
        )
        do_incremental = st.button("增量添加", type="secondary", key="btn_incremental")

    if do_rebuild or do_incremental:
        rebuild = do_rebuild
        if not use_jec and not use_cail:
            st.error("请至少选择一个数据集。")
            return

        if rebuild:
            st.info("将清空旧向量库后重新构建。如果对话页正在运行，请先关闭。")

        total = 0
        progress = st.progress(0.0, text="准备中…")
        rebuild_once = rebuild
        log_box = st.empty()

        def _log(msg):
            log_box.info(msg)

        try:
            jec_bar_end = 0.5 if use_cail else 1.0

            def on_jec_progress(done, total_count, msg):
                _log(msg)
                if total_count > 0:
                    progress.progress(min(jec_bar_end, (done / total_count) * jec_bar_end), text=msg[:60])
                else:
                    progress.progress(min(jec_bar_end, jec_bar_end * 0.08), text=msg[:60])

            cail_bar_base = 0.5 if use_jec else 0.0

            def on_cail_progress(cum, msg):
                _log(msg)
                span = min(0.49, cum / 120000.0)
                progress.progress(min(0.99, cail_bar_base + span), text=msg[:60])

            if use_jec and jec_selected:
                jec_max_val = None if jec_max == 0 else int(jec_max)
                total += update_vector_store_from_jec_qa(
                    rebuild=rebuild_once,
                    splits=tuple(jec_selected),
                    max_items=jec_max_val,
                    progress_callback=on_jec_progress,
                )
                rebuild_once = False
                progress.progress(jec_bar_end, text="JEC-QA 入库完成")

            if use_cail and cail_selected:
                _log("正在入库 CAIL2018…")
                cail_max_val = None if cail_max == 0 else int(cail_max)
                total += update_vector_store_from_cail2018(
                    rebuild=rebuild_once,
                    splits=tuple(cail_selected),
                    max_items_per_split=cail_max_val,
                    progress_callback=on_cail_progress,
                )
                progress.progress(1.0, text="全部完成")

            st.success(f"构建完成！本次共写入约 **{total}** 条向量数据。")

        except Exception as e:
            progress.progress(1.0, text="构建失败")
            st.error(f"构建失败：{e}")
            with st.expander("错误详情", expanded=True):
                st.code(traceback.format_exc(), language="text")


if __name__ == "__main__":
    main()
