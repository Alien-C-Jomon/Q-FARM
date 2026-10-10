document.addEventListener("DOMContentLoaded", () => {
    const prefersReducedMotion =
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /*
     * Q-FARM landing page interactions
     */

    // --------------------------------------------------
    // 1. Gentle mouse movement for the botanical artwork
    // --------------------------------------------------

    const heroArt = document.querySelector(".hero-art");

    if (heroArt && !prefersReducedMotion) {
        heroArt.addEventListener("mousemove", (event) => {
            const rect = heroArt.getBoundingClientRect();

            const x = (event.clientX - rect.left) / rect.width - 0.5;
            const y = (event.clientY - rect.top) / rect.height - 0.5;

            heroArt.style.setProperty("--mouse-x", `${x * 10}px`);
            heroArt.style.setProperty("--mouse-y", `${y * 10}px`);
        });

        heroArt.addEventListener("mouseleave", () => {
            heroArt.style.setProperty("--mouse-x", "0px");
            heroArt.style.setProperty("--mouse-y", "0px");
        });
    }

    // --------------------------------------------------
    // 2. Reveal sections as the user scrolls
    // --------------------------------------------------

    const revealItems = document.querySelectorAll(
        ".feature-card, .intro-grid, .quantum-copy, .quantum-art, .farm-cta"
    );

    if (!prefersReducedMotion && "IntersectionObserver" in window) {
        const observer = new IntersectionObserver(
            (entries, observerInstance) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;

                    entry.target.classList.add("is-visible");
                    observerInstance.unobserve(entry.target);
                });
            },
            {
                threshold: 0.12
            }
        );

        revealItems.forEach((item) => {
            item.classList.add("reveal-item");
            observer.observe(item);
        });
    }

    // --------------------------------------------------
    // 3. Tiny hover movement for the feature cards
    // --------------------------------------------------

    if (!prefersReducedMotion) {
        document.querySelectorAll(".feature-card").forEach((card) => {
            card.addEventListener("mousemove", (event) => {
                const rect = card.getBoundingClientRect();

                const x =
                    (event.clientX - rect.left) / rect.width - 0.5;

                const y =
                    (event.clientY - rect.top) / rect.height - 0.5;

                card.style.transform =
                    `translateY(-6px) rotateX(${y * -2}deg) rotateY(${x * 2}deg)`;
            });

            card.addEventListener("mouseleave", () => {
                card.style.transform = "";
            });
        });
    }

    // --------------------------------------------------
    // 4. Smooth navigation
    // --------------------------------------------------

    document.querySelectorAll('a[href^="#"]').forEach((link) => {
        link.addEventListener("click", (event) => {
            const targetId = link.getAttribute("href");

            if (!targetId || targetId === "#") return;

            const target = document.querySelector(targetId);

            if (!target) return;

            event.preventDefault();

            target.scrollIntoView({
                behavior: prefersReducedMotion ? "auto" : "smooth",
                block: "start"
            });
        });
    });

    console.log("Q-FARM 🌱 frontend initialized");
});