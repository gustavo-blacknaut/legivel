"use client";
import { useEffect, useRef, useState } from "react";
import { useWorkflowText } from "@/lib/workflow-text";
import { Dialog } from "./Dialog";
import { useWords } from "@/lib/maintenance-text";
import "./Workflow.css";

export function GuidedCamera({ onCapture, fallback }: { onCapture: (file: File) => void; fallback: () => void }) {
  const w = useWorkflowText();
  const words = useWords();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [device, setDevice] = useState("");
  const [torchAvailable, setTorchAvailable] = useState(false);
  const [torch, setTorch] = useState(false);
  const [zoomRange, setZoomRange] = useState<{ min: number; max: number; step: number } | null>(null);
  const [zoom, setZoom] = useState(1);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const stop = () => { stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null; };
    const timeout = setTimeout(() => { if (!cancelled && !video.current?.videoWidth) { cancelled = true; stop(); setError(w.cameraUnavailable); } }, 20_000);
    navigator.mediaDevices?.getUserMedia({ video: { ...(device ? { deviceId: { exact: device } } : { facingMode: { ideal: "environment" } }), width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then(async (media) => {
        if (cancelled) { media.getTracks().forEach((track) => track.stop()); return; }
        stream.current = media;
        const track = media.getVideoTracks()[0];
        const capabilities = track?.getCapabilities?.() as MediaTrackCapabilities & { torch?: boolean; zoom?: { min: number; max: number; step: number } };
        setTorchAvailable(!!capabilities?.torch);
        setZoomRange(capabilities?.zoom ?? null);
        setZoom((track?.getSettings?.() as MediaTrackSettings & { zoom?: number })?.zoom ?? capabilities?.zoom?.min ?? 1);
        if (video.current) { video.current.srcObject = media; await video.current.play(); }
        try {
          const available = await navigator.mediaDevices.enumerateDevices();
          if (!cancelled) setDevices(available.filter((item) => item.kind === "videoinput"));
        } catch { /* Device labels are optional; capture remains available. */ }
      }).catch(() => { if (!cancelled) { stop(); setError(w.cameraUnavailable); } });
    const onHidden = () => { if (document.visibilityState === "hidden") { stop(); setOpen(false); } };
    document.addEventListener("visibilitychange", onHidden);
    return () => { cancelled = true; clearTimeout(timeout); document.removeEventListener("visibilitychange", onHidden); stop(); };
  }, [open, device, w.cameraUnavailable]);
  const adjust = async (values: { torch?: boolean; zoom?: number }) => {
    const track = stream.current?.getVideoTracks()[0];
    if (!track) return;
    try {
      await track.applyConstraints({ advanced: [values as MediaTrackConstraintSet] });
      if (stream.current?.getVideoTracks()[0] !== track) return;
      if (values.torch !== undefined) setTorch(values.torch);
      if (values.zoom !== undefined) setZoom(values.zoom);
    } catch { setError(words("Este ajuste não está disponível nesta câmera. Use a captura nativa do aparelho.", "This camera adjustment is unavailable. Use the device camera instead.")); }
  };
  const capture = () => {
    const source = video.current;
    const capturedStream = stream.current;
    if (!source?.videoWidth || capturing) return;
    setCapturing(true);
    const canvas = document.createElement("canvas");
    const ratio = Math.min(1, 3000 / Math.max(source.videoWidth, source.videoHeight));
    canvas.width = Math.round(source.videoWidth * ratio); canvas.height = Math.round(source.videoHeight * ratio);
    if (!canvas.getContext("2d")) { setCapturing(false); setError(w.cameraUnavailable); return; }
    canvas.getContext("2d")!.drawImage(source, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => { setCapturing(false); if (!capturedStream || stream.current !== capturedStream) return; if (blob) { onCapture(new File([blob], "captura.jpg", { type: "image/jpeg" })); setOpen(false); } else setError(w.cameraUnavailable); }, "image/jpeg", .94);
  };
  return <>
    <button className="button button-secondary" type="button" onClick={() => {
      if (!navigator.mediaDevices?.getUserMedia) { fallback(); return; }
      setError(""); setReady(false); setTorch(false); setTorchAvailable(false); setZoomRange(null); setCapturing(false); setDevice(""); setOpen(true);
    }}>{w.capture}</button>
    <Dialog open={open} title={w.capture} wide busy={capturing} onClose={() => setOpen(false)} actions={<>
      <button type="button" className="button button-secondary" disabled={capturing} onClick={() => setOpen(false)}>{w.cancel}</button>
      {error ? <button type="button" className="button" onClick={() => { setOpen(false); fallback(); }}>{w.take}</button> :
        <button type="button" className="button" disabled={!ready || capturing} onClick={capture}>{w.take}</button>}
    </>}>
      <p>{w.captureHint}</p>
      {error && <p role="alert">{error}</p>}
      {!ready && !error && <p role="status">{words("Preparando câmera…", "Preparing camera…")}</p>}
      {devices.length > 1 && <label className="field">{words("Câmera", "Camera")}<select value={device} onChange={(event) => { setReady(false); setError(""); setTorch(false); setTorchAvailable(false); setZoomRange(null); setDevice(event.target.value); }}><option value="">{words("Traseira automática", "Automatic rear camera")}</option>{devices.map((item, index) => <option key={item.deviceId} value={item.deviceId}>{item.label || words(`Câmera ${index + 1}`, `Camera ${index + 1}`)}</option>)}</select></label>}
      {torchAvailable && <button type="button" className="button button-secondary" aria-pressed={torch} onClick={() => void adjust({ torch: !torch })}>{words("Luz da câmera", "Camera light")}</button>}
      {zoomRange && <label className="field">{words("Zoom da câmera", "Camera zoom")}<input type="range" min={zoomRange.min} max={zoomRange.max} step={zoomRange.step || .1} value={zoom} onChange={(event) => void adjust({ zoom: Number(event.target.value) })} /></label>}
      <div className="workflow-camera"><video ref={video} autoPlay muted playsInline onCanPlay={() => setReady(true)} /><div className="workflow-guide" /></div>
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
