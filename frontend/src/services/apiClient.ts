/**
 * Typed API client. Every backend route has exactly one function here.
 * Components never call fetch directly: they use the hooks in src/hooks, which use this.
 */
import type {
  ApiErrorBody, CompareRequest, CompareResponse, Constraints, CropCatalog, DataSource, FarmSummary, FieldOverview,
  GibsLayerMeta, PowerPoint, Priorities, RotationOptions, RotationSpec, Scenario, ScenarioKey, ScenarioLimit,
  ScenarioPreset, StressTestResponse, SuitabilityRow, SweepResponse, VulnerabilityResponse,
} from "@/types/api";

/** In dev, Vite proxies /api to the backend. Set VITE_API_BASE_URL to point somewhere else. */
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public hint: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError(0, "backend_unreachable", "The Kebunda backend is not answering.",
      "Start it with: cd backend && uvicorn app.main:app --reload --port 8000");
  }
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, body.error ?? "http_error", body.detail ?? `Request failed (${res.status}).`, body.hint ?? null);
  }
  return (await res.json()) as T;
}

const get = <T,>(path: string, signal?: AbortSignal) => request<T>(path, { signal });
const post = <T,>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });

const qs = (params: Record<string, string | number | boolean>) =>
  "?" + Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");

export const api = {
  // farms
  listFarms: (signal?: AbortSignal) => get<FarmSummary[]>("/farms", signal),
  getField: (id: string, signal?: AbortSignal) => get<FieldOverview>(`/farms/${encodeURIComponent(id)}`, signal),
  getVulnerability: (id: string, signal?: AbortSignal) => get<VulnerabilityResponse>(`/farms/${encodeURIComponent(id)}/vulnerability`, signal),
  createCustomField: (body: { lat: number; lon: number; name?: string; area_ha?: number; irrigated?: boolean; allocation_mm?: number }) =>
    post<FieldOverview>("/farms/custom", body),

  // nasa
  powerPoint: (lat: number, lon: number, signal?: AbortSignal) => get<PowerPoint>(`/nasa/power${qs({ lat, lon })}`, signal),
  gibsLayers: (signal?: AbortSignal) => get<{ layers: GibsLayerMeta[]; legend_note: string }>("/nasa/gibs/layers", signal),
  sources: (signal?: AbortSignal) => get<{ sources: DataSource[]; status_counts: Record<string, number> }>("/nasa/sources", signal),

  // soil & crops
  catalog: (signal?: AbortSignal) => get<CropCatalog>("/soil-crops/catalog", signal),
  suitability: (id: string, signal?: AbortSignal) =>
    get<{ field_id: string; rows: SuitabilityRow[]; method: string }>(`/soil-crops/suitability/${encodeURIComponent(id)}`, signal),

  // rotations
  rotationOptions: (signal?: AbortSignal) => get<RotationOptions>("/rotations/options", signal),
  compare: (body: CompareRequest, signal?: AbortSignal) => post<CompareResponse>("/rotations/compare", body, signal),

  // scenarios
  scenarioPresets: (signal?: AbortSignal) =>
    get<{ limits: Record<ScenarioKey, ScenarioLimit>; presets: ScenarioPreset[]; note: string }>("/scenarios/presets", signal),
  stressTest: (
    body: { field_id: string; strategies: RotationSpec[]; scenario: Scenario; priorities?: Partial<Priorities>; constraints?: Constraints },
    signal?: AbortSignal,
  ) => post<StressTestResponse>("/scenarios/stress-test", body, signal),
  sweep: (
    body: { field_id: string; strategies: RotationSpec[]; parameter: ScenarioKey; steps?: number; priorities?: Partial<Priorities>; constraints?: Constraints },
    signal?: AbortSignal,
  ) => post<SweepResponse>("/scenarios/sweep", body, signal),
};

export type Api = typeof api;
