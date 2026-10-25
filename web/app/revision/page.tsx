import type { Metadata } from "next";
import { Revision } from "@/components/Revision";

export const metadata: Metadata = { title: "Revisión · Chiron" };

/** Human review of the LLM judge: a medical student labels the patient's eval answers.
 *  Only for the reviewers in CHIRON_REVIEWERS (checked by the backend). */
export default function Page() {
  return <Revision />;
}
