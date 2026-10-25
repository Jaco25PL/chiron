import { Consulta } from "@/components/Consulta";

export default async function Page(props: PageProps<"/consulta/[caseId]">) {
  const { caseId } = await props.params;
  const { modo, nivel } = await props.searchParams;
  return (
    <Consulta
      caseId={caseId}
      modoInicial={modo === "cara" ? "cara" : "chat"}
      nivel={nivel === "principiante" ? "principiante" : "normal"}
    />
  );
}
