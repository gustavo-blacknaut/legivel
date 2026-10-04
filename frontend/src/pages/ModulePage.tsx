import { ScanText, SearchX, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { EmptyState, ListBar, SkeletonRows } from "../components/ListState";
import { PagePicker } from "../components/PagePicker";
import { Confidence, StatusLabel } from "../components/Status";
import { formatDateTime } from "../format";
import type { LanguageInfo, ModuleInfo } from "../types";
import { useInfiniteList, useSentinel } from "../useInfiniteList";

const SCANNER_MODES = [
  { value: "color", label: "Colorido" },
  { value: "gray", label: "Escala de cinza" },
  { value: "bw", label: "Preto e branco" },
];

export function ModulePage() {
  const key = useParams().key ?? "";
  const navigate = useNavigate();
  const [module, setModule] = useState<ModuleInfo | null>(null);
  const [languages, setLanguages] = useState<LanguageInfo[]>([]);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [language, setLanguage] = useState("auto");
  const [mode, setMode] = useState("color");
  const [kind, setKind] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const filters = useMemo(() => new URLSearchParams({ module: key }), [key]);
  const list = useInfiniteList(api.records, filters);
  const sentinel = useSentinel(list.loadMore, list.hasMore);

  useEffect(() => {
    setFiles([]);
    setError(null);
    api.modules().then((modules) => setModule(modules.find((item) => item.key === key) ?? null));
    api.languages().then(setLanguages).catch(() => undefined);
    api.settings().then((settings) => {
      setEnabled(settings.languages);
      setLanguage(settings.default_language);
    });
  }, [key]);

  if (!module) return <div className="spinner spinner-page" />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const form = new FormData();
    form.append("module", module.key);
    form.append("language", language);
    form.append("options", JSON.stringify({ mode, kind: kind || undefined }));
    files.forEach((file) => form.append("pages", file));
    setBusy(true);
    setError(null);
    try {
      const record = await api.uploadRecord(form);
      navigate(`/registros/${record.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao enviar.");
      setBusy(false);
    }
  };

  const languageOptions = languages.filter((item) => enabled.includes(item.code));

  return (
    <div className="page">
      <PageHead title={module.name} description={module.description} />
      <div className="module-grid">
        <form className="panel" onSubmit={submit}>
          <div className="panel-head">
            <h2>Novo envio</h2>
          </div>
          <div className="panel-body stack">
            {module.key === "cards" && (
              <div className="alert alert-warning">
                <ShieldAlert size={16} />
                Envie só a frente. O código de segurança (CVV) nunca é lido nem guardado, e a foto do cartão é descartada após a leitura.
              </div>
            )}
            {error && <div className="alert alert-danger">{error}</div>}
            <PagePicker
              files={files}
              onChange={setFiles}
              maxPages={module.max_pages}
              labels={module.page_labels}
              allowCamera={module.key === "scanner" || module.key === "books"}
            />
            <div className="form-grid">
              <label className="field">
                <span className="field-label">Idioma</span>
                <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                  <option value="auto">Detectar automaticamente</option>
                  {languageOptions.map((item) => (
                    <option key={item.code} value={item.code}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              {module.key === "scanner" && (
                <label className="field">
                  <span className="field-label">Realce</span>
                  <select value={mode} onChange={(event) => setMode(event.target.value)}>
                    {SCANNER_MODES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {Object.keys(module.kinds).length > 0 && (
                <label className="field">
                  <span className="field-label">Tipo</span>
                  <select value={kind} onChange={(event) => setKind(event.target.value)}>
                    <option value="">Identificar automaticamente</option>
                    {Object.entries(module.kinds).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </div>
          <div className="form-footer">
            <span className="footer-note">{files.length > 0 && `${files.length} imagem(ns) selecionada(s)`}</span>
            <button className="button" type="submit" disabled={busy || files.length === 0}>
              <ScanText size={16} strokeWidth={1.75} />
              {busy ? "Processando…" : "Processar"}
            </button>
          </div>
        </form>

        <section className="panel list-panel module-list">
          <div className="panel-head">
            <h2>Registros</h2>
          </div>
          <ListBar total={list.total} singular="registro" pluralLabel="registros" filtered={false} onClear={() => undefined} />
          <div className="list-scroll">
            {list.total === null ? (
              <SkeletonRows count={4} />
            ) : list.items.length === 0 ? (
              <EmptyState icon={SearchX} title="Nada processado ainda" text="Os registros deste módulo aparecem aqui." />
            ) : (
              <ul className="result-list">
                {list.items.map((record) => (
                  <li key={record.id}>
                    <Link to={`/registros/${record.id}`} className="result">
                      {record.thumbnail_url ? <img className="thumb" src={record.thumbnail_url} alt="" loading="lazy" /> : <span className="thumb" />}
                      <span className="result-main">
                        <strong>{record.title || "Sem título"}</strong>
                        <span className="muted">
                          {formatDateTime(record.created_at)}
                          {record.page_count > 1 && ` · ${record.page_count} páginas`}
                          {record.confidence !== null && <> · <Confidence value={record.confidence} /></>}
                        </span>
                      </span>
                      <StatusLabel status={record.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <div ref={sentinel} className="list-sentinel" />
          </div>
        </section>
      </div>
      {busy && (
        <div className="processing" role="status">
          <div className="processing-card">
            <span className="spinner" />
            <span>
              <strong>Processando</strong>
              <span>{files.length > 1 ? `Lendo ${files.length} páginas. Isso pode levar alguns minutos.` : "Lendo a imagem."}</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
