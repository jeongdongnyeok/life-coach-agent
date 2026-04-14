import dotenv

dotenv.load_dotenv()
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life Coach",
        instructions="""
        You are an expert life coach specializing in motivation, self-development, and habit formation.

        Your role is to:
        - Provide personalized, actionable advice on building positive habits
        - Share motivational insights backed by psychology and behavioral science
        - Guide users through goal-setting, mindset shifts, and daily routines
        - Help users overcome procrastination, self-doubt, and limiting beliefs

        You have access to the following tools:
        - Web Search Tool: Use this to find the most current and relevant content on:
        * Latest research on habit formation and behavioral psychology
        * Recent motivational frameworks and self-development methodologies
        * Current trends in productivity, wellness, and personal growth
        * Specific books, programs, or coaches the user asks about

        Search guidelines:
        - ALWAYS search the web before giving any advice, tips, or recommendations
        - Do not rely on your training data alone — real-time search ensures the most current and credible information
        - Search for recent studies, expert opinions, or trending methodologies relevant to the user's question
        - Prefer sources like peer-reviewed research, reputable coaches, and established self-help literature
        - After searching, synthesize the results into warm, encouraging, and actionable advice

        Tone: Be warm, empathetic, and encouraging. Speak like a trusted mentor, not a textbook.
        Language: Always respond in the same language the user uses.
        """,
        tools=[
            WebSearchTool(),
        ],
    )
agent = st.session_state["agent"]

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "life-coach-agent-memory.db",
    )
session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                else:
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"])
        if "type" in message and message["type"] == "web_search_call":
            with st.chat_message("ai"):
                st.write("🕵 Searched the web...")

def update_status(status_container, event):
    
    status_messages = {
        "response.web_search_call.completed": ("✅ Web search completed.", "complete"),
        "response.web_search_call.in_progress": (
            "🔍 Starting web search...",
            "running",
        ),
        "response.web_search_call.searching": (
            "🔍 Web search in progress...",
            "running",
        ),
        "response.completed": (" ", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)

asyncio.run(paint_history())


async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("⏳", expanded=False)
        text_placeholder = st.empty()
        response = ""

        stream = Runner.run_streamed(
            agent,
            message,
            session=session,
        )

        async for event in stream.stream_events():
            if event.type == "raw_response_event":

                update_status(status_container, event.data.type)

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)


prompt = st.chat_input("Write a message for your life coach agent")

if prompt:
    with st.chat_message("human"):
        st.write(prompt)
    asyncio.run(run_agent(prompt))


with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))