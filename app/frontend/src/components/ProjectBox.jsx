import AnalysisProgress from "./AnalysisProgress";
import "./ProjectBox.css";

function ProjectBox({
  projectDescription,
  setProjectDescription,
  onEvaluate,
  error,
  analyzing,
}) {
  return (
    <section className="project-box-wrapper" id="evaluate">
      <div className="project-section-inner">
        <div className="project-intro">
          <span className="project-eyebrow">
            START EVALUATION
          </span>

          <h2>Describe your project</h2>

          <p>
            Tell ModelRank what you're building and what matters most.
          </p>
        </div>

        {/* One card for both states. The input and the progress view sit
            in the same grid cell, so the card is always sized to the
            taller of the two and never moves or resizes when the state
            changes; only which one is visible switches. */}
        <div
          className={`project-box${analyzing ? " is-analyzing" : ""}`}
        >
          <div className="project-box-stack">
            <div
              className="project-box-input"
              inert={analyzing}
            >
              <label htmlFor="project-description">
                Describe your AI project
              </label>

              <div className="project-textarea-wrapper">
                <textarea
                  id="project-description"
                  value={projectDescription}
                  maxLength={2000}
                  onChange={(event) =>
                    setProjectDescription(event.target.value)
                  }
                  placeholder="Example: An AI support assistant focused on accuracy, speed, and low cost."
                />

                <span className="character-count">
                  {projectDescription.length}/2000
                </span>
              </div>

              <button
                className="evaluate-button"
                type="button"
                onClick={onEvaluate}
                disabled={!projectDescription.trim()}
              >
                Evaluate Models
              </button>

              {error && (
                <p className="project-error">
                  {error}
                </p>
              )}
            </div>

            <div
              className="project-box-progress"
              aria-hidden={!analyzing}
            >
              {/* Remounts on each new run so the stages restart at Plan */}
              <AnalysisProgress
                key={analyzing ? "running" : "waiting"}
                running={analyzing}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default ProjectBox;
