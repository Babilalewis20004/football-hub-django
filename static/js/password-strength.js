const passwordInput = document.querySelector("#id_password1");
const strengthBar = document.querySelector("#strength-bar");

if (passwordInput) {
    passwordInput.addEventListener("input", () => {
        const val = passwordInput.value;
        let strength = 0;

        if (val.length > 6) strength++;
        if (/[A-Z]/.test(val)) strength++;
        if (/[0-9]/.test(val)) strength++;
        if (/[^A-Za-z0-9]/.test(val)) strength++;

        const widths = ["0%", "25%", "50%", "75%", "100%"];
        const colors = ["transparent", "#ff4d4d", "#ffa64d", "#ffff4d", "#00ffbf"];

        strengthBar.style.width = widths[strength];
        strengthBar.style.background = colors[strength];
    });
}
