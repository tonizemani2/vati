if (sessionStorage.getItem("hide-nav-banner") === "true") {
 document.documentElement.classList.add("hide-nav-banner");
}
document.addEventListener("DOMContentLoaded", function () {
 document.querySelectorAll(".nav_banner_close_wrap").forEach((button) => {
 button.addEventListener("click", function () {
 sessionStorage.setItem("hide-nav-banner", "true");
 document.documentElement.classList.add("hide-nav-banner");
 });
 });
 document.querySelectorAll(".nav_skip_wrap").forEach(function (link) {
 const target = document.querySelector("main");
 if (!target) return;
 link.addEventListener("click", function () {
 target.setAttribute("tabindex", "-1");
 target.focus();
 });
 });
});