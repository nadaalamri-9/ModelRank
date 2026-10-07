import { useState } from "react";

import {
  ChevronDown,
  Download,
  RotateCcw,
  Trophy,
} from "lucide-react";

import "./ResultsSection.css";

// Decision reasons longer than this get a "Show more" toggle; shorter
// ones fit in the card's three visible lines.
const LONG_REASON_CHARS = 240;

function formatCost(cost) {
  if (cost === null || cost === undefined) {
    return "—";
  }

  return `$${Number(cost).toFixed(6)}`;
}

function formatLatency(latency) {
  if (latency === null || latency === undefined) {
    return "—";
  }

  return `${Number(latency).toFixed(1)}s`;
}

// "tc_1" -> "TC-1"
function formatTestId(id) {
  return String(id ?? "").replace(/^tc[_-]?/i, "TC-");
}

// Counts come from the returned test assessments when there are any,
// so the summary always matches the rows shown; otherwise from the
// Judge's count fields.
function countVerdicts(model) {
  const tests = model.test_case_assessments ?? [];

  if (tests.length > 0) {
    const count = (verdict) =>
      tests.filter(
        (test) => String(test.verdict).toLowerCase() === verdict
      ).length;

    return {
      passed: count("pass"),
      partial: count("partial"),
      failed: count("fail"),
      total: tests.length,
    };
  }

  const passed = model.passed_tests ?? 0;
  const partial = model.partial_tests ?? 0;
  const failed = model.failed_tests ?? 0;

  return { passed, partial, failed, total: passed + partial + failed };
}

function summarize(model) {
  const { passed, partial, failed, total } = countVerdicts(model);
  const parts = [`${passed} of ${total} passed`];

  if (partial) {
    parts.push(`${partial} partial`);
  }

  if (failed) {
    parts.push(`${failed} failed`);
  }

  return parts.join(" · ");
}

// Returns a copy of the set with the key added or removed
function toggled(set, key) {
  const next = new Set(set);

  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }

  return next;
}

function ResultsSection({
  result,
  onNewAnalysis,
  onDownloadPdf,
  downloadingPdf,
  error,
}) {
  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const [openReasons, setOpenReasons] = useState(() => new Set());
  const [reasonOpen, setReasonOpen] = useState(false);

  const rankings = [...(result.model_rankings ?? [])].sort(
    (a, b) => a.rank - b.rank
  );

  const selected = result.selected_model;

  const best =
    rankings.find((model) => model.model_id === selected?.model_id) ??
    rankings[0];

  const bestId = best?.model_id;

  const decisionReason = result.decision_reason ?? "";
  const reasonIsLong = decisionReason.length > LONG_REASON_CHARS;

  const toggleReason = (key) => {
    setOpenReasons((current) => toggled(current, key));
  };

  // Each model opens and closes independently
  const toggleDetails = (modelId) => {
    setExpandedIds((current) => toggled(current, modelId));
  };

  return (
    <section className="results-section">
      <div className="results-header">
        <span className="results-eyebrow">
          ANALYSIS COMPLETE
        </span>

        <h2>
          Your model ranking
        </h2>
      </div>


      {/* 1. Best match */}

      <article className="best-match">
        <div className="best-match-main">
          <div className="best-match-title">
            <span className="best-match-rank">
              <Trophy size={14} strokeWidth={1.8} />
              #1 Best match
            </span>

            <h3>
              {selected?.name ?? best?.name}
            </h3>

            <span className="best-match-provider">
              {selected?.provider ?? best?.provider}
            </span>
          </div>

          <div className="best-match-actions">
            <button
              className="new-analysis-button"
              type="button"
              onClick={onNewAnalysis}
            >
              <RotateCcw size={16} strokeWidth={1.8} />
              New Analysis
            </button>

            <button
              className="download-button"
              type="button"
              onClick={onDownloadPdf}
              disabled={downloadingPdf}
            >
              <Download size={16} strokeWidth={1.8} />

              {downloadingPdf
                ? "Generating PDF..."
                : "Download PDF"}
            </button>
          </div>
        </div>

        {decisionReason && (
          <div className="best-match-reason">
            <p className={reasonOpen ? "" : "is-clamped"}>
              {decisionReason}
            </p>

            {reasonIsLong && (
              <button
                className="text-button"
                type="button"
                onClick={() => setReasonOpen((open) => !open)}
              >
                {reasonOpen ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {best && (
          <dl className="best-match-stats">
            <Stat label="Passed" value={best.passed_tests} tone="pass" />
            <Stat label="Partial" value={best.partial_tests} tone="partial" />
            <Stat label="Failed" value={best.failed_tests} tone="fail" />
            <Stat
              label="Avg latency"
              value={formatLatency(best.average_latency_seconds)}
            />
            <Stat
              label="Total cost"
              value={formatCost(best.total_cost_usd)}
            />
          </dl>
        )}

        {error && (
          <p className="results-error">
            {error}
          </p>
        )}
      </article>


      {/* 2. Comparison table */}

      <div className="results-block">
        <h3 className="results-block-title">
          Model comparison
        </h3>

        <div className="comparison-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Model</th>
                <th scope="col">Provider</th>
                <th scope="col" className="num">Pass</th>
                <th scope="col" className="num">Partial</th>
                <th scope="col" className="num">Fail</th>
                <th scope="col" className="num">Latency</th>
                <th scope="col" className="num">Cost</th>
              </tr>
            </thead>

            <tbody>
              {rankings.map((model) => (
                <tr
                  key={model.model_id}
                  className={
                    model.model_id === bestId ? "is-winner" : undefined
                  }
                >
                  <td className="rank-cell">#{model.rank}</td>
                  <th scope="row" className="model-cell">
                    {model.name}
                  </th>
                  <td className="muted-cell">{model.provider}</td>
                  <td className="num">{model.passed_tests}</td>
                  <td className="num">{model.partial_tests}</td>
                  <td className="num">{model.failed_tests}</td>
                  <td className="num">
                    {formatLatency(model.average_latency_seconds)}
                  </td>
                  <td className="num">
                    {formatCost(model.total_cost_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>


      {/* 3. Detailed results, collapsed by default */}

      <div className="results-block">
        <h3 className="results-block-title">
          Detailed results
        </h3>

        <div className="details-list">
          {rankings.map((model) => {
            const isOpen = expandedIds.has(model.model_id);
            const panelId = `details-${model.rank}`;

            return (
              <article
                key={model.model_id}
                className={`details-item${isOpen ? " is-open" : ""}`}
              >
                <div className="details-summary">
                  <span className="details-rank">#{model.rank}</span>

                  <div className="details-name">
                    <strong>{model.name}</strong>
                    <span>{model.provider}</span>
                  </div>

                  <span className="details-result">
                    {summarize(model)}
                  </span>

                  <button
                    className="details-toggle"
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => toggleDetails(model.model_id)}
                  >
                    {isOpen ? "Hide details" : "View details"}
                    <ChevronDown size={14} strokeWidth={2} />
                  </button>
                </div>

                {isOpen && (
                  <div className="details-panel" id={panelId}>
                    <code className="details-model-id">
                      {model.model_id}
                    </code>

                    <dl className="details-notes">
                      <div>
                        <dt>Quality assessment</dt>
                        <dd>{model.quality_assessment}</dd>
                      </div>

                      <div>
                        <dt>Ranking reason</dt>
                        <dd>{model.reason}</dd>
                      </div>
                    </dl>

                    <ul className="test-list">
                      {model.test_case_assessments?.map((test) => {
                        const reasonKey =
                          `${model.model_id}:${test.test_case_id}`;
                        const reasonOpen = openReasons.has(reasonKey);

                        return (
                          <li
                            className="test-row"
                            key={test.test_case_id}
                          >
                            <span className="test-id">
                              {formatTestId(test.test_case_id)}
                            </span>

                            <span className="test-criterion">
                              {test.criterion}
                            </span>

                            <span
                              className={`verdict verdict-${test.verdict}`}
                            >
                              {test.verdict}
                            </span>

                            <button
                              className={`test-reason${
                                reasonOpen ? " is-open" : ""
                              }`}
                              type="button"
                              aria-expanded={reasonOpen}
                              onClick={() => toggleReason(reasonKey)}
                            >
                              {test.reason}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}


function Stat({ label, value, tone }) {
  return (
    <div className={`stat${tone ? ` stat-${tone}` : ""}`}>
      <dt>{label}</dt>
      <dd>{value ?? "—"}</dd>
    </div>
  );
}


export default ResultsSection;
