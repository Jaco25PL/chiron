"use server";

import { signOut } from "@/auth";

export async function cerrarSesion() {
  await signOut({ redirectTo: "/login" });
}
