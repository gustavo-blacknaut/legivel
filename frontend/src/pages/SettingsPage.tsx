import { LaptopMinimal, LogOut, Monitor, Moon, Save, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { PageHead } from "../components/AppShell";
import { useToast } from "../components/Toast";
import { describeDevice, formatDateTime, getTimeZone, setTimeZone } from "../format";
import { useTheme, type ThemePreference } from "../theme";
import type { SessionInfo, SystemInfo } from "../types";

const THEMES: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
  { value: "system", label: "Sistema", icon: Monitor },
];
const BRAZIL_TIMEZONES = [
  "America/Sao_Paulo",
  "America/Bahia",
  "America/Fortaleza",
  "America/Recife",
  "America/Belem",
  "America/Manaus",
  "America/Cuiaba",
  "America/Campo_Grande",
  "America/Porto_Velho",
  "America/Boa_Vista",
  "America/Rio_Branco",
  "America/Noronha",
];

function currentTimeIn(timeZone: string): string {
  return new Date().toLocaleString("pt-BR", { timeZone, hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

export function SettingsPage() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const { preference, setPreference } = useTheme();
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null);
  const [timezones, setTimezones] = useState<string[]>(BRAZIL_TIMEZONES);
  const [timezone, setTimezone] = useState(getTimeZone());
  const [savedTimezone, setSavedTimezone] = useState(getTimeZone());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.system().then(setSystem).catch(() => undefined);
    api.sessions().then(setSessions).catch(() => setSessions([]));
    api.timezones().then(setTimezones).catch(() => undefined);
  }, []);

  const saveTimezone = async () => {
    setSaving(true);
    try {
      const saved = await api.saveSettings({ timezone });
      setTimeZone(saved.timezone);
      setSavedTimezone(saved.timezone);
      toast("Fuso horário atualizado.");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Não foi possível salvar.", "error");
    } finally {
      setSaving(false);
    }
  };

  const revokeOthers = async () => {
    const result = await api.revokeOtherSessions();
    toast(result.revoked ? `${result.revoked} sessão(ões) encerrada(s).` : "Nenhuma outra sessão ativa.");
    setSessions(await api.sessions());
  };

  const others = timezones.filter((zone) => !BRAZIL_TIMEZONES.includes(zone));

  return (
    <div className="page">
      <PageHead title="Administração" description={`Conectado como ${user?.username}.`} />
      <div className="settings">
        <section className="panel">
          <div className="panel-head">
            <h2>Fuso horário</h2>
          </div>
          <div className="panel-body stack">
            <p className="muted flush">Usado em todas as datas e horas exibidas, inclusive na auditoria.</p>
            <div className="actions-row">
              <label className="field grow">
                <span className="field-label">Local</span>
                <select value={timezone} onChange={(event) => setTimezone(event.target.value)}>
                  <optgroup label="Brasil">
                    {BRAZIL_TIMEZONES.map((zone) => (
                      <option key={zone} value={zone}>
                        {zone.replace("America/", "").replace("_", " ")} ({currentTimeIn(zone)})
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Outros">
                    {others.map((zone) => (
                      <option key={zone} value={zone}>
                        {zone}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </label>
              <button className="button" type="button" onClick={saveTimezone} disabled={saving || timezone === savedTimezone}>
                <Save size={16} strokeWidth={1.75} />
                Salvar
              </button>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Aparência</h2>
          </div>
          <div className="panel-body">
            <div className="segmented" role="group" aria-label="Tema">
              {THEMES.map(({ value, label, icon: Icon }) => (
                <button key={value} type="button" aria-pressed={preference === value} onClick={() => setPreference(value)}>
                  <Icon size={14} strokeWidth={1.75} />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Sessões ativas</h2>
            <button className="button button-secondary" type="button" onClick={revokeOthers} disabled={!sessions || sessions.length < 2}>
              Encerrar as outras
            </button>
          </div>
          <ul className="session-list">
            {(sessions ?? []).map((item) => (
              <li key={item.id}>
                <LaptopMinimal size={18} strokeWidth={1.5} />
                <span className="session-main">
                  <strong>
                    {describeDevice(item.user_agent)}
                    {item.current && <span className="tag">Este aparelho</span>}
                  </strong>
                  <span className="muted">
                    {item.ip_address ?? "IP desconhecido"} · entrou em {formatDateTime(item.created_at)} · expira em{" "}
                    {formatDateTime(item.expires_at)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <div className="panel-body">
            <p className="muted flush">
              A sessão continua ativa por até 30 dias neste aparelho e é renovada automaticamente enquanto você usa o sistema.
            </p>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Servidor</h2>
          </div>
          <dl className="meta-list panel-body">
            <dt>Motor de OCR</dt>
            <dd>{system ? `PaddleOCR local · ${system.ocr_device === "cpu" ? "processador (CPU)" : `placa de vídeo (${system.ocr_device})`}` : "—"}</dd>
            <dt>Armazenamento</dt>
            <dd>{system?.encrypted_storage ? "Imagens criptografadas com AES-256-GCM" : "—"}</dd>
            <dt>Limite de envio</dt>
            <dd>{system ? `${system.max_upload_mb} MB por imagem` : "—"}</dd>
          </dl>
        </section>

        <button className="button button-danger-ghost settings-logout" type="button" onClick={logout}>
          <LogOut size={16} strokeWidth={1.75} />
          Sair deste aparelho
        </button>
      </div>
    </div>
  );
}
