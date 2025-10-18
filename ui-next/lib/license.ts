import { buildApiUrl } from "@/lib/config";

export type LicenseStatus = {
  active: boolean;
  plan: string;
  expires_at: string | null;
  in_grace: boolean;
  features: string[];
  reason: string | null;
};

export async function fetchLicenseStatus(): Promise<LicenseStatus> {
  const response = await fetch(buildApiUrl("/license/status"), { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo obtener el estado de la licencia");
  }
  return response.json();
}
