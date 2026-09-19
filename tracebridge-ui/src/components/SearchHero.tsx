import { ArrowRight, Search } from "lucide-react";
import { useState } from "react";

const UUID_PATTERN = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const EXAMPLE_ID = "06fc3488-bc83-47a4-a768-db3af8b5c161";

interface Props {
  onInvestigate: (correlationId: string) => void;
  disabled: boolean;
}

export function SearchHero({ onInvestigate, disabled }: Props) {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);

  const trimmed = value.trim();
  const isValid = UUID_PATTERN.test(trimmed);
  const showError = touched && trimmed.length > 0 && !isValid;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (isValid) onInvestigate(trimmed);
  }

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-8">
      <h2 className="text-lg font-semibold text-zinc-100">Investigate a transaction</h2>
      <p className="mt-1 text-sm text-zinc-500">Enter a correlation ID to trace it across every TraceBridge service.</p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-600" />
          <input
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              setTouched(false);
            }}
            onBlur={() => setTouched(true)}
            disabled={disabled}
            placeholder={EXAMPLE_ID}
            spellCheck={false}
            className={`w-full rounded-xl border bg-zinc-950 py-3.5 pl-11 pr-4 font-mono text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-sky-600/60 focus:ring-1 focus:ring-sky-600/40 disabled:opacity-50 ${
              showError ? "border-rose-600/60" : "border-zinc-800"
            }`}
          />
        </div>
        <button
          type="submit"
          disabled={disabled || trimmed.length === 0}
          className="group flex items-center justify-center gap-2 rounded-xl bg-sky-500 px-6 py-3.5 text-sm font-medium text-zinc-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
        >
          Investigate
          <ArrowRight className="h-4 w-4 transition group-disabled:translate-x-0 group-hover:translate-x-0.5" />
        </button>
      </form>

      {showError && <p className="mt-2 text-xs text-rose-400">That doesn't look like a valid correlation ID (UUID).</p>}
      {!showError && (
        <p className="mt-2 text-xs text-zinc-600">
          Example: <span className="font-mono text-zinc-500">{EXAMPLE_ID}</span>
        </p>
      )}
    </section>
  );
}
