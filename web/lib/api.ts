/**
 * Typed API client for client components.
 *
 * All calls go through the Next.js backend proxy at /api/backend/...
 * which mints a short-lived HS256 JWT per request (server-side only).
 *
 * Import and use only inside "use client" components.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend/${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = (await res.json()) as {
        detail?: string | { message?: string; context?: unknown };
      };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (
        body.detail &&
        typeof body.detail === "object" &&
        typeof body.detail.message === "string"
      ) {
        message = body.detail.message;
      }
    } catch {
      // leave message as statusText
    }
    throw new ApiError(res.status, message);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Domain types (mirrors backend Pydantic response models)
// ---------------------------------------------------------------------------

export type JobStatus =
  | "validating"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "expired";

export interface Job {
  job_id: string;
  user_id: string;
  status: JobStatus;
  mode: string;
  target_language: string;
  source_language_override: string | null;
  translation_style: string | null;
  user_level: string | null;
  explanation_depth: string | null;
  source_artifact_id: string | null;
  word_count_estimate: number | null;
  credit_estimate: number | null;
  failure_reason: string | null;
  failure_class: string | null;
  cancel_requested: boolean;
  created_at: string;
  updated_at: string;
  retention_deadline: string | null;
  retry_eligible: boolean;
  book_title: string | null;
  book_author: string | null;
  source_filename: string | null;
  progress_percent?: number;
  pipeline_stage?: string | null;
  eta_seconds_remaining?: number | null;
  processing_started_at?: string | null;
}

export interface ArtifactRegistration {
  artifact_id: string;
  object_key: string;
  upload_url: string;
  expires_in_seconds: number;
}

export interface PrecheckResult {
  artifact_id: string;
  status: string;
  detected_language: string | null;
  language_confidence: number | null;
  has_images: boolean | null;
  error_code: string | null;
  completed_at: string | null;
  precheck_id: string;
  word_count: number | null;
  chapter_count: number | null;
}

export interface CreditEstimate {
  estimated_credits: number;
  language_pair_tier: string;
  source_language_confidence_label: string | null;
  is_valid: boolean;
  validation_errors: string[];
}

export interface SubmitJobRequest {
  mode: string;
  target_language: string;
  source_language_override?: string;
  translation_style: string;
  user_level: string;
  explanation_depth: string;
  source_artifact_id: string;
  word_count_estimate?: number;
  credit_estimate: number;
  client_submission_id?: string;
  quality_tier?: string;
  ui_locale?: string;
}

export interface DownloadUrlResponse {
  job_id: string;
  artifact_id: string;
  download_url: string;
  expires_in_seconds: number;
}

export interface CreditsBalance {
  balance: number;
}

export interface UserProfile {
  user_id: string;
  email: string;
  is_admin: boolean;
  balance: number;
}

export interface AdminUserRow {
  user_id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  balance: number;
  created_at: string;
}

export interface AdminJobRow {
  job_id: string;
  user_id: string;
  user_email: string;
  status: string;
  mode: string;
  target_language: string;
  source_language_override: string | null;
  translation_style: string | null;
  user_level: string | null;
  explanation_depth: string | null;
  quality_tier: string | null;
  word_count_estimate: number | null;
  credit_estimate: number | null;
  created_at: string;
  updated_at: string;
  progress_percent: number;
  pipeline_stage: string | null;
  failure_class: string | null;
}

export interface AdminJobRunInfo {
  job_run_id: string;
  run_status: string;
  worker_id: string | null;
  heartbeat_at: string | null;
  lease_expires_at: string | null;
  completed_batches: number;
  total_batches: number;
}

export interface AdminJobDetail extends AdminJobRow {
  failure_reason: string | null;
  failure_class: string | null;
  updated_at: string;
  processing_started_at: string | null;
  progress_percent: number;
  pipeline_stage: string | null;
  total_cost_usd: number;
  total_tokens_in: number;
  total_tokens_out: number;
  run_info: AdminJobRunInfo | null;
}

export interface CreditAdjustResponse {
  user_id: string;
  balance_after: number;
  transaction_id: string;
}

export interface AppSettings {
  initial_credit_grant: number;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const api = {
  /**
   * Register an artifact record and receive a presigned S3 upload URL.
   * jobId is a client-generated UUID used for idempotency.
   */
  registerArtifact(
    jobId: string,
    artifactType: string,
  ): Promise<ArtifactRegistration> {
    return apiFetch<ArtifactRegistration>("storage/artifacts", {
      method: "POST",
      body: JSON.stringify({ artifact_type: artifactType, job_id: jobId }),
    });
  },

  /**
   * Confirm that the client finished uploading a file to S3.
   */
  confirmUpload(
    artifactId: string,
  ): Promise<unknown> {
    return apiFetch(`upload/confirm/${artifactId}`, {
      method: "POST",
    });
  },

  /**
   * Trigger language detection and EPUB validation for an artifact.
   */
  runPrecheck(artifactId: string): Promise<PrecheckResult> {
    return apiFetch<PrecheckResult>(`precheck/${artifactId}`, {
      method: "POST",
    });
  },

  /**
   * Estimate credit cost for a given configuration.
   */
  estimateCredits(params: {
    mode: string;
    targetLanguage: string;
    wordCount: number;
    sourceLanguage?: string;
    translationStyle?: string;
    userLevel?: string;
    explanationDepth?: string;
    sourceLanguageConfidence?: number;
    qualityTier?: string;
  }): Promise<CreditEstimate> {
    return apiFetch<CreditEstimate>("config/estimate", {
      method: "POST",
      body: JSON.stringify({
        mode: params.mode,
        target_language: params.targetLanguage,
        word_count: params.wordCount,
        source_language: params.sourceLanguage,
        translation_style: params.translationStyle ?? "natural",
        user_level: params.userLevel ?? "B1",
        explanation_depth: params.explanationDepth ?? "standard",
        source_language_confidence: params.sourceLanguageConfidence,
        quality_tier: params.qualityTier,
      }),
    });
  },

  /**
   * Submit a translation job.
   */
  submitJob(req: SubmitJobRequest): Promise<Job> {
    return apiFetch<Job>("jobs", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /**
   * List all jobs for the current user.
   */
  listJobs(): Promise<Job[]> {
    return apiFetch<Job[]>("jobs");
  },

  /**
   * Get a single job by ID.
   */
  getJob(jobId: string): Promise<Job> {
    return apiFetch<Job>(`jobs/${jobId}`);
  },

  /**
   * Create a new job from a failed job using the same source file (POST /jobs/{id}/retry).
   */
  retryJob(jobId: string): Promise<Job> {
    return apiFetch<Job>(`jobs/${jobId}/retry`, {
      method: "POST",
    });
  },

  /**
   * Issue a presigned download URL for a completed job's output.
   */
  getDownloadUrl(jobId: string): Promise<DownloadUrlResponse> {
    return apiFetch<DownloadUrlResponse>(`jobs/${jobId}/download-url`);
  },

  /**
   * Get the current user's credit balance.
   */
  getCredits(): Promise<CreditsBalance> {
    return apiFetch<CreditsBalance>("config/credits");
  },

  getProfile(): Promise<UserProfile> {
    return apiFetch<UserProfile>("config/profile");
  },

  listAdminUsers(): Promise<AdminUserRow[]> {
    return apiFetch<AdminUserRow[]>("admin/users");
  },

  listAdminJobs(): Promise<AdminJobRow[]> {
    return apiFetch<AdminJobRow[]>("admin/jobs");
  },

  getAdminJobDetail(jobId: string): Promise<AdminJobDetail> {
    return apiFetch<AdminJobDetail>(`admin/jobs/${jobId}`);
  },

  adjustAdminCredits(
    userId: string,
    delta: number,
  ): Promise<CreditAdjustResponse> {
    return apiFetch<CreditAdjustResponse>(`admin/users/${userId}/credits`, {
      method: "POST",
      body: JSON.stringify({ delta }),
    });
  },

  getAdminSettings(): Promise<AppSettings> {
    return apiFetch<AppSettings>("admin/settings");
  },

  updateAdminSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
    return apiFetch<AppSettings>("admin/settings", {
      method: "PATCH",
      body: JSON.stringify(settings),
    });
  },
};
