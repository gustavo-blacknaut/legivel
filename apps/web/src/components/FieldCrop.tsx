"use client";
import { useEffect, useRef, useState } from "react";
import { useWorkflowText } from "@/lib/workflow-text";
import "./Workflow.css";
export type FieldRegion = { side: string; rect: [number, number, number, number] };
export function FieldCrop({ field, region, src }: { field: string; region?: FieldRegion; src?: string }) {
  const w = useWorkflowText();
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!region || !src) return;
    let active = true;
    const image = new Image();
    image.onload = () => {
      if (!active || !canvas.current) return;
      const [x0, y0, x1, y1] = region.rect;
      const padding = .02;
      const left = Math.max(0, x0 - padding) * image.width, top = Math.max(0, y0 - padding) * image.height;
      const width = Math.max(1, (Math.min(1, x1 + padding) - Math.max(0, x0 - padding)) * image.width);
      const height = Math.max(1, (Math.min(1, y1 + padding) - Math.max(0, y0 - padding)) * image.height);
      canvas.current.width = Math.round(width); canvas.current.height = Math.round(height);
      canvas.current.getContext("2d")?.drawImage(image, left, top, width, height, 0, 0, width, height);
    };
    image.src = src;
    return () => { active = false; };
  }, [region, src]);
  const [zoom, setZoom] = useState(false);
  return <div className="panel panel-body workflow-stack"><strong>{w.reviewCrop}: {field}</strong>
    {region && src ? <><canvas ref={canvas} className="workflow-crop" style={zoom ? { maxHeight: "none" } : undefined} role="img" aria-label={field} /><button className="button button-secondary" type="button" onClick={() => setZoom(!zoom)}>{zoom ? "−" : "+"}</button></> : <p>{w.noRegion}</p>}
  </div>;
}
