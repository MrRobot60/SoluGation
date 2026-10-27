import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { taille?: number };

function Base({ taille = 19, children, ...props }: P) {
  return (
    <svg
      width={taille}
      height={taille}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconeTableau = (p: P) => (
  <Base {...p}>
    <rect x="4" y="4" width="7" height="7" rx="2" />
    <rect x="13" y="4" width="7" height="7" rx="2" />
    <rect x="4" y="13" width="7" height="7" rx="2" />
    <rect x="13" y="13" width="7" height="7" rx="2" />
  </Base>
);
export const IconeMesures = (p: P) => (
  <Base {...p}>
    <path d="M10 6h10M10 12h10M10 18h10" />
    <path d="M4 6l1.2 1.2L7.5 5M4 12l1.2 1.2L7.5 11M4 18l1.2 1.2 2.3-2.2" />
  </Base>
);
export const IconeDocument = (p: P) => (
  <Base {...p}>
    <path d="M7 3.5h7l4 4v13H7z" />
    <path d="M14 3.5v4h4" />
  </Base>
);
export const IconeTache = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M8.5 12.2l2.4 2.4 4.6-5" />
  </Base>
);
export const IconeCercle = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8.5" />
  </Base>
);
export const IconeBouclier = (p: P) => (
  <Base {...p}>
    <path d="M12 3.5l7 3v5c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9v-5z" />
  </Base>
);
export const IconeCouches = (p: P) => (
  <Base {...p}>
    <path d="M12 4l8 4-8 4-8-4z" />
    <path d="M4 12l8 4 8-4" />
    <path d="M4 16l8 4 8-4" />
  </Base>
);
export const IconeCalendrier = (p: P) => (
  <Base {...p}>
    <rect x="4" y="5.5" width="16" height="14" rx="3" />
    <path d="M4 10h16M9 3.5v4M15 3.5v4" />
  </Base>
);
export const IconeRapports = (p: P) => (
  <Base {...p}>
    <path d="M6 20V11M12 20V5M18 20v-6" />
  </Base>
);
export const IconeReglages = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" />
  </Base>
);
export const IconeRecherche = (p: P) => (
  <Base strokeWidth={1.8} {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M16 16l4 4" />
  </Base>
);
export const IconeCloche = (p: P) => (
  <Base strokeWidth={1.8} {...p}>
    <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
    <path d="M10 20.5a2 2 0 0 0 4 0" />
  </Base>
);
export const IconeDepot = (p: P) => (
  <Base strokeWidth={2.2} {...p}>
    <path d="M12 16V5" />
    <path d="M7.5 9.5L12 5l4.5 4.5" />
    <path d="M5 19h14" />
  </Base>
);
export const IconePlus = (p: P) => (
  <Base strokeWidth={2.2} {...p}>
    <path d="M12 5v14M5 12h14" />
  </Base>
);
export const IconeEtincelle = (p: P) => (
  <Base {...p}>
    <path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1-5.1-1.9 5.1-1.9z" />
  </Base>
);
export const IconeChevronHautBas = (p: P) => (
  <Base strokeWidth={2.2} {...p}>
    <path d="M8 9l4-4 4 4" />
    <path d="M8 15l4 4 4-4" />
  </Base>
);
export const IconeSoleil = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
  </Base>
);
export const IconeLune = (p: P) => (
  <Base {...p}>
    <path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z" />
  </Base>
);
export const IconeAuto = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none" />
  </Base>
);

export function Chevron() {
  return (
    <svg width="8" height="14" viewBox="0 0 8 14" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0 text-texte-3">
      <path d="M1.5 1.5L6.5 7l-5 5.5" />
    </svg>
  );
}

export const IconeFenetre = (p: P) => (
  <Base {...p}>
    <rect x="3.5" y="5" width="17" height="14" rx="3" />
    <path d="M3.5 9.5h17M7 7.2h.01M9.5 7.2h.01" />
  </Base>
);
export const IconePortable = (p: P) => (
  <Base {...p}>
    <rect x="5" y="5" width="14" height="10" rx="2" />
    <path d="M3 19h18" />
  </Base>
);
export const IconeReseau = (p: P) => (
  <Base {...p}>
    <rect x="9" y="3.5" width="6" height="5" rx="1.5" />
    <rect x="3.5" y="15.5" width="6" height="5" rx="1.5" />
    <rect x="14.5" y="15.5" width="6" height="5" rx="1.5" />
    <path d="M12 8.5v3.5M6.5 15.5V12h11v3.5" />
  </Base>
);
export const IconePoints = (p: P) => (
  <Base {...p}>
    <circle cx="6" cy="12" r="1" fill="currentColor" />
    <circle cx="12" cy="12" r="1" fill="currentColor" />
    <circle cx="18" cy="12" r="1" fill="currentColor" />
  </Base>
);
export const IconeCroix = (p: P) => (
  <Base strokeWidth={2} {...p}>
    <path d="M7 7l10 10M17 7L7 17" />
  </Base>
);
export const IconeCoche = (p: P) => (
  <Base strokeWidth={2.4} {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Base>
);

export const IconeAide = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9.6 9.4a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.7" />
    <circle cx="12" cy="16.9" r="0.6" fill="currentColor" stroke="none" />
  </Base>
);
