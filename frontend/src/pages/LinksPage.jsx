import {
  ArrowRight,
  CirclePlay,
  Compass,
} from "lucide-react";

import logo from "../assets/logo.svg";
import "./LinksPage.css";

/* Placeholders start with "#TODO": replace them with the real URLs */
const LINKS = {
  app: "https://main.d315adazaocnwp.amplifyapp.com",
  demoVideo: "#TODO-demo-video-url",
  repository: "https://github.com/nadaalamri-9/ModelRank",
  linkedin: "https://www.linkedin.com/in/nada-alamri9",
  github: "https://github.com/nadaalamri-9",
};

/* lucide-react ships no brand marks, so these two are inline */
function GitHubIcon({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function LinkedInIcon({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.73 1.637-1.468 3.37-1.468 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 1 1 0-4.125 2.062 2.062 0 0 1 0 4.125zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

const MAIN_LINKS = [
  {
    title: "Explore ModelRank",
    description: "Find the best-fit AI model for your project.",
    href: LINKS.app,
    icon: <Compass size={20} strokeWidth={1.8} />,
    primary: true,
  },
  {
    title: "Demo Video",
    description: "Watch ModelRank in action.",
    href: LINKS.demoVideo,
    icon: <CirclePlay size={20} strokeWidth={1.8} />,
    external: true,
  },
  {
    title: "GitHub",
    description: "Explore the source code.",
    href: LINKS.repository,
    icon: <GitHubIcon size={18} />,
    external: true,
  },
];

function LinksPage() {
  return (
    <main className="links-page">
      <div className="links-inner">
        <header className="links-header">
          <img
            src={logo}
            alt="ModelRank logo"
            className="links-logo"
          />

          <h1>ModelRank</h1>

          <p>Find the model worth building on.</p>
        </header>

        <nav
          className="links-list"
          aria-label="ModelRank links"
        >
          {MAIN_LINKS.map((link) => (
            <a
              key={link.title}
              href={link.href}
              className={
                link.primary
                  ? "links-button links-button-primary"
                  : "links-button"
              }
              {...(link.external && {
                target: "_blank",
                rel: "noopener noreferrer",
              })}
            >
              <span className="links-button-icon">
                {link.icon}
              </span>

              <span className="links-button-text">
                <span className="links-button-title">
                  {link.title}
                </span>

                <span className="links-button-description">
                  {link.description}
                </span>
              </span>

              <ArrowRight
                className="links-button-arrow"
                size={18}
                strokeWidth={1.8}
                aria-hidden="true"
              />
            </a>
          ))}
        </nav>

        <footer className="links-footer">
          <p className="links-footer-label">Built by</p>
          <p className="links-footer-name">Nada Alamri</p>

          <div className="links-social">
            <a
              href={LINKS.linkedin}
              className="links-social-link"
              aria-label="Nada Alamri on LinkedIn"
              target="_blank"
              rel="noopener noreferrer"
            >
              <LinkedInIcon size={16} />
            </a>

            <a
              href={LINKS.github}
              className="links-social-link"
              aria-label="Nada Alamri on GitHub"
              target="_blank"
              rel="noopener noreferrer"
            >
              <GitHubIcon size={16} />
            </a>
          </div>
        </footer>
      </div>
    </main>
  );
}

export default LinksPage;
