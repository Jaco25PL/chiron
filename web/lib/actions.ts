"use server";

import { cookies } from "next/headers";
import { signOut } from "@/auth";
import { COOKIE_ACENTO } from "@/lib/acento";

export async function cerrarSesion() {
  // the accent is per user: whoever signs in next on this browser gets theirs from the backend
  (await cookies()).delete(COOKIE_ACENTO);
  await signOut({ redirectTo: "/login" });
}
