// Deterministic frame seeking: pause every animation and set its time; let templates update text from t.
window.__seek = function (t) {
  document.getAnimations().forEach(function (a) { a.pause(); a.currentTime = t * 1000; });
  if (window.__tick) { window.__tick(t); }
  return document.getAnimations().length;
};
