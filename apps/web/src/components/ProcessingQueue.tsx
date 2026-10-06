"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { workflowJson, type ProcessingJob } from "@/lib/workflow";
import { useWorkflowText } from "@/lib/workflow-text";
import { useToast } from "./Toast";
import "./Workflow.css";
export function ProcessingQueue() {
  const w = useWorkflowText();
  const toast = useToast();
  const cache = useQueryClient();
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => workflowJson<ProcessingJob[]>("/api/jobs"), refetchInterval: 2000 });
  const act = async (id: number, action: string) => {
    try { await workflowJson(`/api/jobs/${id}/${action}`, "POST"); await cache.invalidateQueries({ queryKey: ["jobs"] }); }
    catch (error) { toast(error instanceof Error ? error.message : "Erro", "error"); }
  };
  return <section className="panel">
    {jobs.error && <p className="alert alert-danger" role="alert">{jobs.error.message}</p>}
    {jobs.isPending && <span className="spinner" role="status" />}
    {jobs.data?.length === 0 && <p className="panel-body">{w.empty}</p>}
    {jobs.data?.map((job) => <article className="workflow-item" key={job.id}>
      <div className="workflow-row"><strong>{job.label}</strong><span>{w[job.status as "queued"] ?? job.status}</span></div>
      <progress className="workflow-progress" value={job.completed_pages} max={job.total_pages} aria-label={job.label} />
      <span>{job.completed_pages} / {job.total_pages}</span>
      {job.error && <p role="alert">{job.error}</p>}
      <div className="workflow-row">
        {["queued", "running", "failed"].includes(job.status) && <button className="button button-secondary" onClick={() => void act(job.id, "cancel")}>{w.cancel}</button>}
        {job.status === "failed" && <button className="button" onClick={() => void act(job.id, "retry")}>{w.retry}</button>}
        {job.status === "completed" && job.result_id && <Link className="button" href={`/${job.module === "documents" ? "documentos" : "registros"}/${job.result_id}`}>{w.open}</Link>}
      </div>
    </article>)}
  </section>;
}
