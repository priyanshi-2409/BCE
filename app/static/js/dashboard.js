//Student_ID_25017334_Name_Priyanshi_Jadeja

// Show/hide booking form
const showBookingBtn = document.getElementById("showBookingBtn");
const bookingForm = document.getElementById("bookingForm");

if (showBookingBtn) {
    showBookingBtn.addEventListener("click", () => {
        const currentDisplay = window.getComputedStyle(bookingForm).display;

        bookingForm.style.display = currentDisplay === "none" ? "block" : "none";
    });
}
