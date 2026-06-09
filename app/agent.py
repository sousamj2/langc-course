"""
Production LangGraph agent with retry logic, fallback models, and LangSmith tracing.

This agent implements a production-grade message processing pipeline with:  
- Bidirectional streaming (Gemini Live)  
- Primary model (Gemini Flash Lite)  
- Secondary model (Gemma 31B)  
- Fallback model (Gemma 26B)  
- Graceful error handling and retry logic  
- LangSmith tracing for all operations  
"""

from typing import Optional
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langsmith import traceable

from app.config import get_settings

import websockets
import asyncio
from google import genai
from google.genai import types

# Initiatilze the official GenAI client (move to main.py ?)
# (It automatically picks the GEMINI_API_KEY environment variable)
client = genai.Client()

class AgentState(TypedDict):
    """
    State for the production agent.
    Uses Annotated with add_messages reducer for message accumulation.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model_used: str
    is_fallback: bool


class ProductionAgent:
    """
    Production LangGraph agent with:
    - Retry on failure (model fallback)
    - Graceful error handling
    - LangSmith tracing
    """

    def __init__ (self):
        settings = get_settings()

        # gemini-3-flash-live - Bidirectional streaming with websocket connection. Up to 65k TPM with unlimitted RPM and RPD.
        self.live_llm = ChatGoogleGenerativeAI(
            model=settings.live_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
            streaming=settings.streaming,
            verbose=settings.verbose,
        )

        # gemini-3.1-flash-lite - Best model in the free tier with 15 RPM, 250k TPM and 500 RPD.
        self.primary_llm = ChatGoogleGenerativeAI(
            model=settings.primary_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
            streaming=settings.streaming,
            verbose=settings.verbose,
        )

        # gemma-4-31b-it - Best open model with unlimitted RPM and TPM but limited to 1500 RPD.
        self.secondary_llm = ChatGoogleGenerativeAI(
            model=settings.secondary_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
            streaming=settings.streaming,
            verbose=settings.verbose,
        )

        # gemma-4-26b-a4b-it - Fallback open model with Unlimitted RPM and TPM but limited to 1500 RPD.
        self.fallback_llm = ChatGoogleGenerativeAI(
            model=settings.fallback_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
            streaming=settings.streaming,
            verbose=settings.verbose,
        )

        self.max_retries = settings.max_retries
        self.graph = self._build_graph()

    async def run_live_websocket_stream(self, message_text: str) -> str:
        """
        Opens a real-time WebSocket connection with Gemini Live.
        Streams text turns using v1alpha audio transcriptions to bypass text-modality handshakes.
        """
        collected_text = []

        # 1. Initialize a specific async live client targeting the v1alpha backend
        #    This mirrors the configuration that successfully ran in test_live.py
        from google.genai import types as genai_types
        from google import genai as official_genai
        
        live_client = official_genai.Client(
            http_options=genai_types.HttpOptions(api_version="v1alpha")
        )

        # 2. Replicate the exact working configuration from test_live.py
        config_live = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=genai_types.AudioTranscriptionConfig()
        )

        clean_prompt = str(message_text).strip()
        model_target = getattr(self, "live_llm", None) and getattr(self.live_llm, "model", None) or "gemini-3.1-flash-live-preview"

        # 3. Connect to the real-time session
        async with live_client.aio.live.connect(model=model_target, config=config_live) as session:
            # Send the text content turn explicitly
            await session.send_client_content(
                turns=genai_types.Content(
                    role='user',
                    parts=[genai_types.Part.from_text(text=clean_prompt)]
                ),
                turn_complete=True
            )

            # 4. Read incoming text transcript chunks
            async for response in session.receive():
                if response.server_content and response.server_content.output_transcription:
                    part = response.server_content.output_transcription
                    if part.text:
                        collected_text.append(part.text)

                # Gracefully exit once the model turn flags completion
                if response.server_content and response.server_content.turn_complete:
                    break
                    
        return "".join(collected_text)

    def _build_graph(self):
        """Build the LangGraph state machine with retry logic"""

        # FIX: Removed 'self' from the signature! 
        # Inside nested methods/closures, this acts as a regular function, not an object method.
        # LangGraph calls `live_message(state)`, passing only 1 argument.
        async def live_message(state: AgentState) -> dict:
            """LangGraph processing node that feeds the latest message to Gemini Live"""
            try:
                if not state.get("messages"):
                    raise ValueError("No messages found in the graph state.")

                last_message = state["messages"][-1]

                # Extract the raw string regardless of wrapper format
                if hasattr(last_message, "content"):
                    user_text = last_message.content
                elif isinstance(last_message, dict):
                    user_text = last_message.get("content", "")
                else:
                    user_text = str(last_message)

                # Call the object method via self reference inherited from the parent scope
                response = await self.run_live_websocket_stream(user_text)
                
                # Check if we got an empty string back to avoid dead loops
                if not response:
                    raise ValueError("Gemini Live session completed but returned an empty response.")

                return {
                    "messages": [AIMessage(content=response)],
                    "error": None,
                    "model_used": "gemini-3.1-flash-live-preview",
                    "is_fallback": False
                }
                
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                            
                return {
                    "messages": [],
                    "error": f"Live session broke [{error_type}]: {error_msg}. Falling back to Cloud Pool...",
                    "retry_count": 1,
                    "model_used": "",
                    "is_fallback": True
                }

        def primary_message(state: AgentState) -> dict:
            """Try to process the message with the primary model."""
            try:
                response = self.primary_llm.invoke(state["messages"])
                return {
                    "messages": [response],
                    "error": None,
                    "model_used": self.primary_llm.model,
                    "is_fallback": False
                }
            except Exception as e:
                return {
                    "messages": [],
                    "error": str(e),
                    "retry_count": state["retry_count"] + 1,
                    "model_used": "",
                    "is_fallback": False
                }

        def secondary_message(state: AgentState) -> dict:
            """Try to process the message with the secondary model."""
            try:
                response = self.secondary_llm.invoke(state["messages"])
                return {
                    "messages": [response],
                    "error": None,
                    "model_used": self.secondary_llm.model,
                    "is_fallback": True
                }
            except Exception as e:
                return {
                    "messages": [],
                    "error": str(e),
                    "retry_count": state["retry_count"] + 1,
                    "model_used": "",
                    "is_fallback": True
                }

        def fallback_message(state: AgentState) -> dict:
            """Try to process the message with the fallback model."""
            try:
                response = self.fallback_llm.invoke(state["messages"])
                return {
                    "messages": [response],
                    "error": None,
                    "model_used": self.fallback_llm.model,
                    "is_fallback": True
                }
            except Exception as e:
                return {
                    "messages": [],
                    "error": str(e),
                    "retry_count": state["retry_count"] + 1,
                    "model_used": "",
                    "is_fallback": True
                }
            

        def handle_error(state: AgentState) -> dict:
            """Returns a graceful error message."""
            return {
                "messages": [
                    AIMessage(content=(
                        "I'm sorry, I am having trouble processing your request. "
                        "Please try again in a moment."
                    ))
                ],
                "model_used": "error_handler",
            }

        def route_after_live(state: AgentState) -> str:
            """Decide what to do after live model attempt."""
            if state.get("error") is None:
                return "done"
            else:
                print(state.get("error"))
                return "primary"
        
        def route_after_primary(state: AgentState) -> str:
            """Decide what to do after primary model attempt."""
            if state.get("error") is None:
                return "done"
            else:
                return "secondary"

        def route_after_secondary(state: AgentState) -> str:
            """Decide what to do after secondary model attempt."""
            if state.get("error") is None:
                return "done"
            else:
                return "fallback"

        def route_after_fallback(state: AgentState) -> str:
            """Decide what to do after fallback model attempt."""
            if state.get("error") is None:
                return "done"
            else:
                return "error"
           

        # Initialize the state graph
        graph = StateGraph(AgentState)

        # graph.add_node("live",live_message)
        graph.add_node("live",secondary_message)
        graph.add_node("primary",primary_message)
        graph.add_node("secondary",secondary_message)
        graph.add_node("fallback",fallback_message)
        graph.add_node("error", handle_error)

        # Add edges
        graph.add_edge(START, "live")
        # Add conditional edges
        graph.add_conditional_edges(
            "live",
            route_after_live,
            {
                "done": END,
                "primary": "primary",
            }
        )

        graph.add_conditional_edges(
            "primary",
            route_after_primary,
            {
                "done": END,
                "secondary": "secondary",
            }
        )

        graph.add_conditional_edges(
            "secondary",
            route_after_secondary,
            {
                "done": END,
                "fallback": "fallback",
            }
        )

        graph.add_conditional_edges(
            "fallback",
            route_after_fallback,
            {
                "done": END,
                "error": "error",
            }
        )

        graph.add_edge("error", END)

        # START → LIVE → PRIMARY → SECONDARY → FALLBACK → ERROR → END
        #          ↓         ↓         ↓           ↓
        #         DONE →    DONE   →  DONE   →    DONE  →   END 

        # Return the compiled graph
        return graph.compile()

    @traceable(name="production_agent_invoke")
    async def invoke(self, message: str) -> dict:
        print("traceable running")
        import os
        print(f"LangSmith Environment Check:")
        # print(f"  - LANGCHAIN_TRACING_V2: {os.environ.get('LANGCHAIN_TRACING_V2')}")
        # print(f"  - LANGSMITH_TRACING: {os.environ.get('LANGSMITH_TRACING')}")
        # print(f"  - LANGCHAIN_ENDPOINT: {os.environ.get('LANGCHAIN_ENDPOINT')}")
        # print(f"  - LANGCHAIN_PROJECT: {os.environ.get('LANGCHAIN_PROJECT')}")
        try:
            from langsmith.run_helpers import get_current_run_tree
            from langsmith import Client
            run_tree = get_current_run_tree()
            if run_tree:
                print(f"  - LangSmith Active Run ID: {run_tree.id}")
                ls_client = Client()
                run_url = ls_client.get_run_url(run=run_tree)
                print(f"  - LangSmith Run URL: {run_url}")
        except Exception as ls_err:
            print(f"Could not retrieve LangSmith info: {ls_err}")
        """
        Invoke the agent with a user message.
        Returns: {"response": str, "model_used": str, "error": str | None, "is_fallback": bool, "retry_count": int}
        """
        result = await self.graph.ainvoke({
            "messages": [HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": "",
            "is_fallback": False,
        })
        return {
            "response": result["messages"][-1].content,
            "model_used": result.get("model_used", "unkown"),
            "error": result.get("error", None),
            "is_fallback": result.get("is_fallback", False),
            "retry_count": result.get("retry_count", 0),
        }