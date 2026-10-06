"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Dialog } from "@/components/Dialog";
import { Forbidden } from "@/components/Forbidden";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { useWords } from "@/lib/maintenance-text";
import { useSession } from "@/lib/session";
import { saveBlob, workflowJson, workflowRequest } from "@/lib/workflow";

type Status = { storage_bytes: number; free_bytes: number; missing_files: number; unreferenced_files: number; queue: Record<string, number>; backup: { created_at?: string; verified_at?: string; restored_at?: string }; restore_pending: boolean; database: string; ocr: string; queue_enabled: boolean };
const size = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;
export default function MaintenancePage() {
  const words = useWords();
  const { can } = useSession();
  const status = useQuery({ queryKey: ["maintenance"], queryFn: () => workflowJson<Status>("/api/maintenance"), enabled: can("settings.manage"), refetchInterval: 15_000 });
  const [password, setPassword] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"restore" | "cleanup" | null>(null);
  const [confirmation, setConfirmation] = useState("");
  if (!can("settings.manage")) return <Forbidden />;
  const action = async (operation: () => Promise<void>) => {
    setBusy(true); setError(""); setMessage("");
    try { await operation(); await status.refetch(); }
    catch (error) { setError(error instanceof Error ? error.message : "Erro"); }
    finally { setBusy(false); }
  };
  const body = () => { const form = new FormData(); form.set("password", password); if (file) form.set("file", file); form.set("confirmation", confirmation); return form; };
  const create = () => action(async () => {
    const response = await workflowRequest("/api/maintenance/backups", { method: "POST", body: body() });
    saveBlob(await response.blob(), `legivel-backup-${new Date().toISOString().slice(0, 10)}.lgb`);
    setMessage(words("Backup baixado. Guarde o arquivo e a senha em locais separados e teste a recuperação.", "Backup downloaded. Keep the file and password separately and test recovery."));
  });
  const verify = () => action(async () => {
    setVerified(false);
    const result = await (await workflowRequest("/api/maintenance/backups/verify", { method: "POST", body: body() })).json();
    setVerified(true); setMessage(`${result.detail} ${result.files} ${words("arquivos", "files")}; ${result.rows} ${words("linhas", "rows")}.`);
  });
  const confirmAction = () => action(async () => {
    if (dialog === "restore") {
      const result = await (await workflowRequest("/api/maintenance/backups/restore", { method: "POST", body: body() })).json();
      setMessage(result.detail); setVerified(false);
    } else {
      const result = await workflowJson<{ removed: number }>("/api/maintenance/cleanup", "POST");
      setMessage(`${result.removed} ${words("arquivos temporários removidos.", "temporary files removed.")}`);
    }
    setDialog(null); setConfirmation("");
  });
  const data = status.data;
  return <div className={page.page}>
    <PageHead title={words("Manutenção e backups", "Maintenance and backups")} description={words("Confira os serviços, proteja os dados e teste a recuperação.", "Check services, protect data and test recovery.")} />
    {status.error && <p role="alert">{status.error.message}</p>}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {busy && <p role="status">{words("Operação em andamento…", "Operation in progress…")}</p>}
    {data && <section className="panel panel-body workflow-stack">
      <h2>{words("Estado do servidor", "Server status")}</h2>
      <dl className="workflow-stats">
        <div><dt>{words("Banco", "Database")}</dt><dd>{data.database}</dd></div>
        <div><dt>OCR</dt><dd>{data.ocr}</dd></div>
        <div><dt>{words("Armazenamento usado", "Storage used")}</dt><dd>{size(data.storage_bytes)}</dd></div>
        <div><dt>{words("Espaço livre", "Free space")}</dt><dd>{size(data.free_bytes)}</dd></div>
        <div><dt>{words("Arquivos ausentes", "Missing files")}</dt><dd>{data.missing_files}</dd></div>
        <div><dt>{words("Arquivos sem referência", "Unreferenced files")}</dt><dd>{data.unreferenced_files}</dd></div>
        <div><dt>{words("Falhas na fila", "Failed jobs")}</dt><dd>{data.queue.failed ?? 0}</dd></div>
        <div><dt>{words("Fila ativa", "Queue enabled")}</dt><dd>{data.queue_enabled ? words("Sim", "Yes") : words("Não", "No")}</dd></div>
        <div><dt>{words("Último backup", "Last backup")}</dt><dd>{data.backup.created_at ? new Date(data.backup.created_at).toLocaleString() : "—"}</dd></div>
        <div><dt>{words("Recuperação testada", "Recovery tested")}</dt><dd>{data.backup.verified_at ? new Date(data.backup.verified_at).toLocaleString() : "—"}</dd></div>
      </dl>
      <button className="button button-secondary" disabled={busy} type="button" onClick={() => setDialog("cleanup")}>{words("Limpar arquivos temporários", "Clean temporary files")}</button>
      <p className="muted">{words("Remove somente arquivos sem referência há mais de 24 horas. Imagens e tarefas com falha continuam guardadas.", "Only unreferenced files older than 24 hours are removed. Images and failed jobs are retained.")}</p>
    </section>}
    <section className="panel panel-body workflow-stack" aria-busy={busy}>
      <h2>{words("Backup e recuperação", "Backup and recovery")}</h2>
      <p>{words("O arquivo criptografado inclui banco, imagens, configurações e chaves. Use uma senha de pelo menos 12 caracteres. Limite do painel: 200 MB; acima disso, use os scripts do servidor.", "The encrypted file includes the database, images, settings and keys. Use a password with at least 12 characters. Panel limit: 200 MB; larger installations use the server scripts.")}</p>
      <label className="field">{words("Senha do backup", "Backup password")}<input type="password" minLength={12} maxLength={256} value={password} disabled={busy} autoComplete="off" onChange={(event) => { setPassword(event.target.value); setVerified(false); }} /></label>
      <button className="button" disabled={busy || password.length < 12 || !!data?.restore_pending} type="button" onClick={create}>{words("Criar e baixar backup", "Create and download backup")}</button>
      <label className="field">{words("Backup para conferir ou restaurar", "Backup to verify or restore")}<input type="file" accept=".lgb" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setVerified(false); }} /></label>
      <div className="workflow-row">
        <button className="button button-secondary" disabled={busy || !file || password.length < 12} type="button" onClick={verify}>{words("Testar recuperação", "Test recovery")}</button>
        <button className="button button-danger" disabled={busy || !verified || !!data?.restore_pending} type="button" onClick={() => setDialog("restore")}>{words("Preparar restauração", "Prepare restoration")}</button>
      </div>
      {data?.restore_pending && <div className="workflow-stack" role="status"><p>{words("Restauração preparada. Reinicie a API no servidor para aplicar. No Docker: docker compose restart api. As gravações e a fila estão pausadas.", "Restoration prepared. Restart the API on the server to apply it. In Docker: docker compose restart api. Writes and the queue are paused.")}</p><button className="button button-secondary" disabled={busy} type="button" onClick={() => action(async () => { await workflowJson("/api/maintenance/backups/restore", "DELETE"); setMessage(words("Restauração cancelada.", "Restoration cancelled.")); })}>{words("Cancelar restauração", "Cancel restoration")}</button></div>}
    </section>
    <Dialog open={!!dialog} title={dialog === "restore" ? words("Restaurar dados?", "Restore data?") : words("Limpar temporários?", "Clean temporary files?")} busy={busy} onClose={() => { setDialog(null); setConfirmation(""); }} actions={<>
      <button className="button button-secondary" disabled={busy} type="button" onClick={() => setDialog(null)}>{words("Cancelar", "Cancel")}</button>
      <button className="button button-danger" disabled={busy || (dialog === "restore" && confirmation !== "RESTAURAR")} type="button" onClick={confirmAction}>{words("Confirmar", "Confirm")}</button></>}>
      {dialog === "restore" ? <><p>{words("O próximo reinício substituirá banco e imagens pelo backup selecionado. Alterações posteriores ao backup serão perdidas. Baixe um backup atual antes de continuar.", "The next restart will replace the database and images with this backup. Changes made after the backup will be lost. Download a current backup first.")}</p><label className="field">{words("Digite RESTAURAR", "Type RESTAURAR")}<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label></> : <p>{words("Remover arquivos antigos que não pertencem a documentos, tarefas ou à identidade visual?", "Remove old files that do not belong to documents, jobs or branding?")}</p>}
    </Dialog>
  </div>;
}
