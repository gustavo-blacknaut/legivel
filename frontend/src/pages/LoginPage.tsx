import { Lock } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { Brand } from "../components/AppShell";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível entrar.");
      setBusy(false);
    }
  };

  return (
    <main className="login">
      <div className="login-box">
        <Brand />
        <form onSubmit={submit}>
          <h1>Entrar</h1>
          {error && <div className="alert alert-danger">{error}</div>}
          <div className="field">
            <label className="field-label" htmlFor="username">Usuário</label>
            <input id="username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" autoCapitalize="none" autoFocus required />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="password">Senha</label>
            <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
          </div>
          <button className="button button-lg button-block" type="submit" disabled={busy}>
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>
        <p className="login-note">
          <Lock size={12} />
          Dados armazenados somente neste servidor, criptografados
        </p>
      </div>
    </main>
  );
}
