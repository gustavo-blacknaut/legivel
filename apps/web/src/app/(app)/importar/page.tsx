"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHead } from "@/components/PageHead";
import { Forbidden } from "@/components/Forbidden";
import { useSession } from "@/lib/session";
import { enqueue, workflowRequest } from "@/lib/workflow";
import { useWords } from "@/lib/maintenance-text";
import page from "@/components/Page.module.css";

type Choice = { page: number; rotation: number; selected: boolean };
function imageFile(base64: string, name: string): File {
  const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
  return new File([bytes], name, { type: "image/jpeg" });
}
export default function ImportPage() {
  const words = useWords();
  const { can } = useSession();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [choices, setChoices] = useState<Choice[]>([]);
  const [module, setModule] = useState("books");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{ page: number; src: string } | null>(null);
  if (!can("documents.upload")) return <Forbidden />;
  const form = () => { const result = new FormData(); if (file) result.set("file", file); result.set("password", password); return result; };
  const inspect = async () => {
    if (!file) return;
    setBusy(true); setError(""); setChoices([]); setPreview(null);
    try {
      const result = await (await workflowRequest("/api/pdf/inspect", { method: "POST", body: form() })).json();
      setChoices(Array.from({ length: result.pages }, (_, index) => ({ page: index + 1, rotation: 0, selected: index < 50 })));
    } catch (error) { setError(error instanceof Error ? error.message : "Erro"); }
    finally { setBusy(false); }
  };
  const render = async (selection: Choice[], thumbnail = false) => {
    const body = form(); body.set("selections", JSON.stringify(selection.map(({ page, rotation }) => ({ page, rotation })))); body.set("preview", String(thumbnail));
    return (await workflowRequest("/api/pdf/render", { method: "POST", body })).json() as Promise<{ pages: { page: number; image: string }[] }>;
  };
  const showPreview = async (choice: Choice) => {
    setBusy(true); setError("");
    try { const result = await render([choice], true); const image = result.pages[0]; if (!image) throw new Error("Prévia indisponível"); setPreview({ page: choice.page, src: `data:image/jpeg;base64,${image.image}` }); }
    catch (error) { setError(error instanceof Error ? error.message : "Erro"); }
    finally { setBusy(false); }
  };
  const send = async () => {
    setBusy(true); setError("");
    try {
      const selected = choices.filter((choice) => choice.selected);
      if (!selected.length || selected.length > (module === "documents" ? 2 : 50)) throw new Error(words("Selecione de 1 a 50 páginas; para identidade, no máximo 2.", "Select 1 to 50 pages; identity documents allow at most 2."));
      const result = await render(selected);
      const body = new FormData(); body.set("module", module); body.set("duplicate", "keep");
      result.pages.forEach((item, index) => body.append(module === "documents" ? (index === 0 ? "front" : "back") : "pages", imageFile(item.image, `${file?.name ?? "pdf"}-pagina-${item.page}.jpg`)));
      await enqueue(body); router.push("/fila");
    } catch (error) { setError(error instanceof Error ? error.message : "Erro"); }
    finally { setBusy(false); }
  };
  return <div className={page.page}>
    <PageHead title={words("Importar PDF", "Import PDF")} description={words("Escolha as páginas e ajuste a orientação antes da leitura.", "Choose pages and adjust their orientation before reading.")} />
    <section className="panel panel-body workflow-stack" aria-busy={busy}>
      <label className="field">{words("Arquivo PDF (até 100 MB)", "PDF file (up to 100 MB)")}<input type="file" accept="application/pdf,.pdf" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setChoices([]); setPreview(null); }} /></label>
      <label className="field">{words("Senha do PDF, se houver", "PDF password, if needed")}<input type="password" value={password} onChange={(event) => { setPassword(event.target.value); setChoices([]); }} autoComplete="off" /></label>
      <button className="button" type="button" disabled={!file || busy} onClick={inspect}>{words("Ver páginas", "View pages")}</button>
      {error && <p role="alert">{error}</p>}
      {busy && <p role="status">{words("Preparando páginas…", "Preparing pages…")}</p>}
      {!!choices.length && <>
        <label className="field">{words("Tipo de leitura", "Reading type")}<select value={module} disabled={busy} onChange={(event) => setModule(event.target.value)}>
          <option value="books">{words("Livros e textos", "Books and text")}</option><option value="scanner">{words("Scanner", "Scanner")}</option><option value="documents">{words("Identidade: frente e verso", "Identity: front and back")}</option>
        </select></label>
        <p role="status">{choices.filter((choice) => choice.selected).length} {words("páginas selecionadas", "pages selected")}</p>
        <div className="workflow-row"><button className="button button-secondary" disabled={busy} type="button" onClick={() => setChoices(choices.map((choice, index) => ({ ...choice, selected: index < 50 })))}>{words("Selecionar até 50", "Select up to 50")}</button><button className="button button-secondary" disabled={busy} type="button" onClick={() => setChoices(choices.map((choice) => ({ ...choice, selected: false })))}>{words("Limpar seleção", "Clear selection")}</button></div>
        {choices.map((choice) => <div className="workflow-row workflow-item" key={choice.page}>
          <label className="check"><input type="checkbox" disabled={busy} checked={choice.selected} onChange={(event) => setChoices(choices.map((item) => item.page === choice.page ? { ...item, selected: event.target.checked } : item))} />{words("Página", "Page")} {choice.page}</label>
          <label className="field">{words("Rotação", "Rotation")} {choice.page}<select disabled={busy} value={choice.rotation} onChange={(event) => { setPreview(null); setChoices(choices.map((item) => item.page === choice.page ? { ...item, rotation: Number(event.target.value) } : item)); }}>{[0, 90, 180, 270].map((value) => <option key={value} value={value}>{value}°</option>)}</select></label>
          <button className="button button-secondary" disabled={busy} type="button" onClick={() => showPreview(choice)}>{words("Prévia", "Preview")} {choice.page}</button>
        </div>)}
        {preview && <figure><img src={preview.src} alt={`${words("Prévia da página", "Page preview")} ${preview.page}`} style={{ maxWidth: "100%", maxHeight: 480 }} /><figcaption>{words("Página", "Page")} {preview.page}</figcaption></figure>}
        <button className="button" type="button" disabled={busy || !choices.some((choice) => choice.selected)} onClick={send}>{words("Enviar páginas para leitura", "Send pages for reading")}</button>
        <p className="muted">{words("Até 100 páginas por PDF e 50 por envio. As páginas selecionadas serão guardadas como imagens; o PDF original permanece com você.", "Up to 100 pages per PDF and 50 per upload. Selected pages are stored as images; you keep the original PDF.")}</p>
      </>}
    </section>
  </div>;
}
