/* Injects the animated EYEWAZ logo (eye wakes up; sound waves float through the
   ear) wherever the static logo image sits, plus into .hero-logo slots. */
(function () {
  var SVG =
    '<svg class="elogo" viewBox="0 0 64 64" fill="none" stroke="currentColor"' +
    ' stroke-width="3" stroke-linecap="round" stroke-linejoin="round" role="img"' +
    ' aria-label="EYEWAZ logo">' +
    /* ear curve wrapping the right side */
    '<path d="M37 6c12 0 21 9 21 20 0 9-5 13-9 17-3 3-4 6-4 9 0 4-3 7-7 7-3 0-5-1-6-3"/>' +
    /* eye that wakes up + blinks */
    '<g class="eye-g">' +
    '<path d="M7 32q18-15 36 0q-18 15-36 0z"/>' +
    '<circle cx="25" cy="32" r="6"/>' +
    '<circle cx="25" cy="32" r="2" fill="currentColor" stroke="none"/>' +
    '</g>' +
    /* sound waves floating inside the ear */
    '<path class="w1" d="M46 26a7 7 0 0 1 0 12"/>' +
    '<path class="w2" d="M50 22a13 13 0 0 1 0 20"/>' +
    '<path class="w3" d="M54 18a19 19 0 0 1 0 28"/>' +
    '</svg>';
  function swap() {
    document.querySelectorAll(".brand img").forEach(function (img) {
      var span = document.createElement("span");
      span.innerHTML = SVG;
      img.replaceWith(span.firstElementChild);
    });
    document.querySelectorAll(".hero-logo").forEach(function (slot) {
      if (!slot.querySelector(".elogo")) slot.innerHTML = SVG;
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", swap);
  else swap();
})();
