import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n";
import { DeleteDialog } from "./DeleteDialog";
import { checkFile, fileFormat } from "./PhotoInput";

function wrap(children: ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <LocaleProvider defaultLanguage="pt-BR" defaultTimeZone="America/Sao_Paulo">
        {children}
      </LocaleProvider>
    </QueryClientProvider>
  );
}

afterEach(cleanup);

describe("PhotoInput", () => {
  it("identifica o formato pelo tipo ou pela extensão", () => {
    expect(fileFormat(new File(["x"], "a.jpg", { type: "image/jpeg" }))).toBe("jpeg");
    expect(fileFormat(new File(["x"], "foto.HEIC", { type: "" }))).toBe("heic");
    expect(fileFormat(new File(["x"], "doc.pdf", { type: "application/pdf" }))).toBeNull();
  });

  it("recusa formato não aceito e arquivo grande", () => {
    const big = new File([new Uint8Array(2 * 1024 * 1024)], "a.png", { type: "image/png" });
    expect(checkFile(big, ["jpeg"], 15)).toBe("format");
    expect(checkFile(big, ["png"], 1)).toBe("size");
    expect(checkFile(big, ["png"], 5)).toBeNull();
  });
});

describe("DeleteDialog", () => {
  it("só libera a exclusão depois de digitar o nome sem se importar com acento", async () => {
    const onConfirm = vi.fn(async () => undefined);
    render(
      wrap(
        <DeleteDialog
          open
          title="Apagar pessoa"
          description="descrição"
          documents={2}
          images={5}
          confirmationValues={["JOÃO DA SILVA", "52998224725"]}
          confirmationLabel="Digite o nome"
          onConfirm={onConfirm}
          onClose={() => undefined}
        />,
      ),
    );
    const button = screen.getByRole("button", { name: "Apagar definitivamente" });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Digite o nome"), { target: { value: "joao da silva" } });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(screen.getByText("imagens e recortes")).toBeInTheDocument();
  });

  it("aceita o CPF com pontuação", () => {
    render(
      wrap(
        <DeleteDialog open title="t" description="d" documents={1} images={1} confirmationValues={["52998224725"]} confirmationLabel="CPF" onConfirm={async () => undefined} onClose={() => undefined} />,
      ),
    );
    fireEvent.change(screen.getByLabelText("CPF"), { target: { value: "529.982.247-25" } });
    expect(screen.getByRole("button", { name: "Apagar definitivamente" })).toBeEnabled();
  });

  it("não renderiza fechado", () => {
    render(wrap(<DeleteDialog open={false} title="t" description="d" documents={1} images={1} onConfirm={async () => undefined} onClose={() => undefined} />));
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
});
