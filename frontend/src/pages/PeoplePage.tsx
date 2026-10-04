import { FilePlus2, SearchX, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { DeleteDialog } from "../components/DeleteDialog";
import { ListFilters, useUrlFilters } from "../components/ListFilters";
import { EmptyState, ListBar, SkeletonRows } from "../components/ListState";
import { StatusLabel } from "../components/Status";
import { useToast } from "../components/Toast";
import { DOCUMENT_TYPE_LABELS, formatCpf, formatDate, initials } from "../format";
import type { Person } from "../types";
import { useInfiniteList, useSentinel } from "../useInfiniteList";

export function PeoplePage() {
  const controls = useUrlFilters();
  const navigate = useNavigate();
  const toast = useToast();
  const list = useInfiniteList(api.people, controls.filters);
  const sentinel = useSentinel(list.loadMore, list.hasMore);
  const [pending, setPending] = useState<Person | null>(null);

  const remove = async () => {
    if (!pending) return;
    await api.deletePerson(pending.id);
    list.remove(pending.id);
    toast(`${pending.full_name ?? "Pessoa"} apagada.`);
    setPending(null);
  };

  return (
    <div className="page page-fill">
      <PageHead
        title="Pessoas"
        description="Cadastro consolidado por CPF a partir dos documentos processados."
        actions={
          <Link to="/novo" className="button hide-compact">
            <FilePlus2 size={16} strokeWidth={1.75} />
            Novo documento
          </Link>
        }
      />
      <section className="panel list-panel">
        <ListFilters controls={controls} dateLabel="Período de cadastro" searchPlaceholder="Nome ou CPF" />
        <ListBar total={list.total} singular="pessoa" pluralLabel="pessoas" filtered={controls.active} onClear={controls.clear} />
        <div className="list-scroll">
          {list.total === null && !list.error ? (
            <SkeletonRows />
          ) : list.items.length === 0 ? (
            controls.active ? (
              <EmptyState icon={SearchX} title="Nenhuma pessoa encontrada" text="Ajuste a busca ou limpe os filtros para ver todo o cadastro." />
            ) : (
              <EmptyState
                icon={Users}
                title="Nenhuma pessoa cadastrada"
                text="As pessoas aparecem aqui assim que um documento com CPF válido é processado."
                action={
                  <Link to="/novo" className="button">
                    <FilePlus2 size={16} strokeWidth={1.75} />
                    Enviar primeiro documento
                  </Link>
                }
              />
            )
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th className="w-150">CPF</th>
                  <th className="w-130 col-optional">Documentos</th>
                  <th className="w-190">Status</th>
                  <th className="w-120 col-optional">Cadastro</th>
                  <th className="cell-actions"><span className="visually-hidden">Ações</span></th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((person) => (
                  <tr key={person.id} onClick={() => navigate(`/pessoas/${person.id}`)}>
                    <td className="cell-primary">
                      <Link to={`/pessoas/${person.id}`} className="cell-name" onClick={(event) => event.stopPropagation()}>
                        <span className="avatar" aria-hidden="true">{initials(person.full_name)}</span>
                        <span>{person.full_name || "Sem nome"}</span>
                      </Link>
                    </td>
                    <td className="cell-meta mono">{formatCpf(person.cpf) || "—"}</td>
                    <td className="cell-meta col-optional">
                      {person.doc_types.map((type) => DOCUMENT_TYPE_LABELS[type] ?? type.toUpperCase()).join(" · ") || "—"}
                    </td>
                    <td className="cell-meta"><StatusLabel status={person.status} /></td>
                    <td className="cell-meta col-optional">{formatDate(person.created_at)}</td>
                    <td className="cell-actions">
                      <button
                        className="icon-button"
                        type="button"
                        aria-label={`Apagar ${person.full_name ?? "pessoa"}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setPending(person);
                        }}
                      >
                        <Trash2 size={16} strokeWidth={1.75} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div ref={sentinel} className="list-sentinel" />
          {list.loading && list.items.length > 0 && <div className="list-loading">Carregando mais…</div>}
          {list.error && <div className="list-loading">{list.error}</div>}
        </div>
      </section>
      <DeleteDialog
        open={pending !== null}
        title="Apagar pessoa e documentos"
        description={
          <>
            <strong>{pending?.full_name ?? "Esta pessoa"}</strong> será removida do cadastro junto com tudo o que está vinculado a ela.
          </>
        }
        documents={pending?.documents ?? 0}
        images={pending?.images ?? 0}
        confirmationValues={[pending?.full_name ?? "", pending?.cpf ?? ""]}
        confirmationLabel="Para confirmar, digite o nome completo ou o CPF"
        onConfirm={remove}
        onClose={() => setPending(null)}
      />
    </div>
  );
}
