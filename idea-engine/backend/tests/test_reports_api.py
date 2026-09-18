import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shared_reads import LeadRead, SmsMessageRead


@pytest.mark.asyncio
async def test_api_full_flow(client: AsyncClient, test_session: AsyncSession):
    # 1. Health check
    health_resp = await client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["data"]["status"] == "healthy"

    # 2. Seed a lead into the test session
    lead_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead = LeadRead(
        id=lead_id,
        user_id=user_id,
        first_name="Bruce",
        last_name="Wayne",
        display_name="Bruce Wayne (Wayne Enterprises)",
        phone="+15551112222",
        email="bruce@wayne.example.com",
        website_url="https://wayne.example.com",
        current_status="NEW",
        created_at=now,
        updated_at=now,
    )
    test_session.add(lead)

    sms = SmsMessageRead(
        id=uuid.uuid4(),
        user_id=user_id,
        lead_id=lead_id,
        direction="INBOUND",
        from_number="+15551112222",
        to_number="+18005550199",
        body="Yes, we are very interested. Please send pricing information.",
        delivery_status="RECEIVED",
        sent_or_received_at=now,
        created_at=now,
    )
    test_session.add(sms)
    await test_session.commit()

    # 3. Test GET /idea/leads/{lead_id}/summary
    lead_summary_resp = await client.get(f"/idea/leads/{lead_id}/summary")
    assert lead_summary_resp.status_code == 200
    summary_data = lead_summary_resp.json()["data"]
    assert summary_data["lead_name"] == "Bruce Wayne (Wayne Enterprises)"
    assert summary_data["final_outcome"] == "INTERESTED"
    assert summary_data["campaigns"] == []
    assert len(summary_data["timeline"]) == 1

    # 4. Test POST /idea/reports/daily/generate
    gen_resp = await client.post(
        "/idea/reports/daily/generate",
        json={"report_date": str(now.date())},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()["data"]
    assert gen_data["status"] == "COMPLETED"
    assert gen_data["total_leads"] == 1
    assert gen_data["summary_counts"]["interested"] == 1
    report_id = gen_data["id"]

    # 5. Test GET /idea/reports/daily
    list_resp = await client.get("/idea/reports/daily")
    assert list_resp.status_code == 200
    reports_list = list_resp.json()["data"]
    assert len(reports_list) >= 1
    assert reports_list[0]["id"] == report_id

    # 6. Test GET /idea/reports/{report_id}
    detail_resp = await client.get(f"/idea/reports/{report_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert detail_data["id"] == report_id
    assert len(detail_data["items"]) == 1
    assert detail_data["items"][0]["final_outcome"] == "INTERESTED"
    assert detail_data["items"][0]["campaigns"] == []

    # 7. Test GET /idea/reports/{report_id}/download
    download_resp = await client.get(f"/idea/reports/{report_id}/download")
    assert download_resp.status_code == 200
    assert (
        download_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(download_resp.content) > 1000
