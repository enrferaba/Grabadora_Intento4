const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:4814";

export type LicenseStatus = {
  active: boolean;
  plan: string;
  expires_at: string | null;
  in_grace: boolean;
  features: string[];
  reason: string | null;
};

export async function fetchLicenseStatus(): Promise<LicenseStatus> {
  const response = await fetch(`${BASE}/license/status`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("No se pudo obtener el estado de la licencia");
  }
  return response.json();
}
