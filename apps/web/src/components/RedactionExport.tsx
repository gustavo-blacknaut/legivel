"use client";
import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { useWorkflowText } from "@/lib/workflow-text";
import { saveBlob, workflowRequest } from "@/lib/workflow";
import { Dialog } from "./Dialog";
import "./Workflow.css";
type Page = { id: number; full_url: string | null };
type Rect = [number, number, number, number];
type Region = { page_id: number; rect: Rect };
export function RedactionExport({ entity, id, pages }: { entity: "document" | "record"; id: number; pages: Page[] }) {
  const w = useWorkflowText();
  const [open, setOpen] = useState(false);
  const [pageId, setPageId] = useState(pages[0]?.id ?? 0);
  const [regions, setRegions] = useState<Region[]>([]);
  const [start, setStart] = useState<[number, number] | null>(null);
  const [rect, setRect] = useState<Rect>([0, 0, 1, 1]);
  const [preview, setPreview] = useState<Blob | null>(null);
  const previewUrl = useMemo(() => preview ? URL.createObjectURL(preview) : null, [preview]);
  const [checked, setChecked] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  const page = pages.find((item) => item.id === pageId);
  const add = (coordinates: Rect) => {
    if (coordinates[0] >= coordinates[2] || coordinates[1] >= coordinates[3]) return;
    setRegions((current) => [...current, { page_id: pageId, rect: coordinates }]); setChecked([]); setPreview(null); setStart(null);
  };
  const select = (event: MouseEvent<HTMLDivElement>) => {
    if (preview) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const point: [number, number] = [(event.clientX - bounds.left) / bounds.width, (event.clientY - bounds.top) / bounds.height];
    if (!start) setStart(point);
    else add([Math.min(start[0], point[0]), Math.min(start[1], point[1]), Math.max(start[0], point[0]), Math.max(start[1], point[1])]);
  };
  const exportFile = async (download = false) => {
    setBusy(true); setError("");
    try {
      const response = await workflowRequest(`/api/redaction/${entity}/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ regions, preview_page: download ? null : pageId }) });
      const blob = await response.blob();
      if (download) saveBlob(blob, `legivel-${id}-ocultado.pdf`);
      else { setPreview(blob); setChecked((current) => Array.from(new Set([...current, pageId]))); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Erro"); }
    finally { setBusy(false); }
  };
  if (!pages.some((item) => item.full_url)) return null;
  return <>
    <button type="button" className="button button-secondary" onClick={() => setOpen(true)}>{w.hide}</button>
    <Dialog open={open} title={w.hide} wide busy={busy} onClose={() => setOpen(false)} actions={<>
      <button type="button" className="button button-secondary" disabled={busy} onClick={() => setOpen(false)}>{w.cancel}</button>
      <button type="button" className="button" disabled={busy || !regions.length || checked.length < pages.length} onClick={() => void exportFile(true)}>{w.download}</button>
    </>}>
      <div className="workflow-stack">
        <p>{w.hideHint}</p>
        <label className="field"><span className="field-label">{w.page}</span><select value={pageId} onChange={(event) => { setPageId(Number(event.target.value)); setPreview(null); setStart(null); }}>{pages.map((item, index) => <option key={item.id} value={item.id}>{index + 1}{checked.includes(item.id) ? " ✓" : ""}</option>)}</select></label>
        {page?.full_url && <div className="workflow-image" onClick={select}>
          <img src={preview && previewUrl ? previewUrl : page.full_url} alt={`${w.page} ${pages.indexOf(page) + 1}`} />
          {!preview && <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {regions.filter((item) => item.page_id === pageId).map((item, index) => <rect key={index} x={item.rect[0] * 100} y={item.rect[1] * 100} width={(item.rect[2] - item.rect[0]) * 100} height={(item.rect[3] - item.rect[1]) * 100} fill="black" />)}
            {start && <circle cx={start[0] * 100} cy={start[1] * 100} r="1" fill="#e33" />}
          </svg>}
        </div>}
        <details><summary>{w.region} (%)</summary><div className="workflow-row">
          {rect.map((value, index) => <label className="field" key={index}>{["X1", "Y1", "X2", "Y2"][index]}<input type="number" min={0} max={100} value={Math.round(value * 100)} onChange={(event) => setRect((current) => current.map((item, i) => i === index ? Number(event.target.value) / 100 : item) as Rect)} /></label>)}
          <button type="button" className="button button-secondary" onClick={() => add(rect)}>{w.save}</button>
        </div></details>
        <div className="workflow-row">
          <button type="button" className="button button-secondary" disabled={busy || !regions.length} onClick={() => void exportFile()}>{w.preview}</button>
          {preview && <button type="button" className="button button-secondary" onClick={() => setPreview(null)}>{w.original}</button>}
          <button type="button" className="button button-ghost" onClick={() => { setRegions([]); setPreview(null); setChecked([]); }}>{w.clear}</button>
        </div>
        {regions.map((item, index) => <div className="workflow-row" key={index}><span>{w.page} {pages.findIndex((p) => p.id === item.page_id) + 1}: {w.region} {index + 1}</span><button type="button" className="button button-ghost" onClick={() => { setRegions((current) => current.filter((_, i) => i !== index)); setPreview(null); setChecked([]); }}>{w.remove}</button></div>)}
        {error && <p role="alert">{error}</p>}
      </div>
    </Dialog>
  </>;
}
