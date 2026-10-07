import logo from "../assets/logo.svg";
import "./Footer.css";

function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <img
            src={logo}
            alt="ModelRank logo"
            className="footer-logo"
          />

          <div>
            <span className="footer-name">
              ModelRank
            </span>

            <p>
              Compare. Evaluate. Rank.
            </p>
          </div>
        </div>

        <p className="footer-copy">
          © 2026 ModelRank
        </p>
      </div>
    </footer>
  );
}

export default Footer;