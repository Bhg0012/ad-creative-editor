// Deterministic frame seeking: pause every animation and set its time.
window.__seek = function (t) {
  document.getAnimations().forEach(function (a) { a.pause(); a.currentTime = t * 1000; });
  return document.getAnimations().length;
};
