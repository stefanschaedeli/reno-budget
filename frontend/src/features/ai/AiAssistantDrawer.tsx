/**
 * The AI Project Assistant wizard — a guided, step-by-step drawer over a
 * re-runnable backend pipeline. Each step produces a draft the user reviews and
 * explicitly accepts; accepting writes real Project / CostItem data. The wizard
 * is the structured "happy path"; per-question help text is the lightweight
 * escape hatch.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Drawer } from "@/components/Drawer";
import { formatChf } from "@/features/costs/types";
import { apiErrorMessage } from "@/lib/apiError";

import {
  useAcceptArtifact,
  useAiSession,
  useRunStep,
  useSubmitAnswers,
} from "./api";
import { QuestionField, validateAnswer, type AnswerValue } from "./QuestionField";
import {
  AI_STEPS,
  bkpScopeSchema,
  estimateSchema,
  questionSetSchema,
  type AiArtifact,
  type AiSession,
  type AiStep,
} from "./types";
import { ValidationFindings } from "./ValidationFindings";

/** Steps that require the classify step to have set a project_type first. */
const NEEDS_TYPE = new Set<AiStep>(["question", "estimate", "bkp_scope"]);

interface Props {
  objectId: string;
  projectId: string;
  onClose: () => void;
}

/** Safely read a string field from an artifact's untyped JSON output. */
function outputString(output: Record<string, unknown>, key: string): string {
  const v = output[key];
  return typeof v === "string" ? v : "";
}

function latestArtifact(session: AiSession | undefined, step: AiStep): AiArtifact | undefined {
  if (!session) return undefined;
  const forStep = session.artifacts.filter((a) => a.step === step);
  return forStep.length ? forStep[forStep.length - 1] : undefined;
}

export function AiAssistantDrawer({ objectId, projectId, onClose }: Props) {
  const { t } = useTranslation();
  const sessionQuery = useAiSession(objectId, projectId, true);
  const runStep = useRunStep(objectId, projectId);
  const submitAnswers = useSubmitAnswers(objectId, projectId);
  const acceptArtifact = useAcceptArtifact(objectId, projectId);

  const session = sessionQuery.data;
  const error = runStep.error ?? acceptArtifact.error ?? submitAnswers.error;
  // The classify step sets the project type; question/estimate/bkp_scope depend
  // on it. Until it's set, gate those steps in the UI rather than letting the
  // backend reject them with a 409.
  const typeReady = Boolean(session?.project_type);

  return (
    <Drawer title={t("ai.title")} onClose={onClose}>
      <div className="space-y-6">
        <p className="text-sm text-ink-muted">{t("ai.intro")}</p>

        {error && (
          <p className="rounded-sheet bg-negative-soft px-3 py-2 text-sm text-negative">
            {apiErrorMessage(error, t("ai.error"))}
          </p>
        )}

        {AI_STEPS.map((step) => (
          <StepSection
            key={step}
            step={step}
            artifact={latestArtifact(session, step)}
            session={session}
            running={runStep.isPending && runStep.variables === step}
            blocked={NEEDS_TYPE.has(step) && !typeReady}
            onRun={() => runStep.mutate(step)}
            onSubmitAnswers={(answers) => submitAnswers.mutate(answers)}
            onAccept={(id) => acceptArtifact.mutate(id)}
            accepting={acceptArtifact.isPending}
          />
        ))}
      </div>
    </Drawer>
  );
}

interface StepProps {
  step: AiStep;
  artifact: AiArtifact | undefined;
  session: AiSession | undefined;
  running: boolean;
  blocked: boolean;
  accepting: boolean;
  onRun: () => void;
  onSubmitAnswers: (answers: Record<string, unknown>) => void;
  onAccept: (artifactId: string) => void;
}

function StepSection({
  step,
  artifact,
  session,
  running,
  blocked,
  accepting,
  onRun,
  onSubmitAnswers,
  onAccept,
}: StepProps) {
  const { t } = useTranslation();

  return (
    <section className="border-t border-rule pt-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-display text-lg text-ink">{t(`ai.steps.${step}`)}</h3>
        <button
          type="button"
          onClick={onRun}
          disabled={running || blocked}
          title={blocked ? t("ai.needsType") : undefined}
          className="rounded-sheet bg-ink px-3 py-1.5 text-sm text-paper transition hover:bg-ink/85 disabled:opacity-50"
        >
          {running
            ? t("ai.running")
            : artifact
              ? t("ai.rerun")
              : t(`ai.stepAction.${step}`)}
        </button>
      </div>

      {blocked && !artifact && (
        <p className="text-xs text-ink-subtle">{t("ai.needsType")}</p>
      )}

      {artifact && (
        <StepBody
          step={step}
          artifact={artifact}
          session={session}
          accepting={accepting}
          onSubmitAnswers={onSubmitAnswers}
          onAccept={onAccept}
        />
      )}
    </section>
  );
}

function StepBody({
  step,
  artifact,
  session,
  accepting,
  onSubmitAnswers,
  onAccept,
}: Omit<StepProps, "running" | "blocked" | "onRun">) {
  if (step === "classify") return <ClassifyBody artifact={artifact!} />;
  if (step === "question")
    return (
      <QuestionBody
        artifact={artifact!}
        session={session}
        onSubmitAnswers={onSubmitAnswers}
      />
    );
  if (step === "describe")
    return <DescribeBody artifact={artifact!} accepting={accepting} onAccept={onAccept} />;
  if (step === "estimate")
    return <EstimateBody artifact={artifact!} accepting={accepting} onAccept={onAccept} />;
  return <BkpScopeBody artifact={artifact!} accepting={accepting} onAccept={onAccept} />;
}

function ClassifyBody({ artifact }: { artifact: AiArtifact }) {
  const { t } = useTranslation();
  const type = outputString(artifact.output, "project_type");
  return <p className="text-sm text-ink">{t("ai.classify.result", { type })}</p>;
}

function QuestionBody({
  artifact,
  session,
  onSubmitAnswers,
}: {
  artifact: AiArtifact;
  session: AiSession | undefined;
  onSubmitAnswers: (answers: Record<string, unknown>) => void;
}) {
  const { t } = useTranslation();
  const parsed = questionSetSchema.safeParse(artifact.output);
  const questions = parsed.success ? parsed.data.questions : [];

  const [answers, setAnswers] = useState<Record<string, AnswerValue>>(() => {
    const init: Record<string, AnswerValue> = {};
    for (const q of questions) {
      const existing = session?.answers?.[q.key];
      init[q.key] = (existing as AnswerValue) ?? (q.type === "boolean" ? false : null);
    }
    return init;
  });

  const hasErrors = questions.some((q) => validateAnswer(q, answers[q.key] ?? null));

  return (
    <div className="space-y-3">
      <ValidationFindings raw={artifact.validation} />
      {questions.map((q) => (
        <QuestionField
          key={q.key}
          question={q}
          value={answers[q.key] ?? null}
          onChange={(v) => setAnswers((prev) => ({ ...prev, [q.key]: v }))}
        />
      ))}
      <button
        type="button"
        disabled={hasErrors}
        onClick={() => onSubmitAnswers(answers)}
        className="rounded-sheet border border-rule px-3 py-1.5 text-sm text-ink-muted hover:border-ink/30 hover:text-ink disabled:opacity-50"
      >
        {t("ai.question.save")}
      </button>
    </div>
  );
}

function AcceptButton({
  artifact,
  accepting,
  onAccept,
}: {
  artifact: AiArtifact;
  accepting: boolean;
  onAccept: (id: string) => void;
}) {
  const { t } = useTranslation();
  if (artifact.status === "accepted") {
    return <span className="text-sm text-positive">{t("ai.accepted")}</span>;
  }
  const ok = (artifact.validation as { ok?: boolean }).ok !== false;
  return (
    <button
      type="button"
      disabled={!ok || accepting}
      onClick={() => onAccept(artifact.id)}
      className="rounded-sheet bg-ink px-3 py-1.5 text-sm text-paper transition hover:bg-ink/85 disabled:opacity-50"
      title={ok ? undefined : t("ai.acceptBlocked")}
    >
      {t("ai.accept")}
    </button>
  );
}

function DescribeBody({
  artifact,
  accepting,
  onAccept,
}: {
  artifact: AiArtifact;
  accepting: boolean;
  onAccept: (id: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      <p className="mb-1 text-xs font-medium text-ink-muted">
        {t("ai.describe.heading")}
      </p>
      <p className="whitespace-pre-wrap rounded-sheet bg-paper-sunk p-3 text-sm text-ink">
        {outputString(artifact.output, "description")}
      </p>
      <AcceptButton artifact={artifact} accepting={accepting} onAccept={onAccept} />
    </div>
  );
}

function ConfidenceTag({ confidence }: { confidence: string }) {
  const { t } = useTranslation();
  const cls =
    confidence === "low"
      ? "text-warning"
      : confidence === "high"
        ? "text-positive"
        : "text-ink-subtle";
  return <span className={`text-xs ${cls}`}>{t(`ai.confidence.${confidence}`)}</span>;
}

function EstimateBody({
  artifact,
  accepting,
  onAccept,
}: {
  artifact: AiArtifact;
  accepting: boolean;
  onAccept: (id: string) => void;
}) {
  const { t } = useTranslation();
  const parsed = estimateSchema.safeParse(artifact.output);
  if (!parsed.success) return null;
  const est = parsed.data;

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-ink-muted">{t("ai.estimate.heading")}</p>
      <table className="w-full text-sm">
        <tbody>
          {est.line_items.map((li, i) => (
            <tr key={i} className="border-b border-rule">
              <td className="py-1 pr-2 text-ink">
                {li.label}
                <span className="block text-xs text-ink-subtle">
                  {t("ai.estimate.assumptions")}: {li.assumptions}
                </span>
              </td>
              <td className="py-1 text-right align-top">
                <ConfidenceTag confidence={li.confidence} />
              </td>
              <td className="py-1 pl-2 text-right font-mono tabular-nums text-ink">
                {formatChf(li.amount_chf)}
              </td>
            </tr>
          ))}
          <tr>
            <td className="py-1 pr-2 font-medium text-ink" colSpan={2}>
              {t("ai.estimate.total")}
            </td>
            <td className="py-1 pl-2 text-right font-mono font-medium tabular-nums text-ink">
              {formatChf(est.total_chf)}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="text-xs text-ink-subtle">{t("ai.estimate.disclaimer")}</p>
      <ValidationFindings raw={artifact.validation} />
      <AcceptButton artifact={artifact} accepting={accepting} onAccept={onAccept} />
    </div>
  );
}

function BkpScopeBody({
  artifact,
  accepting,
  onAccept,
}: {
  artifact: AiArtifact;
  accepting: boolean;
  onAccept: (id: string) => void;
}) {
  const { t } = useTranslation();
  const parsed = bkpScopeSchema.safeParse(artifact.output);
  if (!parsed.success) return null;
  const scope = parsed.data;

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-ink-muted">{t("ai.bkp.heading")}</p>
      {scope.positions.map((pos, i) => (
        <div key={i} className="rounded-sheet bg-paper-sunk p-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-ink">
              <span className="font-mono text-ink-muted">{pos.bkp_code}</span>{" "}
              {pos.title}
            </p>
            <span className="font-mono tabular-nums text-ink">
              {formatChf(pos.estimated_amount_chf)}
            </span>
          </div>
          <ConfidenceTag confidence={pos.confidence} />
          {pos.in_scope.length > 0 && (
            <div className="mt-2 text-xs text-ink-muted">
              <span className="font-medium">{t("ai.bkp.inScope")}:</span>{" "}
              {pos.in_scope.join(", ")}
            </div>
          )}
          {pos.out_of_scope.length > 0 && (
            <div className="mt-1 text-xs text-ink-muted">
              <span className="font-medium">{t("ai.bkp.outOfScope")}:</span>{" "}
              {pos.out_of_scope.join(", ")}
            </div>
          )}
        </div>
      ))}
      <ValidationFindings raw={artifact.validation} />
      <AcceptButton artifact={artifact} accepting={accepting} onAccept={onAccept} />
    </div>
  );
}
