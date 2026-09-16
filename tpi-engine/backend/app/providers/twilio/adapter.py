import uuid
from dataclasses import dataclass

from anyio import to_thread
from twilio.rest import Client

from app.core.config import TwilioNumberRoute, get_settings


class TwilioConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TwilioSendResult:
    sid: str
    status: str
    from_number: str


def route_for_user(user_id: uuid.UUID) -> TwilioNumberRoute:
    settings = get_settings()
    route = next(
        (item for item in settings.twilio_number_routes if item.user_id == str(user_id)),
        None,
    )
    if route:
        return route
    if settings.twilio_default_user_id == str(user_id) and (
        settings.twilio_default_sms_from_number or settings.twilio_messaging_service_sid
    ):
        return TwilioNumberRoute(
            user_id=str(user_id),
            phone_number=settings.twilio_default_sms_from_number,
            messaging_service_sid=settings.twilio_messaging_service_sid,
        )
    raise TwilioConfigurationError("No Twilio SMS number is assigned to this customer")


def user_for_number(phone_number: str) -> uuid.UUID:
    settings = get_settings()
    route = next(
        (item for item in settings.twilio_number_routes if item.phone_number == phone_number),
        None,
    )
    if route:
        return uuid.UUID(route.user_id)
    if settings.twilio_default_sms_from_number == phone_number and settings.twilio_default_user_id:
        return uuid.UUID(settings.twilio_default_user_id)
    raise TwilioConfigurationError("Inbound Twilio number is not assigned to a customer")


async def send_message(user_id: uuid.UUID, to_number: str, body: str) -> TwilioSendResult:
    settings = get_settings()
    if not settings.twilio_configured:
        raise TwilioConfigurationError("Twilio credentials are not configured")
    route = route_for_user(user_id)
    status_callback = (
        f"{settings.public_webhook_base_url.rstrip('/')}/api/v1/provider/twilio/sms/status"
        if settings.public_webhook_base_url
        else None
    )

    def create_message():
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        values = {
            "to": to_number,
            "body": body,
            "status_callback": status_callback,
        }
        if route.messaging_service_sid:
            values["messaging_service_sid"] = route.messaging_service_sid
        elif route.phone_number:
            values["from_"] = route.phone_number
        else:
            raise TwilioConfigurationError("Customer route has no sender configuration")
        return client.messages.create(**values)

    message = await to_thread.run_sync(create_message)
    return TwilioSendResult(
        sid=message.sid,
        status=(message.status or "queued").upper(),
        from_number=message.from_ or route.phone_number or route.messaging_service_sid or "",
    )
