import { useEffect, useState } from "react";
import { Check, LoaderCircle } from "lucide-react";
import "./AnalysisProgress.css";

// The /evaluate request is synchronous, so there are no real progress
// events yet. Stages advance on a timer while the request is pending.
// The durations are rough, illustrative pacing (Run usually does the
// most work), not measured backend timings. The last stage has no
// duration: it stays active until the response arrives and this
// component is replaced by the results.

const STAGES = [
  {
    label: "Plan",
    title: "Planning your evaluation",
    description:
      "Reading your project and choosing the criteria that matter most.",
    duration: 15000,
  },
  {
    label: "Benchmark",
    title: "Building the benchmark",
    description:
      "Writing realistic test cases tailored to your use case.",
    duration: 15000,
  },
  {
    label: "Run",
    title: "Running candidate models",
    description:
      "Sending the same benchmark to each candidate model.",
    duration: 120000,
  },
  {
    label: "Rank",
    title: "Ranking the results",
    description:
      "Scoring quality, speed, and cost to find the strongest fit.",
    duration: null,
  },
];

const SEGMENT = 100 / STAGES.length;

// How long the bar takes to settle on a newly active stage, and how far
// it then creeps toward the next one (as a share of a segment) so the
// bar never looks frozen. It never reaches the next stage on its own.
const SETTLE_MS = 700;
const CREEP_SHARE = 0.6;
const FINAL_CREEP_MS = 45000;

function stageCenter(index) {
  return (index + 0.5) * SEGMENT;
}

// Inner content of the ProjectBox card while analyzing. The card itself
// belongs to ProjectBox; this only fills it. The timer runs only while
// `running`, so the hidden copy laid out in the idle state stays still.
function AnalysisProgress({ running }) {
  const [active, setActive] = useState(0);
  const [fill, setFill] = useState({ to: 0, ms: 0 });

  useEffect(() => {
    if (!running) {
      return undefined;
    }

    const { duration } = STAGES[active];
    const isLast = active === STAGES.length - 1;

    const center = stageCenter(active);
    const creepTo =
      center + SEGMENT * CREEP_SHARE * (isLast ? 0.5 : 1);
    const creepMs = (duration ?? FINAL_CREEP_MS) - SETTLE_MS;

    setFill({ to: center, ms: SETTLE_MS });

    const creep = setTimeout(
      () => setFill({ to: creepTo, ms: creepMs }),
      SETTLE_MS
    );

    const next = duration
      ? setTimeout(() => setActive((index) => index + 1), duration)
      : null;

    return () => {
      clearTimeout(creep);
      clearTimeout(next);
    };
  }, [active, running]);

  const motion = {
    transitionDuration: `${fill.ms}ms`,
    transitionTimingFunction:
      fill.ms === SETTLE_MS
        ? "ease-out"
        : "cubic-bezier(0.2, 0.6, 0.35, 1)",
  };

  return (
    <div className="analysis-progress">
      <div className="analysis-progress-header">
        <span className="analysis-progress-label">
          <LoaderCircle
            className="analysis-spinner"
            size={14}
            strokeWidth={2}
            aria-hidden="true"
          />
          ANALYZING
        </span>

        {/* Every stage's copy sits in the same grid cell, so the
            content is always as tall as the longest one and never
            resizes between stages. Only the active one is visible. */}
        <div
          className="analysis-progress-copy-stack"
          role="status"
          aria-live="polite"
        >
          {STAGES.map((item, index) => (
            <div
              key={item.label}
              className={`analysis-progress-copy${
                index === active ? " is-active" : ""
              }`}
            >
              <h2>{item.title}</h2>
              <p>{item.description}</p>
            </div>
          ))}
        </div>
      </div>

      <div
        className="analysis-progress-track"
        aria-hidden="true"
      >
        <div
          className="analysis-progress-fill"
          style={{ ...motion, width: `${fill.to}%` }}
        />

        <div
          className="analysis-progress-marker"
          style={{ ...motion, left: `${fill.to}%` }}
        />
      </div>

      <ol className="analysis-progress-stages">
        {STAGES.map((item, index) => {
          const state =
            index < active
              ? "completed"
              : index === active
                ? "active"
                : "upcoming";

          return (
            <li
              key={item.label}
              className={`analysis-stage analysis-stage-${state}`}
              aria-current={state === "active" ? "step" : undefined}
            >
              <span className="analysis-stage-icon">
                {state === "completed" && (
                  <Check size={10} strokeWidth={2.6} />
                )}
              </span>

              {item.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default AnalysisProgress;
