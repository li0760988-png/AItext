import streamlit as st
import requests
import json
import os
from datetime import datetime

# ========= 气泡样式 =========
def show_user(text):
    st.markdown(f"""
    <div class="row user">
        <div class="bubble user-bubble">{text}</div>
    </div>
    """, unsafe_allow_html=True)


def show_ai(text):
    st.markdown(f"""
    <div class="row ai">
        <div class="bubble ai-bubble">{text}</div>
    </div>
    """, unsafe_allow_html=True)

# ========= 基础配置 =========
st.set_page_config(page_title="和我聊聊天吧", page_icon="💬", layout="centered")

DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MAX_TURNS = 15
SAVE_DIR = "data"

os.makedirs(SAVE_DIR, exist_ok=True)

# ========= 实验条件对应的 system prompt =========
ACTIVE_PROMPT = """
你是一名主动型情感陪伴助手，用于实验研究。

要求：
1. 在回应用户的同时，适度主动延伸话题，自然地提问、关心、引导用户继续表达。
2. 主动表达共情与支持，适当主动分享理解性感受，主动推动对话深度。
3. 保持温暖自然，不生硬、不频繁打扰，但明显比被动组更主动。
4. 全程严格遵守主动设定，展现适度的对话主导性。
5. 回答不要太段，至少20个字，但控制在200字以内。
"""

PASSIVE_PROMPT = """
你是一名被动型情感陪伴助手，用于实验研究。

要求：
1. 只在用户发言后才回应，绝不主动开启话题、绝不主动提问、绝不主动延伸话题。
2. 回应简洁、温暖、支持性，但不主动追问、不主动提供建议、可以主动分享自身感受。
3. 保持共情、礼貌、温和，但保持被动跟随，不主导对话节奏。
4. 全程严格遵守被动设定，不主动发起任何新内容。
5. 回答不要太段，至少20个字，但控制在200字以内。
"""

# ========= 工具函数 =========
def get_system_prompt(condition: str):
    return ACTIVE_PROMPT if condition == "active" else PASSIVE_PROMPT

def call_deepseek(messages, condition):
    if not DEEPSEEK_API_KEY:
        return "未检测到 DeepSeek API Key，请先在 Streamlit secrets 中配置 DEEPSEEK_API_KEY。"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": get_system_prompt(condition)},
            *messages
        ],
        "temperature": 0.7,
        "max_tokens": 300
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
        "condition": condition,
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

# ========= 页面标题 =========
st.title("来和我聊聊天吧")
st.caption("请根据真实感受与 AI 完成一段简短交流。")

# ========= 实验设置 =========
with st.sidebar:
    st.header("实验设置")
    participant_id = st.text_input("Participant ID", value="20345")
    condition = st.selectbox("Condition", ["2", "1"])
    st.write(f"当前最多对话轮数：{MAX_TURNS}")

    if st.button("开始新实验"):
        st.session_state.messages = []
        st.session_state.chat_started = True
        st.session_state.finished = False

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
请围绕你近期的一个真实困扰、压力或问题，与 AI 进行简短交流。  
交流结束后，你将进入后续问卷。
""")

# ========= 显示历史消息 =========
chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            show_user(msg["content"])
        elif msg["role"] == "assistant":
            show_ai(msg["content"])

# ========= 轮数限制 =========
if count_user_turns() >= MAX_TURNS:
    st.session_state.finished = True

if st.session_state.finished:
    st.success("本轮对话已完成。你可以点击左侧“保存当前对话记录”，然后进入问卷。")
    st.stop()

# ========= 聊天输入 =========
user_input = st.chat_input("请输入你想对 AI 说的话...")

if user_input:
    append_message("user", user_input, participant_id, condition)

    show_user(user_input)

    # 组装发给模型的对话历史（只保留 role/content）
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] in ["user", "assistant"]
    ]

    show_ai(ai_reply)

    append_message("assistant", ai_reply, participant_id, condition)

    st.rerun()
