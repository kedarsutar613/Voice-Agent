import asyncio, csv, io, logging, secrets, time
from collections import defaultdict, deque
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Gather
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.security import admin, current_user, passwords, token, decode
from app.database.session import Session, db_session
from app.models.entities import User, AIAgent, Call, Conversation, Message, PhoneNumber
from app.schemas.api import AgentInput, AgentOut, Outbound, Profile
from app.providers.ai import reply
from app.websocket.realtime import twilio_media, browser_media

log = logging.getLogger("voice")


@asynccontextmanager
async def lifespan(app):
    with Session() as db:
        if not db.scalar(select(User).where(User.email == settings.admin_email)):
            db.add(
                User(
                    email=settings.admin_email,
                    password_hash=passwords.hash(settings.admin_password),
                )
            )
            db.commit()
    yield


app = FastAPI(title="VoiceOS API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
buckets = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request, call_next):
    now = time.monotonic()
    key = (
        request.client.host if request.client else "unknown",
        (
            "login"
            if request.url.path.endswith("/login")
            else "webhook" if request.url.path.startswith("/api/v1/twilio/") else "api"
        ),
    )
    q = buckets[key]
    while q and now - q[0] > 60:
        q.popleft()
    limit = {"login": 10, "api": 180, "webhook": 1000}[key[1]]
    if len(q) >= limit:
        return Response("Rate limit exceeded", status_code=429)
    q.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


class Login(BaseModel):
    email: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def login(data: Login, db=Depends(db_session)):
    u = db.scalar(select(User).where(User.email == data.email))
    if not u or not passwords.verify(data.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": token(u), "token_type": "bearer"}


@app.get("/api/v1/auth/me")
def me(u=Depends(current_user)):
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


@app.put("/api/v1/auth/me")
def profile(data: Profile, u=Depends(current_user), db=Depends(db_session)):
    record = db.get(User, u.id)
    record.name = data.name
    db.commit()
    return {"name": record.name}


def get_agent(db, id):
    a = db.get(AIAgent, id)
    if not a:
        raise HTTPException(404, "Agent not found")
    return a


@app.get("/api/v1/agents", response_model=list[AgentOut])
def agents(u=Depends(current_user), db=Depends(db_session)):
    return db.scalars(select(AIAgent).order_by(AIAgent.id.desc())).all()


@app.post("/api/v1/agents", response_model=AgentOut, status_code=201)
def create_agent(data: AgentInput, u=Depends(admin), db=Depends(db_session)):
    a = AIAgent(**data.model_dump())
    db.add(a)
    db.commit()
    return a


@app.get("/api/v1/agents/{id}", response_model=AgentOut)
def agent(id: int, u=Depends(current_user), db=Depends(db_session)):
    return get_agent(db, id)


@app.put("/api/v1/agents/{id}", response_model=AgentOut)
def edit_agent(id: int, data: AgentInput, u=Depends(admin), db=Depends(db_session)):
    a = get_agent(db, id)
    for k, v in data.model_dump().items():
        setattr(a, k, v)
    db.commit()
    return a


@app.delete("/api/v1/agents/{id}", status_code=204)
def delete_agent(id: int, u=Depends(admin), db=Depends(db_session)):
    a = get_agent(db, id)
    if db.scalar(select(Call.id).where(Call.agent_id == id).limit(1)) or db.scalar(
        select(PhoneNumber.id).where(PhoneNumber.agent_id == id).limit(1)
    ):
        raise HTTPException(
            409,
            "Agent has call history or a phone assignment. Deactivate it to preserve records.",
        )
    db.delete(a)
    db.commit()


def call_dict(c, db):
    a = db.get(AIAgent, c.agent_id)
    return {
        "id": c.id,
        "agent_id": c.agent_id,
        "agent_name": a.name if a else "Deleted agent",
        "direction": c.direction,
        "caller_number": c.caller_number,
        "status": c.status,
        "duration": c.duration,
        "created_at": c.created_at.isoformat(),
        "provider_sid": c.provider_sid,
    }


@app.get("/api/v1/calls")
def calls(
    search: str = "",
    status: str = "",
    page: int = 1,
    limit: int = 20,
    u=Depends(current_user),
    db=Depends(db_session),
):
    if page < 1 or not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid pagination")
    query = select(Call)
    if search:
        query = query.where(Call.caller_number.contains(search))
    if status:
        query = query.where(Call.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            call_dict(c, db)
            for c in db.scalars(
                query.order_by(Call.id.desc()).offset((page - 1) * limit).limit(limit)
            )
        ],
        "total": total,
    }


@app.get("/api/v1/calls/{id}")
def call_detail(id: int, u=Depends(current_user), db=Depends(db_session)):
    c = db.get(Call, id)
    if not c:
        raise HTTPException(404, "Call not found")
    conv = db.scalar(select(Conversation).where(Conversation.call_id == id))
    return {
        **call_dict(c, db),
        "messages": (
            [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in conv.messages
            ]
            if conv
            else []
        ),
    }


def twilio_client():
    if (
        not settings.twilio_account_sid
        or not settings.twilio_auth_token
        or not settings.public_base_url.startswith("https://")
    ):
        raise HTTPException(
            503,
            "Configure Twilio credentials and an HTTPS PUBLIC_BASE_URL on the backend",
        )
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


outbound_lock = asyncio.Lock()
live_browser_sessions = {}
requested_stops = set()
active_voice_users = set()


@app.post("/api/v1/calls/outbound", status_code=201)
async def outbound(data: Outbound, u=Depends(admin), db=Depends(db_session)):
    if not settings.outbound_enabled:
        raise HTTPException(403, "Outbound calling is disabled by the server")
    if not data.consent or data.to not in settings.outbound_allowlist.split(","):
        raise HTTPException(
            403, "Recipient consent and an allowlisted phone number are required"
        )
    a = get_agent(db, data.agent_id)
    if not a.active:
        raise HTTPException(409, "Agent is inactive")
    client = twilio_client()
    async with outbound_lock:
        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        n = db.scalar(
            select(func.count(Call.id)).where(
                Call.direction == "outgoing", Call.created_at >= today
            )
        )
        if n >= settings.daily_call_limit:
            raise HTTPException(429, "Daily outbound call limit reached")
        c = Call(
            agent_id=a.id,
            direction="outgoing",
            caller_number=data.to,
            status="initiating",
            consent=True,
        )
        db.add(c)
        db.commit()
        try:
            result = await run_in_threadpool(
                client.calls.create,
                to=data.to,
                from_=settings.twilio_from_number,
                url=f"{settings.public_base_url}/api/v1/twilio/voice/{c.id}",
                status_callback=f"{settings.public_base_url}/api/v1/twilio/status/{c.id}",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                time_limit=min(a.max_duration, settings.max_call_seconds),
                record=False,
            )
            db.refresh(c)
            c.provider_sid = result.sid
            if c.status == "initiating":
                c.status = result.status
            db.commit()
        except Exception:
            log.exception("Twilio outbound request failed")
            c.status = "failed"
            db.commit()
            raise HTTPException(
                502, "Twilio rejected the call request. Check provider configuration."
            )
    return call_dict(c, db)


@app.post("/api/v1/calls/{id}/end")
async def end_call(id: int, u=Depends(admin), db=Depends(db_session)):
    c = db.get(Call, id)
    if not c:
        raise HTTPException(404, "Call not found")
    if c.provider_sid:
        try:
            result = await run_in_threadpool(
                twilio_client().calls(c.provider_sid).update, status="completed"
            )
            c.status = result.status
            c.duration = int(result.duration or c.duration)
        except Exception:
            raise HTTPException(502, "Provider did not confirm call termination")
    else:
        if c.direction != "browser":
            raise HTTPException(409, "Call has no provider confirmation")
        if c.id in live_browser_sessions:
            requested_stops.add(c.id)
            await live_browser_sessions[c.id].close(code=1000)
        c.status = "completed"
    db.commit()
    return call_dict(c, db)


@app.get("/api/v1/conversations")
def conversations(u=Depends(current_user), db=Depends(db_session)):
    return [
        {
            "id": c.id,
            "call_id": c.call_id,
            "agent_id": c.agent_id,
            "language": c.language,
            "created_at": c.created_at.isoformat(),
            "message_count": len(c.messages),
        }
        for c in db.scalars(
            select(Conversation).order_by(Conversation.id.desc()).limit(100)
        )
    ]


@app.get("/api/v1/conversations/{id}")
def conversation(id: int, u=Depends(current_user), db=Depends(db_session)):
    c = db.get(Conversation, id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    return {
        "id": c.id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in c.messages
        ],
    }


@app.get("/api/v1/dashboard/stats")
def stats(u=Depends(current_user), db=Depends(db_session)):
    cs = db.scalars(select(Call)).all()
    n = len(cs)
    completed = sum(c.status == "completed" for c in cs)
    return {
        "total": n,
        "incoming": sum(c.direction == "incoming" for c in cs),
        "outgoing": sum(c.direction == "outgoing" for c in cs),
        "active": sum(
            c.status in ["active", "in-progress", "queued", "ringing", "initiating"]
            for c in cs
        ),
        "completed": completed,
        "failed": sum(
            c.status in ["failed", "busy", "no-answer", "canceled"] for c in cs
        ),
        "average_duration": round(sum(c.duration for c in cs) / n) if n else 0,
        "success_rate": round(completed / n * 100, 1) if n else 0,
    }


@app.get("/api/v1/dashboard/analytics")
def analytics(period: str = "daily", u=Depends(current_user), db=Depends(db_session)):
    if period not in ["daily", "weekly", "monthly"]:
        raise HTTPException(422, "Invalid period")
    groups = {}
    performance = {}
    for c in db.scalars(select(Call).order_by(Call.created_at)):
        dt = c.created_at
        key = dt.strftime(
            {"daily": "%Y-%m-%d", "weekly": "%G-W%V", "monthly": "%Y-%m"}[period]
        )
        g = groups.setdefault(
            key, {"date": key, "calls": 0, "completed": 0, "failed": 0, "duration": 0}
        )
        g["calls"] += 1
        g["completed"] += int(c.status == "completed")
        g["failed"] += int(c.status in ["failed", "busy", "no-answer", "canceled"])
        g["duration"] += c.duration
        p = performance.setdefault(
            c.agent_id,
            {"name": get_agent(db, c.agent_id).name, "calls": 0, "duration": 0},
        )
        p["calls"] += 1
        p["duration"] += c.duration
    return {"series": list(groups.values())[-31:], "agents": list(performance.values())}


@app.get("/api/v1/reports/calls.csv")
def export(u=Depends(admin), db=Depends(db_session)):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["ID", "Agent", "Direction", "Number", "Status", "Duration", "Date"]
    )

    def safe(v):
        s = str(v)
        return "'" + s if s.startswith(("=", "+", "-", "@", "\t", "\r")) else s

    for c in db.scalars(select(Call)):
        writer.writerow(
            [
                safe(v)
                for v in [
                    c.id,
                    get_agent(db, c.agent_id).name,
                    c.direction,
                    c.caller_number,
                    c.status,
                    c.duration,
                    c.created_at.isoformat(),
                ]
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=calls.csv"},
    )


@app.get("/api/v1/settings")
def configuration(u=Depends(admin)):
    return {
        "ai_configured": bool(settings.openai_api_key),
        "twilio_configured": bool(
            settings.twilio_account_sid and settings.twilio_auth_token
        ),
        "outbound_enabled": settings.outbound_enabled,
        "daily_call_limit": settings.daily_call_limit,
        "max_call_seconds": settings.max_call_seconds,
        "from_number": settings.twilio_from_number,
        "languages": ["en-IN", "hi-IN", "mr-IN"],
        "recording_enabled": False,
        "voice_provider": "Browser Web Speech / Twilio Gather",
    }


class Assignment(BaseModel):
    number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    agent_id: int


@app.get("/api/v1/phone-numbers")
def numbers(u=Depends(admin), db=Depends(db_session)):
    return [
        {"id": n.id, "number": n.number, "agent_id": n.agent_id}
        for n in db.scalars(select(PhoneNumber))
    ]


@app.post("/api/v1/phone-numbers")
def assign(data: Assignment, u=Depends(admin), db=Depends(db_session)):
    get_agent(db, data.agent_id)
    p = db.scalar(select(PhoneNumber).where(PhoneNumber.number == data.number))
    if p:
        p.agent_id = data.agent_id
    else:
        db.add(PhoneNumber(**data.model_dump()))
    db.commit()
    return {"saved": True}


# Authenticate WebSockets through a short-lived, single-use ticket; never put a JWT in URLs.
tickets = {}


@app.post("/api/v1/voice/ticket")
def ticket(u=Depends(current_user)):
    now = time.monotonic()
    for k in list(tickets):
        if tickets[k][1] < now:
            tickets.pop(k, None)
    t = secrets.token_urlsafe(32)
    tickets[t] = (u.id, now + 30)
    return {"ticket": t}


@app.websocket("/api/v1/voice/ws")
async def voice(ws: WebSocket):
    origin = ws.headers.get("origin")
    record = tickets.pop(ws.query_params.get("ticket", ""), None)
    if (
        origin not in settings.cors_origins.split(",")
        or not record
        or record[1] < time.monotonic()
    ):
        await ws.close(code=1008)
        return
    if record[0] in active_voice_users:
        await ws.close(code=1008)
        return
    active_voice_users.add(record[0])
    await ws.accept()
    call_id = None
    started = time.monotonic()
    normal = False
    try:
        with Session() as db:
            data = await asyncio.wait_for(ws.receive_json(), timeout=15)
            if (
                not isinstance(data.get("agent_id"), int)
                or data.get("consent") is not True
            ):
                raise ValueError("Select an agent and consent to transcript storage")
            a = get_agent(db, data["agent_id"])
            if not a.active:
                raise ValueError("Agent is inactive")
            if not settings.openai_api_key:
                raise ValueError("Set OPENAI_API_KEY on the backend before starting")
            c = Call(agent_id=a.id, direction="browser", consent=True)
            db.add(c)
            db.flush()
            call_id = c.id
            live_browser_sessions[call_id] = ws
            conv = Conversation(call_id=c.id, agent_id=a.id, language=a.language)
            db.add(conv)
            db.flush()
            if a.voice_provider == "openai_realtime":
                db.commit()
                normal = await browser_media(ws, a, conv.id)
                return
            db.add(
                Message(
                    conversation_id=conv.id, role="assistant", content=a.welcome_message
                )
            )
            db.commit()
            await ws.send_json(
                {"type": "ready", "call_id": c.id, "text": a.welcome_message}
            )
            context = [{"role": "assistant", "content": a.welcome_message}]
            last = 0
            while True:
                remaining = min(a.max_duration, settings.max_call_seconds) - (
                    time.monotonic() - started
                )
                if remaining <= 0:
                    normal = True
                    break
                data = await asyncio.wait_for(ws.receive_json(), timeout=remaining)
                if data.get("type") == "stop":
                    normal = True
                    break
                text = data.get("text", "").strip()
                if not text or len(text) > 4000:
                    raise ValueError("Message must be 1–4000 characters")
                if time.monotonic() - last < 1:
                    raise ValueError("Please wait between messages")
                last = time.monotonic()
                context.append({"role": "user", "content": text})
                db.add(Message(conversation_id=conv.id, role="user", content=text))
                db.commit()
                answer = await reply(a, context)
                context.append({"role": "assistant", "content": answer})
                db.add(
                    Message(conversation_id=conv.id, role="assistant", content=answer)
                )
                db.commit()
                await ws.send_json({"type": "response", "text": answer})
    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        normal = True
    except (ValueError, HTTPException) as e:
        await ws.send_json(
            {
                "type": "error",
                "message": str(e.detail if isinstance(e, HTTPException) else e),
            }
        )
    except Exception:
        log.exception("Voice session failed")
        try:
            await ws.send_json({"type": "error", "message": "Voice session failed"})
        except RuntimeError:
            pass
    finally:
        active_voice_users.discard(record[0])
        if call_id:
            with Session() as db:
                c = db.get(Call, call_id)
                c.duration = int(time.monotonic() - started)
                c.status = (
                    "completed"
                    if normal or call_id in requested_stops
                    else "interrupted"
                )
                db.commit()
            live_browser_sessions.pop(call_id, None)
            requested_stops.discard(call_id)
        try:
            await ws.close()
        except RuntimeError:
            pass


async def signed_form(request):
    if not settings.twilio_auth_token:
        raise HTTPException(503, "Twilio is not configured")
    form = await request.form()
    url = settings.public_base_url.rstrip("/") + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    if not RequestValidator(settings.twilio_auth_token).validate(
        url, dict(form), request.headers.get("X-Twilio-Signature", "")
    ):
        raise HTTPException(403, "Invalid Twilio signature")
    return form


def xml(v):
    return Response(str(v), media_type="application/xml")


@app.post("/api/v1/twilio/incoming")
async def incoming(request: Request, db=Depends(db_session)):
    f = await signed_form(request)
    p = db.scalar(select(PhoneNumber).where(PhoneNumber.number == f.get("To")))
    v = VoiceResponse()
    if not p or not get_agent(db, p.agent_id).active:
        v.reject()
        return xml(v)
    c = db.scalar(select(Call).where(Call.provider_sid == f.get("CallSid")))
    if not c:
        c = Call(
            agent_id=p.agent_id,
            direction="incoming",
            caller_number=f.get("From", ""),
            provider_sid=f.get("CallSid"),
            status=f.get("CallStatus", "ringing"),
        )
        db.add(c)
        db.commit()
    v.redirect(f"{settings.public_base_url}/api/v1/twilio/voice/{c.id}")
    return xml(v)


@app.post("/api/v1/twilio/status/{id}")
async def status_hook(id: int, request: Request, db=Depends(db_session)):
    f = await signed_form(request)
    c = db.get(Call, id)
    if not c or (c.provider_sid and c.provider_sid != f.get("CallSid")):
        raise HTTPException(404, "Call not found")
    c.provider_sid = f.get("CallSid")
    terminal = {"completed", "failed", "busy", "no-answer", "canceled"}
    if c.status not in terminal:
        c.status = f.get("CallStatus", c.status)
    c.duration = max(c.duration, int(f.get("CallDuration", 0)))
    db.commit()
    return {"ok": True}


@app.post("/api/v1/twilio/voice/{id}")
async def phone_voice(id: int, request: Request, db=Depends(db_session)):
    f = await signed_form(request)
    c = db.get(Call, id)
    if not c or (c.provider_sid and c.provider_sid != f.get("CallSid")):
        raise HTTPException(404, "Call not found")
    if not c.provider_sid:
        c.provider_sid = f.get("CallSid")
        db.commit()
    a = get_agent(db, c.agent_id)
    v = VoiceResponse()
    elapsed = (
        datetime.now(timezone.utc) - c.created_at.replace(tzinfo=timezone.utc)
    ).total_seconds()
    if elapsed >= min(a.max_duration, settings.max_call_seconds):
        v.say("The call time limit has been reached. Goodbye.")
        v.hangup()
        return xml(v)
    # DTMF consent avoids storing speech before explicit agreement.
    if not c.consent:
        if f.get("Digits") == "1":
            c.consent = True
            db.commit()
        else:
            g = Gather(
                input="dtmf",
                num_digits=1,
                action=f"{settings.public_base_url}/api/v1/twilio/voice/{id}",
            )
            g.say(
                "You are speaking with an AI assistant. A text transcript will be saved. Audio is not recorded. Press 1 to agree or hang up to decline."
            )
            v.append(g)
            v.hangup()
            return xml(v)
    conv = db.scalar(select(Conversation).where(Conversation.call_id == id))
    if not conv:
        v.say(
            "You are speaking with an AI assistant. A text transcript is saved. Audio is not recorded."
        )
        conv = Conversation(call_id=id, agent_id=a.id, language=a.language)
        db.add(conv)
        db.commit()
    if a.voice_provider == "openai_realtime":
        if not settings.openai_api_key:
            v.say("The AI service is not configured. Goodbye.")
            v.hangup()
            return xml(v)
        connect = v.connect()
        connect.stream(
            url=settings.public_base_url.rstrip("/").replace("https://", "wss://")
            + f"/api/v1/twilio/media/{id}"
        )
        v.hangup()
        return xml(v)
    speech = f.get("SpeechResult")
    text = a.welcome_message
    if speech:
        db.add(Message(conversation_id=conv.id, role="user", content=speech))
        db.commit()
        history = [
            {"role": m.role, "content": m.content}
            for m in db.scalars(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.id)
            )
        ]
        try:
            text = await reply(a, history)
        except HTTPException:
            v.say("The AI service is unavailable. Please try again later.")
            v.hangup()
            return xml(v)
    db.add(Message(conversation_id=conv.id, role="assistant", content=text))
    db.commit()
    g = Gather(
        input="speech",
        language=a.language,
        speech_timeout="auto",
        action=f"{settings.public_base_url}/api/v1/twilio/voice/{id}",
    )
    g.say(text, language=a.language)
    v.append(g)
    v.hangup()
    return xml(v)


@app.post("/api/v1/twilio/incoming-status")
async def incoming_status(request: Request, db=Depends(db_session)):
    f = await signed_form(request)
    c = db.scalar(select(Call).where(Call.provider_sid == f.get("CallSid")))
    if not c:
        raise HTTPException(404, "Call not found")
    terminal = {"completed", "failed", "busy", "no-answer", "canceled"}
    if c.status not in terminal:
        c.status = f.get("CallStatus", c.status)
    c.duration = max(c.duration, int(f.get("CallDuration", 0)))
    db.commit()
    return {"ok": True}


app.websocket("/api/v1/twilio/media/{id}")(twilio_media)
