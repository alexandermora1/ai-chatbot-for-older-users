import { FormEvent, useEffect, useRef, useState } from "react";
import { Answer, ApiError, ask, fetchSuggestions } from "./api";

type Status = "idle" | "loading" | "done" | "error";

const FALLBACK_REMINDER = "Husk: Gi aldri BankID-koder eller passord til noen, heller ikke til banken eller politiet.";
const MAX_LENGTH = 500;

export default function App() {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [reminder, setReminder] = useState(FALLBACK_REMINDER);
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [formError, setFormError] = useState("");

  const answerHeading = useRef<HTMLHeadingElement>(null);
  const questionField = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchSuggestions()
      .then((data) => {
        setSuggestions(data.suggestions);
        setReminder(data.reminder);
      })
      // The page still works without suggestions.
      .catch(() => setSuggestions([]));
  }, []);

  // Move focus to the answer when it arrives, so keyboard and screen reader users land on it.
  useEffect(() => {
    if (status === "done" || status === "error") answerHeading.current?.focus();
  }, [status, answer]);

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed) {
      setFormError("Skriv et spørsmål først.");
      questionField.current?.focus();
      return;
    }
    setFormError("");
    setAskedQuestion(trimmed);
    setStatus("loading");
    try {
      setAnswer(await ask(trimmed));
      setStatus("done");
      setQuestion("");
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "Noe gikk galt. Prøv igjen om litt.");
      setStatus("error");
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(question);
  }

  const loading = status === "loading";

  return (
    <>
      <a className="skip-link" href="#innhold">
        Hopp til innholdet
      </a>

      <header className="site-header">
        <div className="wrap">
          <h1>Digital hjelp</h1>
          <p className="tagline">Spør om BankID, svindel og Helsenorge. Du får svar i enkle steg.</p>
        </div>
      </header>

      <main id="innhold" className="wrap">
        <p className="notice">
          <strong>Ikke skriv personopplysninger her.</strong> Du trenger aldri å oppgi fødselsnummer, passord eller
          koder for å få hjelp.
        </p>

        {suggestions.length > 0 && (
          <section aria-labelledby="forslag-tittel">
            <h2 id="forslag-tittel">Velg et spørsmål</h2>
            <ul className="suggestions" role="list">
              {suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button type="button" className="suggestion" disabled={loading} onClick={() => void submit(suggestion)}>
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section aria-labelledby="skriv-tittel">
          <h2 id="skriv-tittel">{suggestions.length > 0 ? "Eller skriv ditt eget spørsmål" : "Skriv spørsmålet ditt"}</h2>
          <form onSubmit={onSubmit} noValidate>
            <label htmlFor="sporsmal">Spørsmålet ditt</label>
            <textarea
              id="sporsmal"
              ref={questionField}
              rows={3}
              maxLength={MAX_LENGTH}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              aria-describedby={formError ? "sporsmal-hjelp sporsmal-feil" : "sporsmal-hjelp"}
              aria-invalid={formError ? true : undefined}
            />
            <p id="sporsmal-hjelp" className="hint">
              Skriv slik du ville spurt en person. For eksempel: «Hvordan bytter jeg passord?»
            </p>
            {formError && (
              <p id="sporsmal-feil" className="field-error">
                {formError}
              </p>
            )}
            <button type="submit" className="primary" disabled={loading}>
              {loading ? "Leter etter svar …" : "Spør"}
            </button>
          </form>
        </section>

        {/* Announces progress to screen readers without moving focus. */}
        <p className="visually-hidden" role="status">
          {loading ? "Leter etter svar. Vent litt." : ""}
        </p>

        {loading && (
          <section className="answer" aria-hidden="true">
            <p className="asked">Du spurte: {askedQuestion}</p>
            <p className="loading">Leter etter svar …</p>
          </section>
        )}

        {status === "error" && (
          <section className="answer error" aria-labelledby="svar-tittel">
            <h2 id="svar-tittel" ref={answerHeading} tabIndex={-1}>
              Det gikk ikke denne gangen
            </h2>
            <p>{errorMessage}</p>
            <button type="button" className="primary" onClick={() => void submit(askedQuestion)}>
              Prøv igjen
            </button>
          </section>
        )}

        {status === "done" && answer && (
          <section className="answer" aria-labelledby="svar-tittel">
            <h2 id="svar-tittel" ref={answerHeading} tabIndex={-1}>
              {answer.found ? "Svar" : "Dette kan jeg ikke svare på"}
            </h2>
            <p className="asked">Du spurte: {askedQuestion}</p>
            <p>{answer.intro}</p>

            {answer.steps.length > 0 && (
              <ol className="steps" role="list">
                {answer.steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            )}

            {answer.closing && <p className="closing">{answer.closing}</p>}

            {answer.sources.length > 0 && (
              <div className="sources">
                <h3>Her har jeg svaret fra</h3>
                <ul>
                  {answer.sources.map((source) => (
                    <li key={source.url}>
                      <a href={source.url} target="_blank" rel="noopener noreferrer">
                        {source.title}
                        <span className="new-tab"> (åpnes i ny fane)</span>
                      </a>
                      <span className="domain">{new URL(source.url).hostname.replace(/^www\./, "")}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {answer.found && (
              <p className="disclaimer">Svaret er laget av en datamaskin og kan inneholde feil. Sjekk kilden hvis du er usikker.</p>
            )}
          </section>
        )}
      </main>

      <footer className="site-footer">
        <div className="wrap">
          <p className="reminder">{reminder}</p>
          <p>Dette er et øvingsprosjekt. Det du skriver, blir ikke lagret.</p>
        </div>
      </footer>
    </>
  );
}
