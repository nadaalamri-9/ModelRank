import { useState } from "react";

import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import ProjectBox from "./components/ProjectBox";
import ResultsSection from "./components/ResultsSection";
import HowItWorks from "./components/HowItWorks";
import Footer from "./components/Footer";

import "./App.css";

// Set VITE_API_URL for production builds; local development keeps the default
const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// Evaluations run as background jobs on the backend; poll until done
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_FAILURES = 5;

const wait = (ms) =>
  new Promise((resolve) => setTimeout(resolve, ms));

async function waitForEvaluation(jobId) {
  let failures = 0;

  for (;;) {
    await wait(POLL_INTERVAL_MS);

    let response;

    try {
      response = await fetch(
        `${API_URL}/evaluate/jobs/${jobId}`,
        { cache: "no-store" }
      );
    } catch {
      // Brief network hiccups should not end a long evaluation
      failures += 1;

      if (failures >= MAX_POLL_FAILURES) {
        throw new Error("Failed to evaluate the project.");
      }

      continue;
    }

    if (!response.ok) {
      throw new Error("Failed to evaluate the project.");
    }

    failures = 0;

    const job = await response.json();

    if (job.status === "done") {
      return job.result;
    }

    if (job.status === "failed") {
      throw new Error("Failed to evaluate the project.");
    }
  }
}

function App() {
  const [projectDescription, setProjectDescription] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState(null);

  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const handleEvaluate = async () => {
    if (!projectDescription.trim()) {
      return;
    }

    setStatus("analyzing");
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/evaluate/jobs`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_request: projectDescription,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to evaluate the project.");
      }

      const job = await response.json();
      const data = await waitForEvaluation(job.job_id);

      setJobId(job.job_id);
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(
        err.message || "Something went wrong."
      );

      setStatus("idle");
    }
  };

  const handleDownloadPdf = async () => {
    if (!jobId) {
      return;
    }

    setDownloadingPdf(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/report/pdf`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            job_id: jobId,
            user_request: projectDescription,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to generate the PDF report."
        );
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = "ModelRank_Report.pdf";

      document.body.appendChild(link);
      link.click();

      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(
        err.message || "Failed to download the PDF."
      );
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleNewAnalysis = () => {
    setProjectDescription("");
    setJobId(null);
    setResult(null);
    setError("");
    setStatus("idle");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  return (
    <div className="app">
      <Navbar />

      <Hero />

      {/* The same card stays mounted while analyzing; only its
          content switches to the progress view */}
      {(status === "idle" || status === "analyzing") && (
        <ProjectBox
          projectDescription={projectDescription}
          setProjectDescription={setProjectDescription}
          onEvaluate={handleEvaluate}
          error={error}
          analyzing={status === "analyzing"}
        />
      )}

      {status === "done" && result && (
        <ResultsSection
          result={result}
          onNewAnalysis={handleNewAnalysis}
          onDownloadPdf={handleDownloadPdf}
          downloadingPdf={downloadingPdf}
          error={error}
        />
      )}

      <HowItWorks />

      <Footer />
    </div>
  );
}

export default App;