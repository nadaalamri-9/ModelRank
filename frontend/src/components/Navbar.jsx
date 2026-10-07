import logo from "../assets/logo.svg";
import "./Navbar.css";

function Navbar() {
  const scrollToHowItWorks = () => {
    document
      .getElementById("how-it-works")
      ?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToEvaluate = () => {
    const target =
      document.getElementById("evaluate") ??
      document.getElementById("top");

    target?.scrollIntoView({ behavior: "smooth" });

    document
      .getElementById("project-description")
      ?.focus({ preventScroll: true });
  };

  return (
    <nav className="navbar">
      <a className="navbar-brand" href="#top">
        <img
          src={logo}
          alt="ModelRank logo"
          className="navbar-logo"
        />

        <span className="navbar-name">
          ModelRank
        </span>
      </a>

      <div className="navbar-actions">
        <button
          className="navbar-link"
          type="button"
          onClick={scrollToHowItWorks}
        >
          How it Works
        </button>

        <button
          className="navbar-cta"
          type="button"
          onClick={scrollToEvaluate}
        >
          Start Evaluation
        </button>
      </div>
    </nav>
  );
}

export default Navbar;