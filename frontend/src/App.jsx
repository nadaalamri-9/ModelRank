import { useState } from "react";

import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import ProjectBox from "./components/ProjectBox";
import ResultsSection from "./components/ResultsSection";
import HowItWorks from "./components/HowItWorks";
import Footer from "./components/Footer";

import "./App.css";

function App() {
  const [projectDescription, setProjectDescription] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const handleEvaluate = async () => {
    if (!projectDescription.trim()) {
      return;
    }

    setStatus("analyzing");
    setError("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/evaluate",
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

      const data = await response.json();

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
    if (!projectDescription.trim()) {
      return;
    }

    setDownloadingPdf(true);
    setError("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/report/pdf",
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