document.addEventListener('click', function (event) {
    const link = event.target.closest('.back-button');
    if (!link) return;

    if (
        document.referrer &&
        document.referrer.indexOf(window.location.origin) === 0 &&
        window.history.length > 1
    ) {
        event.preventDefault();
        window.history.back();
    }
});
