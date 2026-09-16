import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import get_settings
from app.db.session import Base
from app.models.idea_reports import IdeaLeadReportItem, IdeaReportRun
from app.models.shared_reads import CallRead, EmailRead, LeadRead, SmsMessageRead
from app.services.report_service import generate_daily_report


async def seed_data():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        today = datetime.now(timezone.utc).date()
        base_time = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)

        print("Checking existing leads in database...")
        stmt = select(LeadRead).limit(10)
        res = await session.execute(stmt)
        existing_leads = list(res.scalars().all())

        if len(existing_leads) >= 5:
            print(f"Found {len(existing_leads)} existing leads in database. Attaching multi-channel interactions to existing leads...")
            target_leads = existing_leads[:5]
            user_id = target_leads[0].user_id
        else:
            print("No existing leads found. Creating sample leads...")
            user_id = uuid.UUID("957b2327-331b-4608-afd7-a0c783314e3b")
            # Verify user exists or pick first user from app_users
            u_stmt = text("SELECT id FROM app_users LIMIT 1")
            u_res = await session.execute(u_stmt)
            u_row = u_res.fetchone()
            if u_row:
                user_id = u_row[0]

            lead_1_id = uuid.UUID("11111111-1111-4111-a111-111111111111")
            lead_2_id = uuid.UUID("22222222-2222-4222-b222-222222222222")
            lead_3_id = uuid.UUID("33333333-3333-4333-c333-333333333333")
            lead_4_id = uuid.UUID("44444444-4444-4444-d444-444444444444")
            lead_5_id = uuid.UUID("55555555-5555-4555-e555-555555555555")

            leads_data = [
                LeadRead(
                    id=lead_1_id,
                    user_id=user_id,
                    first_name="John",
                    last_name="Doe",
                    display_name="John Doe (Acme Corp)",
                    phone="+15551010001",
                    email="john.doe@acme.example.com",
                    website_url="https://acme.example.com",
                    current_status="NEW",
                    created_at=base_time - timedelta(days=2),
                    updated_at=base_time,
                ),
                LeadRead(
                    id=lead_2_id,
                    user_id=user_id,
                    first_name="Jane",
                    last_name="Smith",
                    display_name="Jane Smith (TechCorp)",
                    phone="+15551010002",
                    email="jane.smith@techcorp.example.com",
                    website_url="https://techcorp.example.com",
                    current_status="NEW",
                    created_at=base_time - timedelta(days=2),
                    updated_at=base_time,
                ),
                LeadRead(
                    id=lead_3_id,
                    user_id=user_id,
                    first_name="Alice",
                    last_name="Johnson",
                    display_name="Alice Johnson (Globex)",
                    phone="+15551010003",
                    email="alice@globex.example.com",
                    website_url="https://globex.example.com",
                    current_status="NEW",
                    created_at=base_time - timedelta(days=2),
                    updated_at=base_time,
                ),
                LeadRead(
                    id=lead_4_id,
                    user_id=user_id,
                    first_name="Peter",
                    last_name="Gibbons",
                    display_name="Peter Gibbons (Initech)",
                    phone="+15551010004",
                    email="peter@initech.example.com",
                    website_url="https://initech.example.com",
                    current_status="NEW",
                    created_at=base_time - timedelta(days=2),
                    updated_at=base_time,
                ),
                LeadRead(
                    id=lead_5_id,
                    user_id=user_id,
                    first_name="Bob",
                    last_name="Vance",
                    display_name="Bob Vance (Vance Refrigeration)",
                    phone="+15551010005",
                    email="bob@vancerefrig.example.com",
                    website_url="https://vancerefrig.example.com",
                    current_status="NEW",
                    created_at=base_time - timedelta(days=2),
                    updated_at=base_time,
                ),
            ]

            for lead in leads_data:
                existing = (await session.execute(select(LeadRead).where(LeadRead.id == lead.id))).scalar_one_or_none()
                if not existing:
                    session.add(lead)
            await session.commit()
            target_leads = leads_data

        target_lead_ids = [l.id for l in target_leads]
        print(f"Targeting {len(target_lead_ids)} leads for interactive multi-channel demo...")

        # Clear any prior mock interactions for these specific leads
        await session.execute(delete(CallRead).where(CallRead.lead_id.in_(target_lead_ids)))
        await session.execute(delete(SmsMessageRead).where(SmsMessageRead.lead_id.in_(target_lead_ids)))
        await session.execute(delete(EmailRead).where(EmailRead.lead_id.in_(target_lead_ids)))

        l1, l2, l3, l4, l5 = target_leads[0], target_leads[1], target_leads[2], target_leads[3], target_leads[4]

        # -------------------------------------------------------------
        # Lead 1: INTERESTED (Email -> Call No Answer -> SMS Positive Reply)
        # -------------------------------------------------------------
        session.add(
            EmailRead(
                id=uuid.uuid4(),
                user_id=l1.user_id,
                lead_id=l1.id,
                direction="OUTBOUND",
                from_address="outreach@trex.ai",
                subject=f"Accelerating pipeline automation for {l1.first_name or 'Team'}",
                text_body=f"Hi {l1.first_name or 'there'}, we noticed your recent growth. T Rex autonomously prospects and books qualified meetings.",
                delivery_status="DELIVERED",
                sent_or_received_at=base_time,
                created_at=base_time,
            )
        )
        session.add(
            CallRead(
                id=uuid.uuid4(),
                user_id=l1.user_id,
                lead_id=l1.id,
                direction="OUTBOUND",
                from_number="+18005550199",
                to_number=l1.phone or "+15551010001",
                status="NO_ANSWER",
                outcome="NO_ANSWER",
                duration_seconds=0,
                started_at=base_time + timedelta(hours=2),
                created_at=base_time + timedelta(hours=2),
            )
        )
        session.add(
            SmsMessageRead(
                id=uuid.uuid4(),
                user_id=l1.user_id,
                lead_id=l1.id,
                direction="OUTBOUND",
                from_number="+18005550199",
                to_number=l1.phone or "+15551010001",
                body=f"Hi {l1.first_name or 'there'}, tried reaching you by phone. Open to a quick 5-min demo this week?",
                delivery_status="DELIVERED",
                sent_or_received_at=base_time + timedelta(hours=2, minutes=15),
                created_at=base_time + timedelta(hours=2, minutes=15),
            )
        )
        session.add(
            SmsMessageRead(
                id=uuid.uuid4(),
                user_id=l1.user_id,
                lead_id=l1.id,
                direction="INBOUND",
                from_number=l1.phone or "+15551010001",
                to_number="+18005550199",
                body="Hi! Yes I am definitely interested. Could you send over the pricing and product demo link?",
                delivery_status="RECEIVED",
                sent_or_received_at=base_time + timedelta(hours=3),
                created_at=base_time + timedelta(hours=3),
            )
        )

        # -------------------------------------------------------------
        # Lead 2: DO_NOT_CONTACT (Email -> Inbound Unsubscribe Request)
        # -------------------------------------------------------------
        session.add(
            EmailRead(
                id=uuid.uuid4(),
                user_id=l2.user_id,
                lead_id=l2.id,
                direction="OUTBOUND",
                from_address="outreach@trex.ai",
                subject="Transforming enterprise sales outreach",
                text_body=f"Hi {l2.first_name or 'there'}, would love to show you how T Rex can 10x qualified lead volume.",
                delivery_status="DELIVERED",
                sent_or_received_at=base_time + timedelta(minutes=30),
                created_at=base_time + timedelta(minutes=30),
            )
        )
        session.add(
            EmailRead(
                id=uuid.uuid4(),
                user_id=l2.user_id,
                lead_id=l2.id,
                direction="INBOUND",
                from_address=l2.email or "lead2@example.com",
                subject="Re: Transforming enterprise sales outreach",
                text_body="Please stop contacting me and unsubscribe my email address immediately. Do not contact.",
                delivery_status="RECEIVED",
                sent_or_received_at=base_time + timedelta(hours=1),
                created_at=base_time + timedelta(hours=1),
            )
        )

        # -------------------------------------------------------------
        # Lead 3: CONVERTED (Direct Call Close)
        # -------------------------------------------------------------
        session.add(
            CallRead(
                id=uuid.uuid4(),
                user_id=l3.user_id,
                lead_id=l3.id,
                direction="OUTBOUND",
                from_number="+18005550199",
                to_number=l3.phone or "+15551010003",
                status="COMPLETED",
                outcome="CONVERTED",
                duration_seconds=260,
                summary=f"Agent discussed enterprise tier with {l3.first_name or 'Lead'}. Lead confirmed agreement and completed onboarding.",
                transcript=f"Agent: Hello {l3.first_name or 'there'}. Lead: Hi, we reviewed the pilot proposal and we're ready to proceed. We booked the kickoff meeting and submitted payment.",
                started_at=base_time + timedelta(hours=1, minutes=45),
                created_at=base_time + timedelta(hours=1, minutes=45),
            )
        )

        # -------------------------------------------------------------
        # Lead 4: FOLLOW_UP_REQUIRED (Call Reschedule Request)
        # -------------------------------------------------------------
        session.add(
            CallRead(
                id=uuid.uuid4(),
                user_id=l4.user_id,
                lead_id=l4.id,
                direction="OUTBOUND",
                from_number="+18005550199",
                to_number=l4.phone or "+15551010004",
                status="COMPLETED",
                outcome="FOLLOW_UP_REQUIRED",
                duration_seconds=42,
                summary="Lead stated they were in a meeting and requested a callback tomorrow afternoon.",
                transcript=f"{l4.first_name or 'Lead'}: Hey, I am in the middle of a meeting right now, please call me back tomorrow afternoon around 2 PM.",
                started_at=base_time + timedelta(hours=4),
                created_at=base_time + timedelta(hours=4),
            )
        )

        # -------------------------------------------------------------
        # Lead 5: NO_RESPONSE (Email + Call Unanswered)
        # -------------------------------------------------------------
        session.add(
            EmailRead(
                id=uuid.uuid4(),
                user_id=l5.user_id,
                lead_id=l5.id,
                direction="OUTBOUND",
                from_address="outreach@trex.ai",
                subject="Outreach automation inquiry",
                text_body=f"Hi {l5.first_name or 'there'}, wondering if your team is looking to automate pipeline generation?",
                delivery_status="DELIVERED",
                sent_or_received_at=base_time + timedelta(hours=2),
                created_at=base_time + timedelta(hours=2),
            )
        )
        session.add(
            CallRead(
                id=uuid.uuid4(),
                user_id=l5.user_id,
                lead_id=l5.id,
                direction="OUTBOUND",
                from_number="+18005550199",
                to_number=l5.phone or "+15551010005",
                status="NO_ANSWER",
                outcome="NO_ANSWER",
                duration_seconds=0,
                started_at=base_time + timedelta(hours=4, minutes=30),
                created_at=base_time + timedelta(hours=4, minutes=30),
            )
        )

        await session.commit()
        print("Multi-channel interactions seeded successfully in Supabase!")

        print(f"Generating Lead Intelligence report for date: {today}...")
        report = await generate_daily_report(session, today)
        print(f"Report generated successfully! ID: {report.id}, Leads: {report.total_leads}, File: {report.document_filename}")
        print("Summary counts:")
        print(f" - Interested: {report.summary_counts.interested}")
        print(f" - Converted: {report.summary_counts.converted}")
        print(f" - Follow-up Required: {report.summary_counts.follow_up_required}")
        print(f" - Do Not Contact: {report.summary_counts.do_not_contact}")
        print(f" - No Response: {report.summary_counts.no_response}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())
