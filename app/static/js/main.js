//Student_ID_25017334_Name_Priyanshi_Jadeja

//  Go to top button
document.addEventListener("DOMContentLoaded", () => {
    const goTop = document.querySelector(".go-top");
    if (goTop) {
        goTop.addEventListener("click", () => {
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }
});
