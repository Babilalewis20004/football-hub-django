document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('post-slider');
    const slides = document.querySelectorAll('.post-slide');
    if (!slides.length) return;

    const prevBtn = slider.querySelector('.slider-control-prev');
    const nextBtn = slider.querySelector('.slider-control-next');
    const indicators = slider.querySelectorAll('.slider-indicator');

    let index = 0;
    let timer = null;

    function showSlide(newIndex) {
        slides[index].classList.remove('active');
        if (indicators[index]) {
            indicators[index].classList.remove('active');
            indicators[index].setAttribute('aria-current', 'false');
        }

        index = (newIndex + slides.length) % slides.length;

        slides[index].classList.add('active');
        if (indicators[index]) {
            indicators[index].classList.add('active');
            indicators[index].setAttribute('aria-current', 'true');
        }
    }

    function rotatePosts() {
        showSlide(index + 1);
    }

    function start() {
        if (timer) return;
        timer = setInterval(rotatePosts, 5000);
    }

    function stop() {
        clearInterval(timer);
        timer = null;
    }

    // Manual navigation resets the auto-rotate clock rather than jumping
    // again a moment later.
    function goTo(newIndex) {
        showSlide(newIndex);
        stop();
        start();
    }

    // Activate the first slide
    slides[0].classList.add('active');

    if (prevBtn) prevBtn.addEventListener('click', () => goTo(index - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => goTo(index + 1));

    indicators.forEach((dot, i) => {
        dot.addEventListener('click', () => goTo(i));
    });

    start();

    // Let users pause the rotation instead of it running forever unattended
    slider.addEventListener('mouseenter', stop);
    slider.addEventListener('mouseleave', start);
    slider.addEventListener('focusin', stop);
    slider.addEventListener('focusout', start);
});
