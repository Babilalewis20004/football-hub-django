document.addEventListener('DOMContentLoaded', () => {
    const slides = document.querySelectorAll('.post-slide');
    if (!slides.length) return;

    let index = 0;

    function rotatePosts() {
        slides[index].classList.remove('active');
        index = (index + 1) % slides.length;
        slides[index].classList.add('active');
    }

    // Activate the first slide
    slides[0].classList.add('active');

    // Rotate every 5 seconds
    setInterval(rotatePosts, 5000);
});


document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('swap-container');
    const hero = document.getElementById('hero-section');
    const slider = document.getElementById('post-slider');

    let swapped = false;

    function swapPositions() {
        if (!swapped) {
            container.insertBefore(slider, hero);  // slider moves above hero
        } else {
            container.insertBefore(hero, slider);  // hero moves above slider
        }
        swapped = !swapped;
    }

    setInterval(swapPositions, 5000);
});
