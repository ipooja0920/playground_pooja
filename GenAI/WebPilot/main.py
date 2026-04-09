import asyncio
import os
from pathlib import Path
import yaml
import streamlit as st
from textwrap import dedent

# Load API key from mcp_agent.secrets.yaml into the environment if not already set
def _load_secrets():
    secrets_path = Path(__file__).parent / "mcp_agent.secrets.yaml"
    if secrets_path.exists():
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f) or {}
        api_key = secrets.get("openai", {}).get("api_key", "")
        if api_key and api_key != "YOUR_OPENAI_API_KEY":
            os.environ.setdefault("OPENAI_API_KEY", api_key)

_load_secrets()

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

# Page config
st.set_page_config(page_title="Browser MCP Agent", page_icon="🌐", layout="wide")

# Title and description
st.markdown("<h1 class='main-header'>🌐 Browser MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("Interact with a powerful web browsing agent that can navigate and interact with websites")

# Setup sidebar with example commands
with st.sidebar:
    st.markdown("### Example Commands")

    st.markdown("**Navigation**")
    st.markdown("- Go to https://github.com/ipooja0920/playground_pooja")

    st.markdown("**Interactions**")
    st.markdown("- click on GenAI")
    st.markdown("- Scroll down to view more content")

    st.markdown("**Multi-step Tasks**")
    st.markdown("- Navigate to https://github.com/ipooja0920/playground_pooja, scroll down, and report details")
    st.markdown("- Scroll down and summarize the github readme")

    st.markdown("---")
    st.caption("Note: The agent uses Playwright to control a real browser.")

# Query input
query = st.text_area("Your Command",
                   placeholder="Ask the agent to navigate to websites and interact with them")

# Initialize app and agent
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.mcp_app = MCPApp(name="streamlit_mcp_agent")
    st.session_state.mcp_context = None
    st.session_state.mcp_agent_app = None
    st.session_state.browser_agent = None
    st.session_state.llm = None
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.is_processing = False

# Setup function that runs only once
async def setup_agent():
    if not st.session_state.initialized:
        try:
            # Create context manager and store it in session state
            st.session_state.mcp_context = st.session_state.mcp_app.run()
            st.session_state.mcp_agent_app = await st.session_state.mcp_context.__aenter__()

            # Create and initialize agent
            st.session_state.browser_agent = Agent(
                name="browser",
                instruction="""You are a helpful web browsing assistant that can interact with websites using playwright.
                    - Navigate to websites and perform browser actions (click, scroll, type)
                    - Extract information from web pages
                    - Take screenshots of page elements when useful
                    - Provide concise summaries of web content using markdown
                    - Follow multi-step browsing sequences to complete tasks

                Respond back with a status update on completing the commands.""",
                server_names=["playwright"],
            )

            # Initialize agent and attach LLM
            await st.session_state.browser_agent.initialize()
            st.session_state.llm = await st.session_state.browser_agent.attach_llm(OpenAIAugmentedLLM)

            # List tools once
            logger = st.session_state.mcp_agent_app.logger
            tools = await st.session_state.browser_agent.list_tools()
            logger.info("Tools available:", data=tools)

            # Mark as initialized
            st.session_state.initialized = True
        except Exception as e:
            return f"Error during initialization: {str(e)}"
    return None

# Main function to run agent
async def run_mcp_agent(message):
    if not os.getenv("OPENAI_API_KEY"):
        return "Error: OpenAI API key not provided"

    try:
        # Make sure agent is initialized
        error = await setup_agent()
        if error:
            return error

        # Generate response without recreating agents
        # Switch use_history to False to reduce the passed context
        result = await st.session_state.llm.generate_str(
            message=message,
            request_params=RequestParams(use_history=True, maxTokens=10000)
            )
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# Defaults
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

def start_run():
    st.session_state.is_processing = True

# Button (use a callback so the click just flips state)
st.button(
    "🚀 Run Command",
    type="primary",
    use_container_width=True,
    disabled=st.session_state.is_processing,
    on_click=start_run,
)

# If we're in a processing run, do the work now
if st.session_state.is_processing:
    with st.spinner("Processing your request..."):
        result = st.session_state.loop.run_until_complete(run_mcp_agent(query))
    # persist result across the next rerun
    st.session_state.last_result = result
    # unlock the button and refresh UI
    st.session_state.is_processing = False
    st.rerun()

# Render the most recent result (after the rerun)
if st.session_state.last_result:
    st.markdown("### Response")
    st.markdown(st.session_state.last_result)
else:
    # (your existing help text here)
    pass


# Footer
st.markdown("---")
st.write("Built with Streamlit, Playwright, and [MCP-Agent](https://www.github.com/lastmile-ai/mcp-agent) Framework ❤️")
