/**
 * Main JavaScript file for PDF Test Generator
 */

document.addEventListener('DOMContentLoaded', function() {
    // Handle form submissions with validation
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUploadForm);
    }
    
    // Setup countdown timer for tests
    const timerElement = document.getElementById('timer');
    if (timerElement) {
        startTimer(3600, timerElement); // 60 minutes by default
    }
    
    // Add animation to badges
    const badges = document.querySelectorAll('.badge-earned:not(.locked)');
    badges.forEach(badge => {
        badge.classList.add('animate__animated', 'animate__pulse');
    });
});

/**
 * Handle the upload form submission
 * @param {Event} event - The form submission event
 */
function handleUploadForm(event) {
    const fileInput = document.getElementById('pdf_file');
    const submitBtn = document.querySelector('#uploadForm button[type="submit"]');
    
    if (fileInput && fileInput.files.length === 0) {
        event.preventDefault();
        // Show error message
        document.getElementById('fileError').textContent = 'Please select a PDF file';
        document.getElementById('fileError').classList.remove('d-none');
        return false;
    }
    
    // Show loading state
    if (submitBtn) {
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        submitBtn.disabled = true;
    }
    
    return true;
}

/**
 * Start a countdown timer for test time limit
 * @param {number} duration - Total seconds for the timer
 * @param {HTMLElement} display - The element to display the timer
 */
function startTimer(duration, display) {
    let timer = duration;
    let minutes, seconds;
    
    const interval = setInterval(function () {
        minutes = parseInt(timer / 60, 10);
        seconds = parseInt(timer % 60, 10);

        minutes = minutes < 10 ? "0" + minutes : minutes;
        seconds = seconds < 10 ? "0" + seconds : seconds;

        display.textContent = minutes + ":" + seconds;

        if (--timer < 0) {
            clearInterval(interval);
            display.textContent = "00:00";
            // Auto-submit the test when time is up
            const testForm = document.getElementById('testForm');
            if (testForm) {
                testForm.submit();
            }
        }
    }, 1000);
}

/**
 * Format time in MM:SS format
 * @param {number} seconds - Total seconds
 * @returns {string} Formatted time
 */
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}