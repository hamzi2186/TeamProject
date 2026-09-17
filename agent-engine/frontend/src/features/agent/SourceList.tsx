import { BookOpen, FileText } from "lucide-react";
import { AssistantSourceItem } from "../../api/agent";

interface SourceListProps {
  sources: AssistantSourceItem[];
}

export function SourceList({ sources }: SourceListProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="agent-sources-container">
      <div className="agent-sources-header">
        <BookOpen size={14} />
        <span>Documentation Sources ({sources.length})</span>
      </div>
      <div className="agent-sources-grid">
        {sources.map((s, idx) => (
          <div className="agent-source-card" key={`${s.source_path}-${idx}`}>
            <div className="agent-source-badge">
              <FileText size={12} />
              <span>{s.module_key.toUpperCase()}</span>
            </div>
            <div className="agent-source-details">
              <strong className="agent-source-path" title={s.source_path}>
                {s.source_path}
              </strong>
              {s.header_path && (
                <span className="agent-source-header">{s.header_path}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

