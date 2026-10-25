import { useCallback, useEffect, useState } from "react";

export type ChoixTheme = "systeme" | "clair" | "sombre";
const CLE = "sg-theme";
const requeteSombre = () => window.matchMedia("(prefers-color-scheme: dark)");

function lireChoix(): ChoixTheme {
  try {
    const v = localStorage.getItem(CLE);
    return v === "clair" || v === "sombre" ? v : "systeme";
  } catch {
    return "systeme";
  }
}

function appliquer(choix: ChoixTheme) {
  const sombre = choix === "systeme" ? requeteSombre().matches : choix === "sombre";
  document.documentElement.dataset.theme = sombre ? "sombre" : "clair";
}

/** Préférence d'affichage, mémorisée dans ce navigateur (confort uniquement). */
export function useTheme() {
  const [choix, setChoix] = useState<ChoixTheme>(lireChoix);

  useEffect(() => {
    appliquer(choix);
    if (choix !== "systeme") return;
    const mq = requeteSombre();
    const suivre = () => appliquer("systeme");
    mq.addEventListener("change", suivre);
    return () => mq.removeEventListener("change", suivre);
  }, [choix]);

  const choisir = useCallback((nouveau: ChoixTheme) => {
    try {
      if (nouveau === "systeme") localStorage.removeItem(CLE);
      else localStorage.setItem(CLE, nouveau);
    } catch {
      /* stockage indisponible : le choix vaut pour la session */
    }
    setChoix(nouveau);
  }, []);

  return { choix, choisir };
}
