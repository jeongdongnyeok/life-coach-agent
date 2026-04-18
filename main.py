import dotenv

dotenv.load_dotenv()
from openai import OpenAI
import asyncio
import base64
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool, ImageGenerationTool

client = OpenAI()

VECTOR_STORE_ID = "vs_69dfa1f2e36081919fa6db8f3281ab00"


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
            FileSearchTool(
                vector_store_ids=[VECTOR_STORE_ID], 
                max_num_results=3, 
            ),
            ImageGenerationTool(
                tool_config={
                    "type": "image_generation",
                    "quality": "high",
                    "output_format": "jpeg",
                    "moderation": "low",
                    "partial_images": 1,
                }
            ),
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
        if "type" in message:
            message_type = message["type"]
            if message_type == "web_search_call":
                with st.chat_message("ai"):
                    st.write("🔍 Searched the web...")
            elif message_type == "file_search_call":
                with st.chat_message("ai"):
                    st.write("🗂️ Searched your files...")
            elif message_type == "image_generation_call":
                image = base64.b64decode(message["result"])
                with st.chat_message("ai"):
                    st.image(image)


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
        "response.file_search_call.completed": ("✅ file search completed.", "complete"),
        "response.file_search_call.in_progress": (
            "📂 Starting file search...",
            "running",
        ),
        "response.file_search_call.searching": (
            "📂 File search in progress...",
            "running",
        ),
        "response.image_generation_call.generating": (
            "🎨 Drawing image...",
            "running",
        ),
        "response.image_generation_call.in_progress": (
            "🎨 Drawing image...",
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
        image_placeholder = st.empty()
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
                elif event.data.type == "response.image_generation_call.partial_image":
                    image = base64.b64decode(event.data.partial_image_b64)
                    image_placeholder.image(image)

                elif event.data.type == "response.completed":
                    image_placeholder.empty()


prompt = st.chat_input("Write a message for your life coach agent", accept_file=True, file_type=["txt", "pdf"],)

if prompt:

    for file in prompt.files:
        if file.type.startswith("text/"):
            with st.chat_message("ai"):
                with st.status("⏳ Uploading file...") as status:
                    uploaded_file = client.files.create(
                        file=(file.name, file.getvalue()),
                        purpose="user_data",
                    )
                    status.update(label="🗂️ Attaching file...")
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORE_ID,
                        file_id=uploaded_file.id
                    )
                    status.update(label="⌛️ File Uploaded", state="complete")
                

    if prompt.text:
        with st.chat_message("human"):
            st.write(prompt.text)
        asyncio.run(run_agent(prompt.text))


with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))