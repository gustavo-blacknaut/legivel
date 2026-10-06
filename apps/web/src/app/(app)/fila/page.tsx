"use client";
import { PageHead } from "@/components/PageHead";
import { ProcessingQueue } from "@/components/ProcessingQueue";
import page from "@/components/Page.module.css";
import { useWorkflowText } from "@/lib/workflow-text";
export default function QueuePage() {
  const w = useWorkflowText();
  return <div className={page.page}><PageHead title={w.queue} description={w.queueDescription} /><ProcessingQueue /></div>;
}
