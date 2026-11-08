"use client";
import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { capabilitiesSchema } from "@/lib/contracts";
export function ProviderNotice() {
  const { data } = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api("capabilities", capabilitiesSchema),
  });
  if (
    !data ||
    (data.embedding_provider !== "fake" && data.llm_provider !== "fake")
  )
    return null;
  return (
    <div className="notice" style={{ marginBottom: 22 }}>
      <FlaskConical size={16} />
      <span>
        Controlled test providers are configured. Fake vectors have no semantic
        meaning; fixture answers do not demonstrate real-model quality.
      </span>
    </div>
  );
}
