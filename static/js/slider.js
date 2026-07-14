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

