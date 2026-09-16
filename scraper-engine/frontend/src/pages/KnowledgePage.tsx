import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Globe2, Plus, RefreshCw } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { knowledgeApi } from "../api/knowledge";
import { StatusBadge } from "../components/StatusBadge";

export function KnowledgePage() {
  const [url, setUrl] = useState("");
  const queryClient = useQueryClient();
  const websites = useQuery({
    queryKey: ["websites"],
    queryFn: knowledgeApi.list,
    refetchInterval: (query) => query.state.data?.some((item) => ["PENDING", "CRAWLING", "PROCESSING", "EMBEDDING", "REFRESHING"].includes(item.kb_status ?? "")) ? 3000 : false,
  });
  const ingest = useMutation({
    mutationFn: knowledgeApi.ingest,
    onSuccess: () => { setUrl(""); void queryClient.invalidateQueries({ queryKey: ["websites"] }); },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (url.trim()) ingest.mutate(url.trim());
  }
  const rows = websites.data ?? [];
  const ready = rows.filter((item) => item.kb_status === "READY").length;
  const failed = rows.filter((item) => item.kb_status === "FAILED").length;
  const processing = rows.length - ready - failed;
  return (
    <main className="page">
      <div className="breadcrumb">Knowledge / Websites</div>
      <div className="page-header">
        <div><h1>Client knowledge</h1><p>Crawl lead websites and maintain reusable, retrieval-ready knowledge bases.</p></div>
      </div>
      <form className="ingest-panel" onSubmit={submit}>
        <div className="ingest-icon"><Plus size={20} /></div>
        <label><span>Add a website</span><input type="url" required maxLength={2048} placeholder="https://example.com" value={url} onChange={(event) => setUrl(event.target.value)} /></label>
        <button className="primary-button" disabled={ingest.isPending}>{ingest.isPending ? <RefreshCw className="spin" size={16} /> : <Globe2 size={16} />}Start indexing</button>
      </form>
      {ingest.error && <div className="error-state" role="alert">{ingest.error.message}</div>}
      <section className="metrics" aria-label="Knowledge metrics">
        <article><span>Websites</span><strong>{rows.length}</strong></article>
        <article><span>Ready</span><strong>{ready}</strong></article>
        <article><span>Processing</span><strong>{processing}</strong></article>
        <article><span>Failed</span><strong>{failed}</strong></article>
      </section>
      <section className="surface">
        <div className="section-heading"><div><h2>Websites</h2><p>One knowledge base is reused for matching sites in your account.</p></div><button className="icon-button" onClick={() => void websites.refetch()} aria-label="Refresh websites"><RefreshCw size={17} /></button></div>
        {websites.isLoading && <div className="loading-state">Loading websites...</div>}
        {websites.error && <div className="error-state">Could not load websites. Try again.</div>}
        {!websites.isLoading && !websites.error && rows.length === 0 && <div className="empty-state"><Globe2 size={24} /><h3>No websites yet</h3><p>Add a lead website to build your first client knowledge base.</p></div>}
        {rows.length > 0 && <div className="table-wrap"><table><thead><tr><th>Website</th><th>Leads using KB</th><th>Pages</th><th>Chunks</th><th>Status</th><th>Last crawled</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{rows.map((item) => <tr key={item.id}><td><strong>{item.normalized_key}</strong><small>{item.normalized_url}</small></td><td>{item.leads_using_kb}</td><td>{item.page_count}</td><td>{item.chunk_count}</td><td><StatusBadge status={item.kb_status} /></td><td>{item.last_crawled_at ? new Date(item.last_crawled_at).toLocaleString() : "Not crawled"}</td><td><Link className="row-action" to={`/knowledge/${item.id}`}>View <ArrowRight size={15} /></Link></td></tr>)}</tbody></table></div>}
      </section>
    </main>
  );
}

