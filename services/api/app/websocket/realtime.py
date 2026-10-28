"""Bidirectional Twilio PCMU media bridge. Requires live provider validation."""

import asyncio
import base64
import json
import logging
from urllib.parse import urlencode
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from twilio.request_validator import RequestValidator
from sqlalchemy import select
from app.core.config import settings
from app.providers.ai import provider_error
from app.database.session import Session
from app.models.entities import AIAgent, Call, Conversation, Message

log = logging.getLogger("voice.realtime")
active_streams = set()


def session_config(agent):
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": agent.system_prompt
            + f" Speak in {agent.language}. You are an AI assistant. Keep responses concise.",
            "output_modalities": ["audio"],
            "max_output_tokens": 500,
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": {
                        "type": "server_vad",
                        "create_response": True,
                        "interrupt_response": True,
                    },
                },
                "output": {
                    "format": {"type": "audio/pcmu"},
                    "voice": agent.voice or "alloy",
                },
            },
        },
    }


def persist(conversation_id, role, content):
    if content:
        with Session() as db:
            db.add(Message(conversation_id=conversation_id, role=role, content=content))
            db.commit()


async def twilio_media(ws: WebSocket, id: int):
    url = (
        settings.public_base_url.rstrip("/").replace("https://", "wss://") + ws.url.path
    )
    signature = ws.headers.get("x-twilio-signature", "")
    validator = RequestValidator(settings.twilio_auth_token)
    if not settings.twilio_auth_token or not any(
        validator.validate(u, {}, signature) for u in [url, url + "/"]
    ):
        await ws.close(code=1008)
        return
    with Session() as db:
        call = db.get(Call, id)
        if (
            not call
            or not call.consent
            or call.status in {"completed", "failed", "canceled"}
            or id in active_streams
        ):
            await ws.close(code=1008)
            return
        agent = db.get(AIAgent, call.agent_id)
        conv = db.scalar(select(Conversation).where(Conversation.call_id == id))
        if (
            not conv
            or not agent.active
            or agent.voice_provider != "openai_realtime"
            or not settings.openai_api_key
        ):
            await ws.close(code=1008)
            return
        conversation_id, provider_sid = conv.id, call.provider_sid
    await ws.accept()
    active_streams.add(id)
    try:
        # Validate Twilio's account and call metadata before connecting a paid AI stream.
        async with asyncio.timeout(10):
            start = await ws.receive_json()
            if start.get("event") == "connected":
                start = await ws.receive_json()
            info = start.get("start", {})
            if (
                start.get("event") != "start"
                or info.get("callSid") != provider_sid
                or info.get("accountSid") != settings.twilio_account_sid
            ):
                raise ValueError("Stream metadata does not match the authorized call")
        stream_sid = info["streamSid"]
        state = {"timestamp": 0, "output_start": None, "item": None, "bytes": 0}
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?" + urlencode({"model": agent.model}),
            additional_headers={"Authorization": "Bearer " + settings.openai_api_key},
            max_size=2**20,
            open_timeout=15,
        ) as ai:
            await ai.send(json.dumps(session_config(agent)))
            # Wait for provider acceptance; malformed configurations must fail visibly in logs.
            async with asyncio.timeout(15):
                while True:
                    event = json.loads(await ai.recv())
                    if event["type"] == "error":
                        raise provider_error(event.get("error", {}))
                    if event["type"] == "session.updated":
                        break
            await ai.send(
                json.dumps(
                    {
                        "type": "response.create",
                        "response": {
                            "instructions": "Greet the caller using this welcome message: "
                            + agent.welcome_message
                        },
                    }
                )
            )

            async def upstream():
                async for raw in ws.iter_text():
                    event = json.loads(raw)
                    if event.get("event") == "stop":
                        return
                    if event.get("event") == "media":
                        state["timestamp"] = int(event["media"].get("timestamp", 0))
                        payload = event["media"]["payload"]
                        if len(payload) > 64000:
                            raise ValueError("Audio frame too large")
                        base64.b64decode(payload, validate=True)
                        await ai.send(
                            json.dumps(
                                {"type": "input_audio_buffer.append", "audio": payload}
                            )
                        )

            async def downstream():
                async for raw in ai:
                    event = json.loads(raw)
                    kind = event["type"]
                    if kind == "error":
                        raise provider_error(event.get("error", {}))
                    if kind == "response.output_audio.delta":
                        if state["item"] != event.get("item_id"):
                            state.update(
                                item=event.get("item_id"),
                                output_start=state["timestamp"],
                                bytes=0,
                            )
                        state["bytes"] += len(base64.b64decode(event["delta"]))
                        await ws.send_json(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": event["delta"]},
                            }
                        )
                    elif kind == "input_audio_buffer.speech_started":
                        await ws.send_json({"event": "clear", "streamSid": stream_sid})
                        if state["item"] and state["output_start"] is not None:
                            elapsed = min(
                                state["bytes"] // 8,
                                max(0, state["timestamp"] - state["output_start"]),
                            )
                            await ai.send(
                                json.dumps(
                                    {
                                        "type": "conversation.item.truncate",
                                        "item_id": state["item"],
                                        "content_index": 0,
                                        "audio_end_ms": elapsed,
                                    }
                                )
                            )
                            state.update(item=None, output_start=None, bytes=0)
                    elif (
                        kind == "conversation.item.input_audio_transcription.completed"
                    ):
                        persist(conversation_id, "user", event.get("transcript", ""))
                    elif kind == "response.output_audio_transcript.done":
                        persist(
                            conversation_id, "assistant", event.get("transcript", "")
                        )

            tasks = [asyncio.create_task(upstream()), asyncio.create_task(downstream())]
            try:
                async with asyncio.timeout(
                    min(agent.max_duration, settings.max_call_seconds)
                ):
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception:
        log.exception("Realtime media bridge failed for call %s", id)
    finally:
        active_streams.discard(id)
        # TwiML after Connect hangs up. Only the provider callback marks completion.
        try:
            await ws.close()
        except RuntimeError:
            pass


async def browser_media(ws, agent, conversation_id):
    """PCM24k bidirectional browser transport; the authenticated route owns call state."""
    normal = False
    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?" + urlencode({"model": agent.model}),
        additional_headers={"Authorization": "Bearer " + settings.openai_api_key},
        max_size=2**20,
        open_timeout=15,
    ) as ai:
        config = session_config(agent)
        config["session"]["audio"]["input"]["format"] = {
            "type": "audio/pcm",
            "rate": 24000,
        }
        config["session"]["audio"]["output"]["format"] = {
            "type": "audio/pcm",
            "rate": 24000,
        }
        await ai.send(json.dumps(config))
        async with asyncio.timeout(15):
            while True:
                event = json.loads(await ai.recv())
                if event["type"] == "error":
                    raise provider_error(event.get("error", {}))
                if event["type"] == "session.updated":
                    break
        await ws.send_json({"type": "ready", "realtime": True})
        await ai.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {
                        "instructions": "Greet the user using this welcome message: "
                        + agent.welcome_message
                    },
                }
            )
        )

        async def upstream():
            nonlocal normal
            async for raw in ws.iter_text():
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "stop":
                    normal = True
                    return
                if kind == "audio":
                    audio = event.get("audio", "")
                    if not 0 < len(audio) <= 64000:
                        raise ValueError("Invalid audio frame length")
                    base64.b64decode(audio, validate=True)
                    await ai.send(
                        json.dumps(
                            {"type": "input_audio_buffer.append", "audio": audio}
                        )
                    )
                elif kind == "interrupt":
                    await ai.send(json.dumps({"type": "response.cancel"}))
                elif kind == "text":
                    text = event.get("text", "").strip()
                    if not text or len(text) > 4000:
                        raise ValueError("Message must be 1–4000 characters")
                    persist(conversation_id, "user", text)
                    await ai.send(
                        json.dumps(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": text}],
                                },
                            }
                        )
                    )
                    await ai.send(json.dumps({"type": "response.create"}))

        async def downstream():
            async for raw in ai:
                event = json.loads(raw)
                kind = event["type"]
                if kind == "error":
                    # Cancellation may race with response completion; it is harmless.
                    if (
                        event.get("error", {}).get("code")
                        == "response_cancel_not_active"
                    ):
                        continue
                    raise provider_error(event.get("error", {}))
                if kind == "response.output_audio.delta":
                    await ws.send_json({"type": "audio", "audio": event["delta"]})
                elif kind == "input_audio_buffer.speech_started":
                    await ws.send_json({"type": "interrupted"})
                elif kind == "conversation.item.input_audio_transcription.completed":
                    text = event.get("transcript", "")
                    persist(conversation_id, "user", text)
                    await ws.send_json({"type": "input_transcript", "text": text})
                elif kind == "response.output_audio_transcript.done":
                    text = event.get("transcript", "")
                    persist(conversation_id, "assistant", text)
                    await ws.send_json(
                        {"type": "response", "text": text, "realtime": True}
                    )

        tasks = [asyncio.create_task(upstream()), asyncio.create_task(downstream())]
        try:
            async with asyncio.timeout(
                min(agent.max_duration, settings.max_call_seconds)
            ):
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    task.result()
        except asyncio.TimeoutError:
            normal = True
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    return normal
