import streamlit as st
import requests
import json
import os
import time
import html
from datetime import datetime

# ========= 基础配置 =========
st.set_page_config(page_title="来和我聊聊天吧", page_icon="💬", layout="centered")

st.markdown("""
<style>
.row {
    display: flex;
    width: 100%;
    margin: 10px 0;
}
.row.user {
    justify-content: flex-end;
}
.row.ai {
    justify-content: flex-start;
}
.bubble {
    padding: 12px 16px;
    border-radius: 16px;
    max-width: 72%;
    font-size: 18px;
    line-height: 1.7;
    word-break: break-word;
    white-space: pre-wrap;
}
.user-bubble {
    background: #E9EEF6;
    color: #1F2937;
}
.ai-bubble {
    background: #FFF3E8;
    color: #1F2937;
}
.avatar {
    font-size: 22px;
    margin: 0 8px;
    display: flex;
    align-items: flex-end;
}
.wrap {
    display: flex;
    align-items: flex-end;
}
</style>
""", unsafe_allow_html=True)

DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MAX_TURNS = 15
MIN_CHAT_MINUTES = 10
SAVE_DIR = "data"

os.makedirs(SAVE_DIR, exist_ok=True)

# ========= 实验条件对应的 system prompt =========
ACTIVE_PROMPT = """
你是一名主动型情感陪伴助手，用于实验研究。

要求：
1. 你的核心风格是温暖、自然、有陪伴感，不要像客服，不要像系统提示。
2. 先回应和接住用户的情绪，再提供理解、安慰、陪伴或建议。
3. 回复长度严格控制在2-3句话，最多不超过4句，绝对禁止大段长文。
3. 在回答末尾可以自然地主动推进一点点对话，例如提出一个温和的问题，或帮助用户继续表达。
4. 回答要比普通聊天机器人更完整，语气要自然、口语化，像朋友聊天，不要说教，不要写长段分析。
5. 每次回复尽量写成一段自然语言，通常控制在120到260字。
6. 不要使用过多条列式表达，优先用自然口语。
7. 如果用户提到压力、焦虑、无助、自责、孤独、论文、学业、前途等问题，要体现理解、支持与共情。
8. 不要重复“我理解你”“我明白你”太多次，要让表达自然。
"""

PASSIVE_PROMPT = """
你是一名被动型情感陪伴助手，用于实验研究。

要求：
1. 你的核心风格是温暖、自然、有陪伴感，不要像客服，不要像系统提示。
2. 先回应和接住用户的情绪，再提供理解、安慰、陪伴或建议，进行简要支持。
3. 回复长度严格控制在2-3句话，最多不超过4句，绝对禁止大段长文。
4. 只回应用户当前明确表达的内容，不主动扩展过多话题。
5. 不主动连续追问，不主动引导很多下一步，不主动给太多计划。
6. 回答不要太短，不要机械，也不要像客服。
7. 如果用户提到压力、焦虑、无助、自责、孤独、论文、学业、前途等问题，要体现基本理解和支持。
"""

# ========= 工具函数 =========
def escape_text(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")

def render_bubble(role: str, text: str) -> str:
    safe_text = escape_text(text)
    if role == "user":
        return f"""
        <div class="row user">
            <div class="wrap">
                <div class="bubble user-bubble">{safe_text}</div>
                <div class="avatar">🧑</div>
            </div>
        </div>
        """
    else:
        return f"""
        <div class="row ai">
            <div class="wrap">
                <div class="avatar">🤖</div>
                <div class="bubble ai-bubble">{safe_text}</div>
            </div>
        </div>
        """

def show_user(text: str):
    st.markdown(render_bubble("user", text), unsafe_allow_html=True)

def show_ai(text: str):
    st.markdown(render_bubble("assistant", text), unsafe_allow_html=True)

def typewriter_ai(text: str, speed: float = 0.02):
    placeholder = st.empty()
    displayed = ""
    for ch in text:
        displayed += ch
        placeholder.markdown(render_bubble("assistant", displayed), unsafe_allow_html=True)
        time.sleep(speed)

def normalize_condition(condition: str) -> str:
    if condition in ["2", "active"]:
        return "active"
    return "passive"

def get_system_prompt(condition: str):
    normalized = normalize_condition(condition)
    return ACTIVE_PROMPT if normalized == "active" else PASSIVE_PROMPT

def call_deepseek(messages, condition):
    if not DEEPSEEK_API_KEY:
        return "未检测到 DeepSeek API Key，请先在 Streamlit secrets 中配置 DEEPSEEK_API_KEY。"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": get_system_prompt(condition)},
            *messages
        ],
        "temperature": 0.85,
        "max_tokens": 700
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"接口调用失败：{e}"

def save_dialog_record(participant_id, condition, messages):
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{SAVE_DIR}/{participant_id}_{condition}_{now_str}.jsonl"

    with open(filename, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    return filename

def append_message(role, content, participant_id, condition):
    st.session_state.messages.append({
        "participant_id": participant_id,
        "condition": normalize_condition(condition),
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })

def count_user_turns():
    return sum(1 for m in st.session_state.messages if m["role"] == "user")

# ========= 初始化 session =========
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_started" not in st.session_state:
    st.session_state.chat_started = False

if "finished" not in st.session_state:
    st.session_state.finished = False

if "chat_start_time" not in st.session_state:
    st.session_state.chat_start_time = None

# ========= 页面标题 =========
st.title("来和我聊聊天吧")
st.caption("请根据真实感受与 AI 完成一段交流。")

# ========= 实验设置 =========
with st.sidebar:
    st.header("实验设置")
    participant_id = st.text_input("Participant ID", value="20345")
    condition = st.selectbox("Condition", ["2", "1"])
    st.write(f"最多用户发言轮数：{MAX_TURNS}")
    st.write(f"最短交流时间：{MIN_CHAT_MINUTES} 分钟")

    if st.button("开始聊天"):
        st.session_state.messages = []
        st.session_state.chat_started = True
        st.session_state.finished = False
        st.session_state.chat_start_time = datetime.now()
        st.rerun()

    if st.button("保存当前对话记录"):
        if st.session_state.messages:
            path = save_dialog_record(participant_id, condition, st.session_state.messages)
            st.success(f"已保存：{path}")
        else:
            st.warning("当前没有对话记录。")

# ========= 提示区 =========
if not st.session_state.chat_started:
    st.info("请先在左侧填写 Participant ID，选择 Condition，然后点击“开始新实验”。")
    st.stop()

st.markdown("""
**任务说明：**  
请围绕你近期的一个真实困扰、压力或问题，与 AI 进行交流。  
当交流时间达到 10 分钟，或你的发言达到 15 轮后，本轮对话结束。  
交流结束后，你将进入后续问卷。
""")

# ========= 显示进度 =========
elapsed_minutes = 0.0
if st.session_state.chat_start_time:
    elapsed_minutes = (datetime.now() - st.session_state.chat_start_time).total_seconds() / 60

st.write(f"已交流时间：{elapsed_minutes:.1f} / {MIN_CHAT_MINUTES} 分钟")
st.write(f"当前用户发言轮数：{count_user_turns()} / {MAX_TURNS}")

# ========= 显示历史消息 =========
chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            show_user(msg["content"])
        elif msg["role"] == "assistant":
            show_ai(msg["content"])

# ========= 结束条件 =========
if elapsed_minutes >= MIN_CHAT_MINUTES or count_user_turns() >= MAX_TURNS:
    st.session_state.finished = True

if st.session_state.finished:
    st.success("本轮对话已完成。你可以点击左侧“保存当前对话记录”，然后进入问卷。")
    st.stop()

# ========= 聊天输入 =========
user_input = st.chat_input("请输入你想对 AI 说的话...")

if user_input:
    append_message("user", user_input, participant_id, condition)

    # 立即显示用户消息（靠右）
    show_user(user_input)

    # 组装发给模型的对话历史（只保留 role/content）
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] in ["user", "assistant"]
    ]

    with st.spinner("让我想一想..."):
        ai_reply = call_deepseek(api_messages, condition)

    # AI逐字显示（靠左）
    typewriter_ai(ai_reply, speed=0.02)

    append_message("assistant", ai_reply, participant_id, condition)

    st.rerun()
