"""
法律 RAG 智能问答系统 —— UI 样式注入。
设计规范：参照 DESIGN.md（Claude/Anthropic 暖羊皮纸风格）。
主色：陶土色 #c96442；背景：羊皮纸 #f5f4ed；卡片：象牙 #faf9f5。
"""
from __future__ import annotations


_ROOT_VARS = """
:root {
    /* ── Anthropic 设计系统色板 ── */
    --rag-accent:       #c96442;              /* 主品牌色：陶土 */
    --rag-accent-2:     #d97757;              /* 珊瑚强调 */
    --rag-accent-soft:  rgba(201,100,66,0.08);
    --rag-accent-ring:  rgba(201,100,66,0.22);
    --rag-danger:       #b53333;              /* 错误深红 */
    --rag-danger-hover: #9a2b2b;
    --rag-bg:           #f5f4ed;              /* 羊皮纸主背景 */
    --rag-surface:      #faf9f5;              /* 象牙卡片底 */
    --rag-surface-2:    #faf9f5;              /* 侧栏底 */
    --rag-border:       #f0eee6;              /* 奶油边框 */
    --rag-border-strong:#e8e6dc;              /* 暖沙边框 */
    --rag-text:         #141413;              /* 近黑主文字 */
    --rag-muted:        #5e5d59;              /* 橄榄灰次文字 */
    --rag-subtle:       #87867f;              /* 石灰三级文字 */
    --rag-chip:         #e8e6dc;              /* 标签底暖沙 */
    --rag-user-bg:      #c96442;              /* 用户气泡：陶土 */
    --rag-user-fg:      #faf9f5;              /* 用户气泡文字 */
    --rag-assistant-bg: #ffffff;        /* 助手气泡白 */
    --rag-assistant-fg: #141413;        /* 助手气泡文字 */
    --rag-radius: 12px;
    --rag-radius-sm: 8px;
    /* ring-based shadow（不用冷色投影） */
    --rag-shadow-sm: 0px 0px 0px 1px #d1cfc5;
    --rag-shadow:    rgba(0,0,0,0.05) 0px 4px 24px;
    --rag-shadow-lg: rgba(0,0,0,0.07) 0px 8px 32px;
    --rag-badge-strong:    #3d7a5a;
    --rag-badge-weak:      #7a6330;
    --rag-badge-unrelated: #87867f;
}
"""


_BASE_CSS = """
html, body, .stApp, [class*="css"] {
    font-family: Inter, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
    color: var(--rag-text);
    line-height: 1.6;
}
.stApp { background: var(--rag-bg); }

/* 标题使用 serif 字体 */
h1, h2, h3, h4 {
    font-family: Georgia, "Times New Roman", serif !important;
    font-weight: 500 !important;
    color: #141413 !important;
    line-height: 1.20 !important;
}

/* 全局滚动条（暖色调） */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f5f4ed; }
::-webkit-scrollbar-thumb { background: #d1cfc5; border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: #b0aea5; }

/* 放宽主内容区宽度，使三栏更舒展 */
section.main > div.block-container {
    max-width: 1320px;
    padding-top: 1.4rem;
    padding-bottom: 5.5rem;
}

/* 隐藏默认 Streamlit 页脚与菜单的多余间距 */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
"""


_HERO_CSS = """
/* 顶部标题栏 — 羊皮纸底色，不用渐变 */
.rag-hero {
    background: #141413;
    color: #faf9f5;
    padding: 1.25rem 1.5rem;
    border-radius: 12px;
    margin: 0 0 1.1rem 0;
    box-shadow: rgba(0,0,0,0.05) 0px 4px 24px;
}
.rag-hero::after {
    content: "";
    position: absolute;
    right: -60px; top: -60px;
    width: 180px; height: 180px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.22) 0%, rgba(255,255,255,0) 70%);
    pointer-events: none;
}
.rag-hero h1 {
    font-family: Georgia, serif !important;
    color: #faf9f5 !important;
    font-size: 1.6rem;
    font-weight: 500 !important;
    margin: 0 0 0.35rem 0;
    line-height: 1.20;
}
.rag-hero p {
    margin: 0;
    font-size: 0.95rem;
    color: #b0aea5;
    line-height: 1.60;
}
.rag-hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.7rem;
}
.rag-hero-chip {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    font-size: 0.78rem;
    color: #faf9f5;
    background: rgba(255,255,255,0.10);
    border: 1px solid #30302e;
    border-radius: 999px;
}
"""


_SIDEBAR_CSS = """
/* ======== 侧边栏（象牙底，奶油边框）======== */
section[data-testid="stSidebar"] {
    background: #faf9f5;
    border-right: 1px solid #f0eee6;
}
section[data-testid="stSidebar"] > div {
    padding-top: 0.75rem;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    font-family: Georgia, serif !important;
    color: #141413;
    font-weight: 500 !important;
    letter-spacing: 0;
}
section[data-testid="stSidebar"] h1 { font-size: 1.15rem; margin-bottom: 0.4rem; }
section[data-testid="stSidebar"] h2 { font-size: 1.0rem; }
section[data-testid="stSidebar"] h3 { font-size: 0.9rem; margin: 0.4rem 0 0.3rem; }

/* 侧栏标签文字 */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: var(--rag-muted) !important;
    font-size: 0.82rem !important;
    font-weight: 500;
}

/* 侧栏选择器（下拉） */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background: var(--rag-surface) !important;
    border: 1px solid var(--rag-border) !important;
    border-radius: var(--rag-radius-sm) !important;
    min-height: 40px;
    transition: border-color .15s ease, box-shadow .15s ease;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {
    border-color: var(--rag-accent-2) !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {
    border-color: var(--rag-accent) !important;
    box-shadow: 0 0 0 3px var(--rag-accent-ring) !important;
}

/* 侧栏输入框 */
section[data-testid="stSidebar"] input[type="text"],
section[data-testid="stSidebar"] textarea {
    background: var(--rag-surface) !important;
    border: 1px solid var(--rag-border) !important;
    border-radius: var(--rag-radius-sm) !important;
    color: var(--rag-text) !important;
    transition: border-color .15s ease, box-shadow .15s ease;
}
section[data-testid="stSidebar"] input[type="text"]:focus,
section[data-testid="stSidebar"] textarea:focus {
    border-color: var(--rag-accent) !important;
    box-shadow: 0 0 0 3px var(--rag-accent-ring) !important;
}

/* 侧栏按钮 - 默认 */
section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    border-radius: var(--rag-radius-sm);
    border: 1px solid var(--rag-border);
    background: var(--rag-surface);
    color: var(--rag-text);
    font-weight: 500;
    padding: 0.45rem 0.9rem;
    transition: all .15s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    border-color: var(--rag-accent-2);
    color: var(--rag-accent);
}

/* 侧栏按钮 - 主按钮（新建对话 · 陶土色）*/
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid*="primary"] {
    background: #c96442 !important;
    border: 1px solid #c96442 !important;
    color: #faf9f5 !important;
    font-weight: 500;
    box-shadow: 0px 0px 0px 1px #c96442;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
section[data-testid="stSidebar"] .stButton > button[data-testid*="primary"]:hover {
    background: #b5582e !important;
    border-color: #b5582e !important;
}

/* 侧栏开关 */
section[data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:first-child,
section[data-testid="stSidebar"] [data-testid="stToggle"] label > div:first-child {
    background: var(--rag-border-strong) !important;
}
section[data-testid="stSidebar"] [data-testid="stToggle"] input:checked + div,
section[data-testid="stSidebar"] [role="switch"][aria-checked="true"] {
    background: var(--rag-accent) !important;
}

/* 侧栏分隔线与 expander */
section[data-testid="stSidebar"] hr { border-color: var(--rag-border); margin: 0.7rem 0; }
section[data-testid="stSidebar"] details {
    border: 1px solid var(--rag-border);
    border-radius: var(--rag-radius-sm);
    background: var(--rag-surface);
    padding: 0.1rem 0.2rem;
}
section[data-testid="stSidebar"] summary {
    font-size: 0.85rem;
    color: var(--rag-text);
}
"""


_CHAT_CSS = """
/* ======== 主对话区 ======== */
.rag-chat-main {
    background: var(--rag-surface);
    border: 1px solid var(--rag-border);
    border-radius: var(--rag-radius);
    padding: 0.8rem 1rem 0.4rem;
    box-shadow: var(--rag-shadow-sm);
    margin-bottom: 0.75rem;
}

/* Tabs（对话 / 快速示例） */
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-weight: 600;
    color: var(--rag-muted);
    padding-top: 0.5rem;
    padding-bottom: 0.55rem;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--rag-accent) !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background-color: var(--rag-accent) !important;
    height: 3px !important;
    border-radius: 3px 3px 0 0;
}
div[data-testid="stTabs"] [data-baseweb="tab-border"] {
    background-color: var(--rag-border) !important;
}

/* 聊天消息卡片 - 通用兜底（圆角卡片） */
div[data-testid="stChatMessage"] {
    background: transparent;
    padding: 0.25rem 0.1rem;
    margin-bottom: 0.35rem;
}
div[data-testid="stChatMessage"] p { line-height: 1.65; }

/* 助手气泡 - 主选择器（现代浏览器 :has()） */
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: var(--rag-assistant-bg);
    border: 1px solid var(--rag-border);
    border-radius: 14px 14px 14px 4px;
    padding: 0.8rem 1rem;
    box-shadow: var(--rag-shadow-sm);
    max-width: 92%;
    margin-right: auto;
}

/* 用户气泡 — 陶土色（无渐变）*/
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: #c96442;
    border: 1px solid #c96442;
    border-radius: 14px 14px 4px 14px;
    padding: 0.8rem 1rem;
    box-shadow: 0px 0px 0px 1px #c96442;
    max-width: 88%;
    margin-left: auto;
    color: #faf9f5;
}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) *,
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p,
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) li,
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) strong {
    color: var(--rag-user-fg) !important;
}
/* 用户气泡里的头像底色淡化 */
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="chatAvatarIcon-user"] {
    background: rgba(255,255,255,0.18) !important;
}

/* 输入框（吸附底部）*/
div[data-testid="stChatInput"] {
    position: sticky;
    bottom: 0;
    background: rgba(245, 244, 237, 0.94);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-top: 1px solid #f0eee6;
    padding: 0.55rem 0.2rem 0.65rem;
    margin-top: 0.25rem;
    z-index: 10;
}
div[data-testid="stChatInput"] > div {
    border: 1px solid var(--rag-border) !important;
    border-radius: 12px !important;
    background: var(--rag-surface) !important;
    box-shadow: var(--rag-shadow-sm);
    transition: border-color .15s ease, box-shadow .15s ease;
}
div[data-testid="stChatInput"] > div:focus-within {
    border-color: var(--rag-accent) !important;
    box-shadow: 0 0 0 3px var(--rag-accent-ring) !important;
}
div[data-testid="stChatInput"] textarea {
    color: var(--rag-text) !important;
    font-size: 0.95rem;
}
div[data-testid="stChatInput"] textarea::placeholder {
    color: var(--rag-subtle) !important;
}
/* 发送按钮：陶土色 */
div[data-testid="stChatInput"] button {
    background: #c96442 !important;
    color: #faf9f5 !important;
    border-radius: 10px !important;
    transition: background .15s ease;
}
div[data-testid="stChatInput"] button:hover {
    background: #b5582e !important;
}
div[data-testid="stChatInput"] button svg {
    fill: #fff !important;
    color: #fff !important;
}

/* 欢迎态 info 提示 */
div[data-testid="stAlert"] {
    border-radius: 12px;
    border: 1px solid var(--rag-border);
    background: var(--rag-surface);
}

/* bordered container 统一风格 */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid var(--rag-border) !important;
    background: var(--rag-surface) !important;
    box-shadow: var(--rag-shadow-sm);
}

/* 正文按钮（快速示例等）— 暖沙色 */
.rag-chat-main .stButton > button,
section.main .stButton > button {
    border-radius: 8px;
    border: 1px solid #e8e6dc;
    background: #e8e6dc;
    color: #4d4c48;
    font-weight: 500;
    transition: all .15s ease;
    box-shadow: 0px 0px 0px 1px #d1cfc5;
}
.rag-chat-main .stButton > button:hover,
section.main .stButton > button:hover {
    border-color: #c96442;
    color: #c96442;
    background: #f5f4ed;
}

/* status 块样式收敛 */
div[data-testid="stStatusWidget"],
div[data-testid="stStatus"] {
    border-radius: 12px;
    border: 1px solid var(--rag-border);
    background: var(--rag-surface-2);
}

/* metric 字号 */
div[data-testid="stMetricValue"] { font-size: 1.35rem; }
"""


_RESPONSIVE_CSS = """
@media (max-width: 1200px) {
    section.main > div.block-container { max-width: 100%; padding-left: 1rem; padding-right: 1rem; }
}
@media (max-width: 1000px) {
    .rag-hero { padding: 1rem 1.1rem; }
    .rag-hero h1 { font-size: 1.25rem; }
    .rag-hero p { font-size: 0.88rem; }
    div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]),
    div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        max-width: 100%;
    }
}
"""


def inject_chat_css(st) -> None:
    st.markdown(
        f"""
        <style>
        {_ROOT_VARS}
        {_BASE_CSS}
        {_HERO_CSS}
        {_SIDEBAR_CSS}
        {_CHAT_CSS}
        {_RESPONSIVE_CSS}
        </style>
        """,
        unsafe_allow_html=True,
    )


_KB_CSS = """
/* ======== 右侧检索结果面板 ======== */
.rag-kb-side {
    position: sticky;
    top: 0.5rem;
}
.kb-panel {
    background: var(--rag-surface);
    border: 1px solid var(--rag-border);
    border-radius: var(--rag-radius);
    padding: 0.9rem 1rem 1rem;
    box-shadow: var(--rag-shadow-sm);
    margin-bottom: 0.75rem;
}
.kb-panel-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.98rem;
    font-weight: 600;
    color: var(--rag-text);
    margin: 0 0 0.6rem 0;
    padding-bottom: 0.55rem;
    border-bottom: 1px solid var(--rag-border);
}
.kb-panel-title::before {
    content: "";
    display: inline-block;
    width: 3px; height: 16px;
    border-radius: 2px;
    background: #c96442;
    margin-right: 0.55rem;
    vertical-align: middle;
}

.kb-empty {
    color: var(--rag-muted);
    font-size: 0.9rem;
    line-height: 1.7;
    text-align: center;
    padding: 2rem 0.8rem;
    border: 1px dashed var(--rag-border-strong);
    border-radius: 12px;
    background: var(--rag-surface-2);
}
.kb-empty-icon {
    font-size: 1.5rem;
    color: var(--rag-subtle);
    margin-bottom: 0.35rem;
}

.kb-card {
    border: 1px solid var(--rag-border);
    border-radius: 12px;
    padding: 0.85rem 1rem;
    background: var(--rag-surface);
    margin-bottom: 0.6rem;
    transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
}
.kb-card:hover {
    border-color: var(--rag-accent-2);
    box-shadow: rgba(0,0,0,0.05) 0px 4px 24px;
}

.kb-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.74rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    line-height: 1.4;
}
.kb-badge-strong { background: rgba(5, 150, 105, 0.12); color: var(--rag-badge-strong); }
.kb-badge-weak   { background: rgba(217, 119, 6, 0.12); color: var(--rag-badge-weak); }
.kb-badge-unrelated { background: rgba(148, 163, 184, 0.18); color: var(--rag-badge-unrelated); }
"""


def inject_kb_css(st) -> None:
    st.markdown(
        f"""
        <style>
        {_KB_CSS}
        </style>
        """,
        unsafe_allow_html=True,
    )
