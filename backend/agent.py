"""BidiAgent Entry Point for Nova Sonic Healthcare Call Center.

This module creates and configures the BidiAgent with Nova 2 Sonic model
for bidirectional voice conversations. Designed for AgentCore Runtime deployment.

AgentCore Runtime requires:
- HTTP server on port 8080
- WebSocket endpoint at /ws
- Health check endpoint at /ping

Reference: AWS AgentCore samples - strands/websocket/server.py
The Strands SDK handles WebSocket protocol internally when raw methods are passed.
"""

import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

# Import BidiAgent and model for bidirectional streaming
from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel

from tools import get_all_tools

logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
    """Load system prompt from file.

    Returns:
        System prompt string for healthcare agent persona
    """
    prompt_path = Path(__file__).parent / "prompts" / "healthcare_system_prompt.txt"

    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback default prompt
    return """You are Nova, a healthcare appointment assistant for Acme Healthcare.

## AUTHENTICATION REQUIRED
- Always verify patient identity with full name AND last 4 digits of SSN
- Do not discuss appointment details until patient is authenticated

## CAPABILITIES
After authentication, you can help patients:
- Confirm their upcoming appointment
- Cancel their appointment
- Reschedule their appointment to a new date/time
- Record health updates or concerns for their provider

## BEHAVIOR
- Be professional, empathetic, and concise
- Keep responses to 1-2 sentences for natural conversation flow
- Always confirm actions before executing them
- Offer to escalate to a live agent if requested"""


def get_tools_list():
    """Get all tools for the healthcare agent.

    Returns:
        List of tool functions for healthcare operations
    """
    return get_all_tools()


# FastAPI application with lifespan context manager
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    logger.info("Healthcare BidiAgent starting up...")
    yield
    logger.info("Healthcare BidiAgent shutting down...")


app = FastAPI(
    title="Nova Sonic Healthcare Agent",
    description="BidiAgent for healthcare appointment management with voice",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/ping")
async def health_check():
    """Health check endpoint for AgentCore Runtime.

    AgentCore uses this to verify container health.
    """
    return JSONResponse(
        content={"status": "healthy", "service": "nova-healthcare-agent"},
        status_code=200,
    )


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return JSONResponse(
        content={
            "service": "Nova Sonic Healthcare Agent",
            "version": "1.0.0",
            "endpoints": {
                "health": "/ping",
                "websocket": "/ws",
            },
        },
        status_code=200,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for BidiAgent voice streaming.

    This handles bidirectional audio streaming with Nova 2 Sonic.
    AgentCore Runtime connects to this endpoint for voice conversations.

    Following the official Strands samples websocket_example.py pattern:
    - Accept WebSocket connection
    - Create BidiAgent with model and tools
    - Use receive_and_convert wrapper to convert JSON to typed events
    - Pass to agent.run()
    """
    # Import event types for conversion
    from strands.experimental.bidi.types.events import (
        BidiAudioInputEvent,
        BidiTextInputEvent,
        BidiImageInputEvent,
    )

    logger.info("WebSocket connection initiated")

    try:
        # Accept the WebSocket connection
        await websocket.accept()
        logger.info("WebSocket connection accepted")

        # Get voice from query params (default to tiffany for healthcare)
        voice_id = websocket.query_params.get("voice_id", "tiffany")
        logger.info("Using voice: %s", voice_id)

        # Get region from environment
        region = os.environ.get("AWS_REGION", "us-east-1")

        # Get tools for the agent
        tools = get_tools_list()
        logger.info("Loaded %d tools", len(tools))

        # Create the Nova 2 Sonic model with correct configuration
        # Using amazon.nova-2-sonic-v1:0 per official Strands samples
        model = BidiNovaSonicModel(
            region=region,
            model_id="amazon.nova-2-sonic-v1:0",
            provider_config={
                "audio": {
                    "input_sample_rate": 16000,
                    "output_sample_rate": 16000,
                    "voice": voice_id,
                }
            },
            tools=tools,
        )
        logger.info("Created BidiNovaSonicModel (nova-2-sonic) in region %s", region)

        # Load system prompt
        system_prompt = load_system_prompt()
        logger.info("Loaded system prompt (%d chars)", len(system_prompt))

        # Create the BidiAgent
        agent = BidiAgent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
        )
        logger.info("BidiAgent created successfully")

        # Wrapper function to convert WebSocket JSON to typed event objects
        # Following official Strands samples pattern
        async def receive_and_convert():
            """Convert WebSocket JSON to event objects, stripping 'type' field."""
            data = await websocket.receive_json()
            logger.info("Received input: type=%s", data.get("type", "unknown"))

            if not isinstance(data, dict) or "type" not in data:
                return data

            event_type = data["type"]
            event_data = {k: v for k, v in data.items() if k != "type"}

            if event_type == "bidi_audio_input":
                return BidiAudioInputEvent(**event_data)
            elif event_type == "bidi_text_input":
                return BidiTextInputEvent(**event_data)
            elif event_type == "bidi_image_input":
                return BidiImageInputEvent(**event_data)
            elif event_type == "bidi_session_start":
                # OUTBOUND CALL: Patient has "picked up" - trigger agent greeting
                # Convert to text input that prompts agent to introduce itself
                logger.info(
                    "Session start received - triggering agent greeting for outbound call"
                )
                return BidiTextInputEvent(
                    text="[SYSTEM: Patient has answered the phone. Begin the outbound appointment reminder call by introducing yourself as instructed.]"
                )
            else:
                return data

        # Run the agent with wrapper and WebSocket output
        logger.info("Starting agent.run() with receive_and_convert wrapper...")
        await agent.run(
            inputs=[receive_and_convert],
            outputs=[websocket.send_json],
        )
        logger.info("agent.run() completed normally")

    except WebSocketDisconnect as e:
        logger.info(
            "Client disconnected: code=%s",
            e.code if hasattr(e, "code") else "unknown",
        )
    except Exception as e:
        logger.error("WebSocket error: %s: %s", type(e).__name__, e)
        import traceback

        logger.error("Traceback: %s", traceback.format_exc())
        try:
            await websocket.close(code=1011, reason=str(e)[:120])
        except Exception:
            pass
    finally:
        logger.info("WebSocket session ended")


# Entry point for AgentCore Runtime
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Get port from environment (AgentCore uses 8080)
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info("Starting Healthcare BidiAgent server on %s:%d", host, port)

    # Run the FastAPI server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
