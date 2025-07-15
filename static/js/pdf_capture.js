// pdf_capture.js
// This script allows users to capture the visible itinerary section as an image (PNG) or trigger the PDF download button.
// Requires html2canvas (for image capture). Ensure it's included in your HTML.

document.addEventListener('DOMContentLoaded', function() {
    const captureBtn = document.getElementById('capture-btn');
    if (captureBtn) {
        captureBtn.addEventListener('click', function() {
            const itinerarySection = document.querySelector('.itinerary-section');
            if (!itinerarySection) return;
            html2canvas(itinerarySection, {useCORS: true, backgroundColor: '#fff'}).then(function(canvas) {
                // Create a download link for PNG
                const link = document.createElement('a');
                link.download = 'itinerary_capture.png';
                link.href = canvas.toDataURL('image/png');
                link.click();
            });
        });
    }
    // Optionally, allow triggering the PDF download button
    const pdfBtn = document.querySelector('.download-btn');
    const quickPdfBtn = document.getElementById('quick-pdf-btn');
    if (quickPdfBtn && pdfBtn) {
        quickPdfBtn.addEventListener('click', function() {
            pdfBtn.click();
        });
    }
});
