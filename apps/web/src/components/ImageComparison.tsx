"use client";
import { useState } from "react";
import { useSession } from "@/lib/session";
import { useWords } from "@/lib/maintenance-text";
import { Dialog } from "./Dialog";

export function ImageComparison({ pages }: { pages: { label: string; original: string | null; processed: string | null }[] }) {
  const words = useWords();
  const { can } = useSession();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [failed, setFailed] = useState(false);
  const images = pages.filter((page) => page.original && page.processed && page.original !== page.processed);
  if (!can("images.original") || !images.length) return null;
  const current = images[selected] ?? images[0];
  if (!current) return null;
  return <>
    <button type="button" className="button button-secondary" onClick={() => { setFailed(false); setZoom(1); setOpen(true); }}>{words("Comparar original e tratada", "Compare original and processed")}</button>
    <Dialog open={open} title={words("Comparação de imagens", "Image comparison")} large onClose={() => setOpen(false)} actions={<button className="button button-secondary" type="button" onClick={() => setOpen(false)}>{words("Fechar", "Close")}</button>}>
      <div className="workflow-row">
        <label className="field">{words("Página", "Page")}<select value={selected} onChange={(event) => { setSelected(Number(event.target.value)); setFailed(false); setZoom(1); }}>{images.map((item, index) => <option key={index} value={index}>{item.label}</option>)}</select></label>
        <label className="field">{words("Ampliação", "Zoom")}<select value={zoom} onChange={(event) => setZoom(Number(event.target.value))}>{[1, 1.5, 2, 3].map((value) => <option key={value} value={value}>{value * 100}%</option>)}</select></label>
      </div>
      {failed && <p role="alert">{words("Não foi possível carregar uma imagem. Feche e tente novamente.", "An image could not be loaded. Close and try again.")}</p>}
      {open && <div className="comparison-grid" key={selected}>{[[words("Original", "Original"), current.original], [words("Tratada", "Processed"), current.processed]].map(([label, src]) => <figure key={label}>
        <figcaption>{label}</figcaption><div className="comparison-scroll" tabIndex={0} role="region" aria-label={words(`Imagem ${label}: use as setas para navegar`, `${label} image: use arrow keys to scroll`)}><img src={src!} alt={`${current.label} — ${label}`} style={{ width: `${zoom * 100}%` }} onError={() => setFailed(true)} /></div>
      </figure>)}</div>}
    </Dialog>
  </>;
}
