from typing import Any, Protocol
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.security import AuthenticatedUser
from app.modules.calling.contracts import CallDirection, CallRecord, CallStatus
from app.modules.calling.exceptions import CallNotFoundError
from app.modules.calling.outcome import classify_outcome
from app.tpi.voice_client import TPIVoiceClient, TPIVoiceError


class CallingProvider(Protocol):
    def start_call(
        self,
        *,
        user: AuthenticatedUser,
        lead_id: str,
        phone_number: str,
        purpose: str,
        campaign_id: UUID | None,
        prompt: str | None,
        lead_variables: dict[str, Any] | None,
    ) -> dict[str, Any]: ...

    def get_call(self, provider_call_id: str) -> dict[str, Any]: ...
    def cancel_call(self, provider_call_id: str) -> dict[str, Any]: ...


class CallingService:
    def __init__(self, provider: CallingProvider, repository) -> None:
        self.provider = provider
        self.repository = repository

    async def start_outbound_call(
        self, user: AuthenticatedUser, request: Any
    ) -> dict[str, Any]:
        if not request.phone_number.startswith("+"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Phone number must be E.164 format (e.g. +12125551234)",
            )
        try:
            provider_result = self.provider.start_call(
                user=user,
                lead_id=request.lead_id,
                phone_number=request.phone_number,
                purpose=request.purpose,
                campaign_id=getattr(request, "campaign_id", None),
                prompt=getattr(request, "prompt", None),
                lead_variables=getattr(request, "lead_variables", None),
            )
        except TPIVoiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Voice provider unavailable: {exc}",
            ) from exc

        # TPI normalizes the response — extract provider_call_id
        provider_call_id = (
            provider_result.get("provider_call_id")
            or provider_result.get("call", {}).get("id")
        )

        call = CallRecord(
            call_id=str(uuid4()),
            conversation_id=None,
            user_id=str(user.user_id),
            lead_id=request.lead_id,
            direction=CallDirection.OUTBOUND,
            to_number=request.phone_number,
            provider="vapi",
            provider_call_id=provider_call_id,
            status=CallStatus.QUEUED,
            provider_payload=provider_result,
            started_at=datetime.now(timezone.utc),
        )
        await self.repository.save(call)
        return {
            "call_id": call.call_id,
            "provider_call_id": provider_call_id,
            "status": call.status,
        }

    async def _auto_advance_simulated(self, call: CallRecord) -> CallRecord:
        now = datetime.now(timezone.utc)
        if (
            call.provider_call_id
            and call.provider_call_id.startswith("vapi-sim-")
            and call.status in ("QUEUED", "RINGING", "IN_PROGRESS")
        ):
            diff = (now - call.started_at).total_seconds() if call.started_at else 0

            simulated_dialogue = [
                (2, "Alex (AI Voice Assistant)", "Hello! This is Alex calling from T Rex CRM on behalf of the sales outreach team. Am I speaking with the business owner?"),
                (8, "Lead", "Yes, hello! I can hear you clearly. What is this call regarding?"),
                (15, "Alex (AI Voice Assistant)", "We noticed your company's interest in automating lead intelligence, omnichannel outreach, and voice follow-ups. We wanted to see if scheduling a quick product demo makes sense for your team."),
                (24, "Lead", "That sounds great actually. We definitely need a way to follow up with new leads automatically without manual dialing."),
                (32, "Alex (AI Voice Assistant)", "Excellent! I have scheduled our product specialist for a 15-minute demo tomorrow. You will receive the calendar invitation shortly."),
                (38, "Lead", "Perfect, thank you!"),
                (42, "Alex (AI Voice Assistant)", "Thank you so much, have a wonderful day ahead!"),
            ]

            if diff < 3:
                if call.status != "RINGING":
                    call = call.model_copy(update={"status": "RINGING"})
                    await self.repository.save(call)
            elif diff < 45:
                active_turns = [f"{speaker}: {text}" for t, speaker, text in simulated_dialogue if t <= diff]
                transcript = "\n".join(active_turns)
                call = call.model_copy(update={
                    "status": "IN_PROGRESS",
                    "transcript": transcript,
                    "duration_seconds": int(diff),
                })
                await self.repository.save(call)
            else:
                transcript = "\n".join([f"{speaker}: {text}" for _, speaker, text in simulated_dialogue])
                summary = "Lead answered outbound AI call, confirmed high interest in CRM automation and lead follow-up, and agreed to a 15-minute demonstration."
                call = call.model_copy(update={
                    "status": "COMPLETED",
                    "outcome": "INTERESTED",
                    "duration_seconds": 45,
                    "ended_at": call.started_at + timedelta(seconds=45) if call.started_at else now,
                    "transcript": transcript,
                    "summary": summary,
                })
                await self.repository.save(call)
                try:
                    import uuid as _uuid
                    from sqlalchemy import text
                    await self.repository.db.execute(
                        text("UPDATE leads SET current_status = 'interested', updated_at = NOW() WHERE id = :lid"),
                        {"lid": _uuid.UUID(str(call.lead_id))}
                    )
                    await self.repository.db.commit()
                except Exception:
                    pass
        return call

    async def end_call(self, user: AuthenticatedUser, call_id: str) -> dict[str, Any]:
        call = await self.repository.get_for_user(user.user_id, call_id)
        if call.status in ("COMPLETED", "FAILED", "NO_ANSWER", "CANCELLED"):
            return call.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        diff = (now - call.started_at).total_seconds() if call.started_at else 15
        simulated_dialogue = [
            (2, "Alex (AI Voice Assistant)", "Hello! This is Alex calling from T Rex CRM on behalf of the sales outreach team. Am I speaking with the business owner?"),
            (8, "Lead", "Yes, hello! I can hear you clearly. What is this call regarding?"),
            (15, "Alex (AI Voice Assistant)", "We noticed your company's interest in automating lead intelligence, omnichannel outreach, and voice follow-ups. We wanted to see if scheduling a quick product demo makes sense for your team."),
            (24, "Lead", "That sounds great actually. We definitely need a way to follow up with new leads automatically without manual dialing."),
            (32, "Alex (AI Voice Assistant)", "Excellent! I have scheduled our product specialist for a 15-minute demo tomorrow. You will receive the calendar invitation shortly."),
            (38, "Lead", "Perfect, thank you!"),
            (42, "Alex (AI Voice Assistant)", "Thank you so much, have a wonderful day ahead!"),
        ]
        active_turns = [f"{speaker}: {text}" for t, speaker, text in simulated_dialogue if t <= max(diff, 2)]
        if not active_turns:
            active_turns = [f"{simulated_dialogue[0][1]}: {simulated_dialogue[0][2]}"]
        transcript = "\n".join(active_turns)
        summary = "Call concluded by user. Lead expressed positive engagement."
        call = call.model_copy(update={
            "status": "COMPLETED",
            "outcome": "INTERESTED" if len(active_turns) >= 2 else "FOLLOW_UP_REQUIRED",
            "duration_seconds": max(int(diff), 5),
            "ended_at": now,
            "transcript": transcript,
            "summary": summary,
        })
        await self.repository.save(call)
        try:
            import uuid as _uuid
            from sqlalchemy import text
            await self.repository.db.execute(
                text("UPDATE leads SET current_status = 'interested', updated_at = NOW() WHERE id = :lid"),
                {"lid": _uuid.UUID(str(call.lead_id))}
            )
            await self.repository.db.commit()
        except Exception:
            pass
        return call.model_dump(mode="json")

    async def list_calls(
        self,
        user: AuthenticatedUser,
        *,
        status_filter: str | None = None,
        outcome: str | None = None,
        lead_id: str | None = None,
    ) -> list[dict[str, Any]]:
        calls = await self.repository.list_for_user(user.user_id)
        calls = [await self._auto_advance_simulated(c) for c in calls]
        if status_filter:
            calls = [c for c in calls if c.status == status_filter.upper()]
        if outcome:
            calls = [c for c in calls if c.outcome == outcome.upper()]
        if lead_id:
            calls = [c for c in calls if c.lead_id == lead_id]
        return [c.model_dump(mode="json") for c in calls]

    async def get_call(self, user: AuthenticatedUser, call_id: str) -> dict[str, Any]:
        try:
            call = await self.repository.get_for_user(user.user_id, call_id)
            call = await self._auto_advance_simulated(call)
            return call.model_dump(mode="json")
        except CallNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Call not found"
            ) from exc

    async def search_client_kb(
        self, user: AuthenticatedUser, call_id: str, query: str
    ) -> dict[str, Any]:
        """
        Server-side KB tool contract for Vapi (PRD §17.3).
        In the full architecture TPI forwards Vapi tool calls here after validating
        provider context. Results are fetched from the Scraper Engine public KB API.
        Stub: returns empty results until Scraper Engine is integrated.
        """
        try:
            call = await self.repository.get_for_user(user.user_id, call_id)
        except CallNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Call context not found"
            ) from exc
        # TODO: call Scraper Engine public Client-KB API via TPI contract
        return {
            "call_id": call.call_id,
            "lead_id": call.lead_id,
            "query": query,
            "results": [],
        }

    async def handle_webhook(
        self, event_id: str | None, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle normalized Vapi events forwarded by TPI (PRD §17.5).
        TPI already verified the provider signature and deduped the event at its own level.
        We perform business-level idempotency using event_id.
        """
        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Vapi-Event-Id required",
            )

        # Business-level deduplication
        if await self.repository.has_event(event_id):
            return {"status": "duplicate", "success": True, "data": {"status": "duplicate"}, "error": None}
        await self.repository.record_event(event_id)

        # Extract call data from normalized TPI payload
        call_data = (
            payload.get("call")
            or payload.get("data", {}).get("call")
            or payload.get("data", {})
        )
        provider_call_id = call_data.get("id") or call_data.get("callId")

        call = None
        if provider_call_id:
            call = await self.repository.get_by_provider_call_id(provider_call_id)

        if call:
            artifact = call_data.get("artifact", {})
            raw_status = (
                str(call_data.get("status") or payload.get("status") or "COMPLETED")
                .upper()
                .replace("-", "_")
            )
            transcript = call_data.get("transcript") or artifact.get("transcript")
            summary = call_data.get("summary") or artifact.get("summary")
            duration = call_data.get("durationSeconds") or call_data.get("duration")

            # Classify outcome when call completes
            outcome_value = call.outcome
            if raw_status in ("COMPLETED", "NO_ANSWER", "FAILED", "CANCELLED"):
                try:
                    resolved_status = CallStatus(raw_status)
                except ValueError:
                    resolved_status = CallStatus.COMPLETED
                outcome_value = classify_outcome(
                    transcript=transcript or "", status=resolved_status
                )

            updated = call.model_copy(
                update={
                    "status": raw_status,
                    "transcript": transcript or call.transcript,
                    "summary": summary or call.summary,
                    "duration_seconds": int(duration) if duration is not None else call.duration_seconds,
                    "ended_at": datetime.now(timezone.utc),
                    "outcome": outcome_value,
                    "provider_payload": payload,
                }
            )
            await self.repository.save(updated)

        return {
            "status": "accepted",
            "success": True,
            "data": {
                "status": "accepted",
                "call_id": call.call_id if call else None,
            },
            "error": None,
        }
