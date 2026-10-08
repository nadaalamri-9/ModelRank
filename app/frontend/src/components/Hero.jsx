import "./Hero.css";

function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero-visual" aria-hidden="true" />

      <div className="hero-content">
        <span className="hero-eyebrow">
          MODEL EVALUATION SYSTEM
        </span>

        <h1>
          Find the model
          <span>worth building on.</span>
        </h1>

        <p>
          Describe your project once. ModelRank benchmarks multiple
          language models and ranks the strongest fit for your use case.
        </p>
      </div>
    </section>
  );
}

export default Hero;
