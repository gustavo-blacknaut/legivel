"use client";
import { useEffect, useRef, useState } from "react";
import { useWorkflowText } from "@/lib/workflow-text";
import { Dialog } from "./Dialog";
import "./Workflow.css";

export function GuidedCamera({ onCapture, fallback }: { onCapture: (file: File) => void; fallback: () => void }) {
  const w = useWorkflowText();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then((media) => {
        if (cancelled) { media.getTracks().forEach((track) => track.stop()); return; }
        stream.current = media;
        if (video.current) { video.current.srcObject = media; void video.current.play(); }
      }).catch(() => setError(w.cameraUnavailable));
    return () => { cancelled = true; stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null; };
  }, [open, w.cameraUnavailable]);
  const capture = () => {
    const source = video.current;
    if (!source?.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = source.videoWidth; canvas.height = source.videoHeight;
    canvas.getContext("2d")?.drawImage(source, 0, 0);
    canvas.toBlob((blob) => { if (blob) { onCapture(new File([blob], "captura.jpg", { type: "image/jpeg" })); setOpen(false); } }, "image/jpeg", .94);
  };
  return <>
    <button className="button button-secondary" type="button" onClick={() => {
      if (!navigator.mediaDevices?.getUserMedia) { fallback(); return; }
      setError(""); setOpen(true);
    }}>{w.capture}</button>
    <Dialog open={open} title={w.capture} wide onClose={() => setOpen(false)} actions={<>
      <button type="button" className="button button-secondary" onClick={() => setOpen(false)}>{w.cancel}</button>
      {error ? <button type="button" className="button" onClick={() => { setOpen(false); fallback(); }}>{w.take}</button> :
        <button type="button" className="button" onClick={capture}>{w.take}</button>}
    </>}>
      <p>{w.captureHint}</p>
      {error && <p role="alert">{error}</p>}
      <div className="workflow-camera"><video ref={video} autoPlay muted playsInline /><div className="workflow-guide" /></div>
    </Dialog>
  </>;
}

type Quality = { warnings: string[]; corners: [number, number][] };
export function CaptureAssessment({ file, preview, label }: { file: File; preview: string; label: string }) {
  const w = useWorkflowText();
  const [result, setResult] = useState<Quality | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const form = new FormData(); form.append("photo", file);
    const token = window.location.pathname.match(/^\/enviar\/([^/]+)$/)?.[1];
    const endpoint = token ? `/api/public/scan/${encodeURIComponent(decodeURIComponent(token))}/check` : "/api/capture/check";
    fetch(endpoint, { method: "POST", body: form, headers: { "X-Requested-With": "legivel" }, signal: controller.signal })
      .then(async (response) => { if (response.ok) setResult(await response.json()); })
      .catch(() => {});
    return () => controller.abort();
  }, [file]);
  return <div className="workflow-stack workflow-assessment" role="status">
    <div className="workflow-image">
      <img src={preview} alt={label} />
      {result && result.corners.length > 0 && <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polygon points={result.corners.map(([x, y]) => `${x * 100},${y * 100}`).join(" ")} fill="none" stroke="#0a8" strokeWidth=".7" /></svg>}
    </div>
    {result?.warnings.map((warning) => <p className="alert alert-warning" key={warning}>{warning}</p>)}
    {result && <small>{w.qualityHint}</small>}
  </div>;
}
