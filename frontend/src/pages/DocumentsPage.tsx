import { FilePlus2, Files, SearchX } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { ListFilters, useUrlFilters } from "../components/ListFilters";
import { EmptyState, ListBar, SkeletonRows } from "../components/ListState";
import { Confidence, StatusLabel } from "../components/Status";
import { DOCUMENT_TYPE_LABELS, formatCpf, formatDateTime } from "../format";
import { useInfiniteList, useSentinel } from "../useInfiniteList";

export function DocumentsPage() {
  const controls = useUrlFilters();
  const navigate = useNavigate();
  const list = useInfiniteList(api.documents, controls.filters);
  const sentinel = useSentinel(list.loadMore, list.hasMore);

  return (
    <div className="page page-fill">
      <PageHead
        title="Documentos"
        description="Todos os documentos processados, do mais recente ao mais antigo."
        actions={
          <Link to="/novo" className="button hide-compact">
            <FilePlus2 size={16} strokeWidth={1.75} />
            Novo documento
          </Link>
        }
      />
      <section className="panel list-panel">
        <ListFilters controls={controls} dateLabel="Período de processamento" searchPlaceholder="Nome ou CPF" />
        <ListBar total={list.total} singular="documento" pluralLabel="documentos" filtered={controls.active} onClear={controls.clear} />
        <div className="list-scroll">
          {list.total === null && !list.error ? (
            <SkeletonRows />
          ) : list.items.length === 0 ? (
            controls.active ? (
              <EmptyState icon={SearchX} title="Nenhum documento encontrado" text="Ajuste a busca ou limpe os filtros." />
            ) : (
              <EmptyState
                icon={Files}
                title="Nenhum documento processado"
                text="Envie a frente e o verso de um RG, CNH ou cartão CPF para começar."
                action={
                  <Link to="/novo" className="button">
                    <FilePlus2 size={16} strokeWidth={1.75} />
                    Novo documento
                  </Link>
                }
              />
            )
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Titular</th>
                  <th className="w-80">Tipo</th>
                  <th className="w-150">CPF</th>
                  <th className="w-100 col-optional">Confiança</th>
                  <th className="w-190">Status</th>
                  <th className="w-150 col-optional">Processado em</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((document) => (
                  <tr key={document.id} onClick={() => navigate(`/documentos/${document.id}`)}>
                    <td className="cell-primary">
                      <Link to={`/documentos/${document.id}`} className="cell-name" onClick={(event) => event.stopPropagation()}>
                        {document.thumbnail_url ? <img className="thumb" src={document.thumbnail_url} alt="" loading="lazy" /> : <span className="thumb" />}
                        <span>{document.full_name || "Titular não identificado"}</span>
                      </Link>
                    </td>
                    <td className="cell-meta">
                      <span className="tag">{DOCUMENT_TYPE_LABELS[document.doc_type] ?? document.doc_type.toUpperCase()}</span>
                    </td>
                    <td className="cell-meta mono">{formatCpf(document.cpf) || "—"}</td>
                    <td className="cell-meta col-optional"><Confidence value={document.confidence} /></td>
                    <td className="cell-meta"><StatusLabel status={document.status} /></td>
                    <td className="cell-meta col-optional">{formatDateTime(document.processed_at)}</td>
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
    </div>
  );
}
