from typing import Any, Protocol
from datetime import datetime, timezone
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
        if call.status == "QUEUED" and call.provider_call_id and call.provider_call_id.startswith("vapi-sim-"):
            diff = (now - call.started_at).total_seconds() if call.started_at else 10
            if diff >= 3:
                transcript = (
                    "AI (T Rex Voice Assistant): Hello, this is Alex calling from T Rex CRM on behalf of the sales automation team. Am I speaking with the business owner?\n"
                    "Lead: Yes, hello! I can hear you. What is this call regarding?\n"
                    "AI (T Rex Voice Assistant): We noticed your interest in automating lead intelligence, omnichannel outreach, and voice follow-ups. We wanted to see if scheduling a quick product demo makes sense for your team.\n"
                    "Lead: That sounds great actually. We definitely need a way to follow up with leads automatically without manual dialing.\n"
                    "AI (T Rex Voice Assistant): Excellent! I have scheduled our product specialist for a 15-minute demo tomorrow. You will receive the calendar invitation shortly.\n"
                    "Lead: Perfect, thank you!\n"
                    "AI (T Rex Voice Assistant): Thank you, have a wonderful day ahead!"
                )
                summary = "Lead answered outbound AI call, confirmed high interest in CRM automation and lead follow-up, and agreed to a 15-minute demonstration."
                call = call.model_copy(update={
                    "status": "COMPLETED",
                    "outcome": "INTERESTED",
                    "duration_seconds": 65,
                    "ended_at": now,
                    "transcript": transcript,
                    "summary": summary,
                })
                await self.repository.save(call)
        return call

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
