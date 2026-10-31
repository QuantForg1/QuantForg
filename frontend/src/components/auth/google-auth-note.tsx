/** Google OAuth is not implemented in the existing auth API. */
export function GoogleAuthNote() {
  return (
    <div className="mt-5">
      <div className="relative my-4 text-center text-xs text-[var(--fg-subtle)]">
        <span className="relative z-10 bg-[var(--surface)] px-3">or continue with</span>
        <span className="absolute inset-x-0 top-1/2 border-t border-[var(--border)]" aria-hidden />
      </div>
      <button
        type="button"
        disabled
        aria-describedby="google-auth-status"
        className="flex h-11 w-full cursor-not-allowed items-center justify-center gap-2 rounded-[var(--radius-sm)] border border-[var(--border)] bg-transparent text-sm font-medium text-[var(--fg-muted)] opacity-80"
      >
        <span aria-hidden className="text-base font-semibold text-[#8ab4f8]">
          G
        </span>
        Continue with Google
      </button>
      <p id="google-auth-status" className="mt-2 text-center text-xs leading-relaxed text-[var(--fg-muted)]">
        Google sign-in is not configured for this deployment. Use email and password.
      </p>
    </div>
  );
}
