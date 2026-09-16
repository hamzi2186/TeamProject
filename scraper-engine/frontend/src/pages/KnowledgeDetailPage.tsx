import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, RefreshCw, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { knowledgeApi } from "../api/knowledge";
import { StatusBadge } from "../components/StatusBadge";

export function KnowledgeDetailPage() {
  const { websiteId = "" } = useParams();
  const [query, setQuery] = useState("");
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["website-status", websiteId], queryFn: () => knowledgeApi.status(websiteId), refetchInterval: (query) => ["QUEUED", "RUNNING"].includes(query.state.data?.job?.status ?? "") ? 2500 : false });
  const pages = useQuery({ queryKey: ["website-pages", websiteId], queryFn: () => knowledgeApi.pages(websiteId), enabled: status.data?.website.kb_status === "READY" });
  const refresh = useMutation({ mutationFn: () => knowledgeApi.refresh(websiteId), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["website-status", websiteId] }) });
  const search = useMutation({ mutationFn: (value: string) => knowledgeApi.search(status.data!.website.knowledge_base_id!, value) });
  function submit(event: FormEvent) { event.preventDefault(); if (query.trim()) search.mutate(query.trim()); }
  if (status.isLoading) return <main className="page"><div className="loading-state">Loading knowledge base...</div></main>;
  if (status.error || !status.data) return <main className="page"><div className="error-state">Knowledge base could not be loaded.</div></main>;
  const website = status.data.website;
  const job = status.data.job;
  return (
    <main className="page">
      <Link className="back-link" to="/knowledge"><ArrowLeft size={16} />All websites</Link>
      <div className="detail-header"><div><div className="breadcrumb">Knowledge / {website.normalized_key}</div><h1>{website.normalized_key}</h1><p>{website.normalized_url}</p></div><div className="header-actions"><StatusBadge status={website.kb_status} /><button className="secondary-button" disabled={refresh.isPending || ["QUEUED", "RUNNING"].includes(job?.status ?? "")} onClick={() => refresh.mutate()}><RefreshCw size={16} />Refresh</button></div></div>
      {(refresh.error || job?.error_message) && <div className="error-state">{refresh.error?.message ?? job?.error_message}</div>}
      <section className="metrics detail-metrics">
        <article><span>Pages indexed</span><strong>{website.page_count}</strong></article>
        <article><span>Chunks</span><strong>{website.chunk_count}</strong></article>
        <article><span>Leads using KB</span><strong>{website.leads_using_kb}</strong></article>
        <article><span>Last crawl</span><strong className="metric-date">{website.last_crawled_at ? new Date(website.last_crawled_at).toLocaleDateString() : "Pending"}</strong></article>
      </section>
      {job && <section className="surface progress-panel"><div className="section-heading"><div><h2>Indexing progress</h2><p>The worker is crawling and preparing retrieval content.</p></div><StatusBadge status={job.status} /></div><div className="progress-grid"><span>Discovered <strong>{job.pages_discovered}</strong></span><span>Crawled <strong>{job.pages_crawled}</strong></span><span>Indexed <strong>{job.pages_indexed}</strong></span><span>Chunks <strong>{job.chunks_generated}</strong></span></div></section>}
      <section className="surface search-panel"><div className="section-heading"><div><h2>Test retrieval</h2><p>Search the same tenant-scoped Client KB contract used by outreach engines.</p></div></div><form className="search-form" onSubmit={submit}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="What services does this company offer?" disabled={website.kb_status !== "READY"} /><button className="primary-button" disabled={search.isPending || website.kb_status !== "READY"}><Search size={16} />Search</button></form>{search.error && <div className="error-state">{search.error.message}</div>}{search.data && <div className="search-results"><div className="result-meta">{search.data.results.length} results · {search.data.embedding_model} · {search.data.embedding_dimension} dimensions</div>{search.data.results.map((result) => <article key={result.chunk_id}><div><strong>{result.page_title ?? "Website content"}</strong><span>{Math.round(result.similarity * 100)}% similarity</span></div><p>{result.content}</p><a href={result.source_url} target="_blank" rel="noreferrer">Source <ExternalLink size={14} /></a></article>)}</div>}</section>
      <section className="surface"><div className="section-heading"><div><h2>Indexed pages</h2><p>Cleaned sources retained for traceable retrieval.</p></div></div>{pages.isLoading && <div className="loading-state">Loading pages...</div>}{pages.data && pages.data.length > 0 && <div className="table-wrap"><table><thead><tr><th>Page</th><th>URL</th><th>Status</th><th>Depth</th><th>Last fetched</th></tr></thead><tbody>{pages.data.map((page) => <tr key={page.id}><td><strong>{page.title ?? "Untitled page"}</strong></td><td><a className="source-link" href={page.canonical_url} target="_blank" rel="noreferrer">{page.canonical_url}<ExternalLink size={13} /></a></td><td>{page.http_status}</td><td>{page.depth}</td><td>{new Date(page.fetched_at).toLocaleString()}</td></tr>)}</tbody></table></div>}{pages.data?.length === 0 && <div className="empty-state">No indexed pages are available yet.</div>}</section>
    </main>
  );
}
