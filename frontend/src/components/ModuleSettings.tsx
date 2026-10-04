import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { LanguageInfo, Settings } from "../types";
import { useToast } from "./Toast";

export function ModuleSettings() {
  const toast = useToast();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [languages, setLanguages] = useState<LanguageInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [defaultLanguage, setDefaultLanguage] = useState("auto");

  useEffect(() => {
    api.settings().then((result) => {
      setSettings(result);
      setSelected(result.languages);
      setDefaultLanguage(result.default_language);
    });
    api.languages().then(setLanguages).catch(() => undefined);
  }, []);

  if (!settings) return null;

  const toggle = (code: string) =>
    setSelected((current) => (current.includes(code) ? current.filter((item) => item !== code) : [...current, code]));

  const saveLanguages = async () => {
    try {
      const result = await api.saveSettings({ languages: selected, default_language: defaultLanguage });
      setSettings(result);
      toast("Idiomas atualizados.");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Não foi possível salvar.", "error");
    }
  };

  const toggleCards = async (enabled: boolean) => {
    try {
      setSettings(await api.saveSettings({ store_card_numbers: enabled }));
      toast(enabled ? "Números de cartão serão guardados criptografados." : "Números de cartão não serão mais guardados.");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Não foi possível salvar.", "error");
    }
  };

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h2>Idiomas do OCR</h2>
        </div>
        <div className="panel-body stack">
          <p className="muted flush">
            Os idiomas marcados entram na detecção automática. Cada escrita (latina, cirílica, árabe, asiáticas) usa um pacote próprio, baixado no primeiro uso.
          </p>
          <div className="settings-checks">
            {languages.map((language) => (
              <label key={language.code} className="check">
                <input type="checkbox" checked={selected.includes(language.code)} onChange={() => toggle(language.code)} />
                {language.name}
              </label>
            ))}
          </div>
          <div className="actions-row">
            <label className="field grow">
              <span className="field-label">Idioma padrão dos envios</span>
              <select value={defaultLanguage} onChange={(event) => setDefaultLanguage(event.target.value)}>
                <option value="auto">Detectar automaticamente</option>
                {languages
                  .filter((language) => selected.includes(language.code))
                  .map((language) => (
                    <option key={language.code} value={language.code}>
                      {language.name}
                    </option>
                  ))}
              </select>
            </label>
            <button className="button" type="button" onClick={saveLanguages} disabled={selected.length === 0}>
              <Save size={16} strokeWidth={1.75} />
              Salvar
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Cartões</h2>
        </div>
        <div className="panel-body stack">
          <p className="muted flush">
            Por padrão só a bandeira e os 4 últimos dígitos são guardados. O CVV nunca é lido. Guardar o número completo exige a chave
            LINCE_CARD_ENCRYPTION_KEY no servidor, separada da chave das imagens.
          </p>
          <label className="check">
            <input
              type="checkbox"
              checked={settings.store_card_numbers}
              disabled={!settings.card_key_configured}
              onChange={(event) => toggleCards(event.target.checked)}
            />
            Guardar o número completo, criptografado
            {!settings.card_key_configured && <span className="tag">Chave não configurada</span>}
          </label>
        </div>
      </section>
    </>
  );
}
