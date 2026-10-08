import {
  MessageSquareText,
  Layers3,
  Play,
  ChartNoAxesColumnIncreasing,
} from "lucide-react";

import "./HowItWorks.css";

function HowItWorks() {
  const steps = [
    {
      number: "01",
      title: "Plan",
      description:
        "Understand your project and identify the evaluation criteria that matter.",
      icon: MessageSquareText,
    },
    {
      number: "02",
      title: "Benchmark",
      description:
        "Generate a focused benchmark with realistic test cases for your use case.",
      icon: Layers3,
    },
    {
      number: "03",
      title: "Run",
      description:
        "Test multiple candidate models on the same benchmark in parallel.",
      icon: Play,
    },
    {
      number: "04",
      title: "Rank",
      description:
        "Compare quality, speed, and cost to select the best model for your project.",
      icon: ChartNoAxesColumnIncreasing,
    },
  ];

  return (
    <section
      className="how-it-works"
      id="how-it-works"
    >
      <div className="how-it-works-heading">
        <span className="how-it-works-eyebrow">
          HOW IT WORKS
        </span>

        <h2>
          How ModelRank works
        </h2>

        <p>
          One project description becomes a focused benchmark,
          run across multiple models under the same conditions.
        </p>
      </div>

      <div className="how-it-works-grid">
        {steps.map((step) => {
          const Icon = step.icon;

          return (
            <article
              className="how-it-works-step"
              key={step.number}
            >
              <div className="how-step-marker">
                <span className="how-step-number">
                  {step.number}
                </span>

                <div className="how-step-icon">
                  <Icon
                    size={19}
                    strokeWidth={1.6}
                  />
                </div>
              </div>

              <div className="how-step-content">
                <h3>
                  {step.title}
                </h3>

                <p>
                  {step.description}
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default HowItWorks;