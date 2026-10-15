import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { DataTable, type Column } from "@/components/DataTable";

interface Row { id: number; name: string; n: number }
const rows: Row[] = [{ id: 1, name: "Alpha", n: 3 }, { id: 2, name: "Beta", n: 5 }];
const columns: Column<Row>[] = [
  { id: "name", header: "Nombre", sortKey: "name", cell: (r) => r.name },
  { id: "n", header: "Cantidad", cell: (r) => r.n, hidden: true },
];

function Harness({ onSort }: { onSort: (s: string | null) => void }) {
  const [sort, setSort] = useState<string | null>(null);
  const [sel, setSel] = useState<Set<number | string>>(new Set());
  return (
    <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} sort={sort}
      onSort={(s) => { setSort(s); onSort(s); }} selectable selected={sel} onSelectedChange={setSel}
      bulkActions={<button>Acción masiva</button>} />
  );
}

describe("DataTable", () => {
  beforeEach(() => localStorage.clear());

  it("muestra filas y respeta columnas ocultas por defecto", () => {
    render(<Harness onSort={() => {}} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Cantidad" })).not.toBeInTheDocument();
  });

  it("cicla la ordenación asc → desc → ninguna", async () => {
    const calls: (string | null)[] = [];
    render(<Harness onSort={(s) => calls.push(s)} />);
    const btn = screen.getByRole("button", { name: "Nombre" });
    await userEvent.click(btn);
    await userEvent.click(btn);
    await userEvent.click(btn);
    expect(calls).toEqual(["name", "-name", null]);
  });

  it("selección múltiple muestra acciones masivas", async () => {
    render(<Harness onSort={() => {}} />);
    expect(screen.queryByText("Acción masiva")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Seleccionar todos" }));
    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.getByText("Acción masiva")).toBeInTheDocument();
  });

  it("permite mostrar columnas ocultas", async () => {
    render(<Harness onSort={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Columnas" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Cantidad" }));
    expect(screen.getByRole("columnheader", { name: "Cantidad" })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("cols:undefined") ?? "null")).toBeNull(); // sin storageKey no persiste
  });

  it("muestra estado vacío", () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(r) => r.id} />);
    expect(screen.getByText("Sin resultados")).toBeInTheDocument();
  });
});
