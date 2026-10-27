// Thème posé avant le premier rendu (pas de flash) : choix enregistré, sinon préférence système.
(function () {
  var choix = null;
  try { choix = localStorage.getItem("sg-theme"); } catch (e) {}
  var sombre = choix ? choix === "sombre" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = sombre ? "sombre" : "clair";
})();
