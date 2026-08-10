(function () {
    var STORAGE_KEY = 'cookieConsent';

    document.addEventListener('DOMContentLoaded', function () {
        var banner = document.getElementById('cookie-consent-banner');
        if (!banner) {
            return;
        }

        var acceptBtn = document.getElementById('cookie-consent-accept');
        var declineBtn = document.getElementById('cookie-consent-decline');

        var existingChoice = localStorage.getItem(STORAGE_KEY);

        if (!existingChoice) {
            banner.classList.remove('d-none');
        }

        function recordChoice(choice) {
            localStorage.setItem(STORAGE_KEY, choice);
            banner.classList.add('d-none');
        }

        acceptBtn.addEventListener('click', function () {
            recordChoice('accepted');
        });

        declineBtn.addEventListener('click', function () {
            recordChoice('declined');
        });
    });
})();
