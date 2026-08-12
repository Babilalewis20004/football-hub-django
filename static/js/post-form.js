// Featured image dropzone: forwards clicks/drops to the real file input
// (rendered by Django's ClearableFileInput below it) and mirrors the
// selected file into a live preview, matching the wireframe's imgdrop.
document.addEventListener('DOMContentLoaded', function () {
    var dropzone = document.getElementById('imageDropzone');
    if (!dropzone) return;

    var fileInput = dropzone.parentElement.querySelector('.image-upload-controls input[type="file"]');
    var preview = document.getElementById('imageDropzonePreview');
    var placeholder = document.getElementById('imageDropzonePlaceholder');

    if (!fileInput || !preview || !placeholder) return;

    function showFile(file) {
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function (e) {
            preview.src = e.target.result;
            preview.classList.remove('d-none');
            placeholder.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }

    dropzone.addEventListener('click', function () {
        fileInput.click();
    });

    dropzone.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', function () {
        if (fileInput.files && fileInput.files[0]) {
            showFile(fileInput.files[0]);
        }
    });

    ['dragenter', 'dragover'].forEach(function (eventName) {
        dropzone.addEventListener(eventName, function (event) {
            event.preventDefault();
            event.stopPropagation();
            dropzone.classList.add('is-dragover');
        });
    });

    ['dragleave', 'drop'].forEach(function (eventName) {
        dropzone.addEventListener(eventName, function (event) {
            event.preventDefault();
            event.stopPropagation();
            dropzone.classList.remove('is-dragover');
        });
    });

    dropzone.addEventListener('drop', function (event) {
        var files = event.dataTransfer.files;
        if (!files || !files.length) return;

        fileInput.files = files;
        showFile(files[0]);
    });
});
