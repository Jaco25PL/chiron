import { auth } from "@/auth";
import { Home } from "@/components/Home";

export default async function Page() {
  const session = await auth(); // proxy.ts already guarantees a signed-in user here
  const u = session?.user;
  return <Home usuario={{ nombre: u?.name ?? "", email: u?.email ?? "", imagen: u?.image ?? null }} />;
}
