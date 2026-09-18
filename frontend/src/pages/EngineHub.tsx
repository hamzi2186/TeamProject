import { ArrowRight, Bot, DatabaseZap, Mail, MessageSquare, PhoneCall, Users } from "lucide-react";
import { Link } from "react-router-dom";

interface EngineCardProps {
  title: string;
  description: string;
  path: string;
  icon: typeof PhoneCall;
  tone: string;
  statusText?: string;
  isExternalOrPending?: boolean;
}

const engines: EngineCardProps[] = [
  {
    title: "Calling Engine",
    description: "AI voice call automation, real-time call tracking, transcript playback, and outcome classification.",
    path: "/calling",
    icon: PhoneCall,
    tone: "green",
    statusText: "Active",
  },
  {
    title: "SMS Engine",
    description: "Autonomous 2-way SMS conversations and outreach campaigns via Twilio/TPI.",
    path: "/sms/",
    icon: MessageSquare,
    tone: "purple",
    statusText: "Active",
    isExternalOrPending: false,
  },
  {
    title: "Leads Workspace",
    description: "Canonical leads database. Review imported contacts and trigger outbound calls directly.",
    path: "/leads",
    icon: Users,
    tone: "blue",
    statusText: "Active",
  },
  {
    title: "HubSpot Integration",
    description: "Connect HubSpot CRM, sync contacts, and map properties to the canonical lead schema.",
    path: "/hubspot",
    icon: DatabaseZap,
    tone: "orange",
    statusText: "Active",
  },
  {
    title: "Mailer Engine",
    description: "Personalized cold email campaigns, SMTP delivery, and open/reply tracking.",
    path: "/calling",
    icon: Mail,
    tone: "blue",
    statusText: "Available",
    isExternalOrPending: false,
  },
  {
    title: "Agent Engine",
    description: "Conversational RAG assistant answering questions grounded in verified documentation.",
    path: "/agent/",
    icon: Bot,
    tone: "green",
    statusText: "Active",
    isExternalOrPending: false,
  },
];

export function EngineHub() {
  return (
    <main className="hub-page">
      <header className="hub-header">
        <p className="eyebrow dark">T Rex Operations Platform</p>
        <h1>Engine Selection & Workspace</h1>
        <p>Choose an operational engine to launch workflows, manage leads, or view outreach analytics.</p>
      </header>
      <section className="engine-grid">
        {engines.map(({ title, description, path, icon: Icon, tone, statusText }) => {
          const content = (
            <>
              <span className="engine-icon">
                <Icon size={24} />
              </span>
              <div className="engine-card-body">
                <div className="engine-card-title-row">
                  <strong>{title}</strong>
                  {statusText && (
                    <span className={`pill ${statusText === "Active" ? "ready" : "neutral"}`}>
                      {statusText}
                    </span>
                  )}
                </div>
                <small>{description}</small>
              </div>
              <ArrowRight className="engine-arrow" size={20} />
            </>
          );

          if (path.startsWith("/agent") || path.startsWith("/sms")) {
            return (
              <a className={`engine-card engine-card-${tone}`} href={path} key={title}>
                {content}
              </a>
            );
          }

          return (
            <Link className={`engine-card engine-card-${tone}`} to={path} key={title}>
              {content}
            </Link>
          );
        })}
      </section>
    </main>
  );
}
