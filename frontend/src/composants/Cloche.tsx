import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router";

import { useCompteurNotifications, useLireNotifications, useNotifications } from "../api/hooks";
import { quand } from "../lib/format";
import { IconeCloche } from "./Icones";

/** Cloche de notifications : compteur rafraîchi chaque minute, liste à l'ouverture. */
export function Cloche({ compacte = false }: { compacte?: boolean }) {
  const [ouvert, setOuvert] = useState(false);
  const [position, setPosition] = useState<CSSProperties>({});
  const zone = useRef<HTMLDivElement>(null);
  const bouton = useRef<HTMLButtonElement>(null);
  const liste = useRef<HTMLDivElement>(null);
  const naviguer = useNavigate();
  const { data: compteur } = useCompteurNotifications();
  const { data: notifications = [], isPending } = useNotifications(ouvert);
  const lire = useLireNotifications();
  const nonLues = compteur?.non_lues ?? 0;

  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent | KeyboardEvent) => {
      const dedans = zone.current?.contains(e.target as Node) || liste.current?.contains(e.target as Node);
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !dedans) setOuvert(false);
    };
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", fermer);
    return () => {
      document.removeEventListener("mousedown", fermer);
      document.removeEventListener("keydown", fermer);
    };
  }, [ouvert]);

  return (
    <div ref={zone} className="relative">
      <button ref={bouton} type="button" aria-expanded={ouvert} aria-haspopup="dialog"
        onClick={() => {
          // Liste rendue à la racine du document (portail) : le verre (backdrop-filter) de la barre latérale
          // rattacherait sinon même un élément « fixed » à la barre, et le couperait.
          const r = bouton.current!.getBoundingClientRect();
          setPosition(compacte ? { top: r.top, left: r.right + 24 } : { top: r.bottom + 8, right: window.innerWidth - r.right });
          setOuvert(!ouvert);
        }}
        aria-label={nonLues ? `Notifications, ${nonLues} non lue${nonLues > 1 ? "s" : ""}` : "Notifications"}
        className={`relative flex shrink-0 items-center justify-center rounded-full ${compacte ? "size-9 hover:bg-remplissage" : "verre size-11"}`}>
        <IconeCloche taille={compacte ? 18 : 19} />
        {nonLues > 0 && (
          <span aria-hidden="true" className="absolute -top-0.5 -right-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-alerte px-1 text-[11px] font-bold text-white">
            {nonLues > 99 ? "99+" : nonLues}
          </span>
        )}
      </button>
      {ouvert && createPortal(
        <div ref={liste} role="dialog" aria-label="Notifications" style={position}
          className="verre fixed z-50 flex max-h-[70dvh] w-[min(380px,calc(100vw-32px))] flex-col overflow-hidden rounded-[22px]">
          <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
            <span className="text-[15px] font-bold">Notifications</span>
            {nonLues > 0 && (
              <button type="button" onClick={() => lire.mutate(undefined)} className="py-1 text-[13px] font-semibold text-accent-texte">
                Tout marquer comme lu
              </button>
            )}
          </div>
          <ul className="overflow-y-auto px-1.5 pb-1.5">
            {isPending && <li className="px-3 py-4 text-sm text-texte-2">Chargement…</li>}
            {!isPending && notifications.length === 0 && <li className="px-3 py-4 text-sm text-texte-2">Aucune notification.</li>}
            {notifications.map((n) => (
              <li key={n.id}>
                <button type="button" onClick={() => { if (!n.lue_le) lire.mutate(n.id); setOuvert(false); if (n.lien) naviguer(n.lien); }}
                  className="flex w-full gap-2.5 rounded-2xl px-3 py-2.5 text-left hover:bg-remplissage">
                  <span aria-hidden="true" className={`mt-1.5 size-2 shrink-0 rounded-full ${n.lue_le ? "bg-transparent" : "bg-accent"}`} />
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className={`text-sm leading-snug ${n.lue_le ? "" : "font-semibold"}`}>
                      {n.titre}{n.lue_le ? "" : <span className="sr-only"> (non lue)</span>}
                    </span>
                    {n.message && <span className="line-clamp-2 text-[13px] leading-snug text-texte-2 whitespace-pre-line">{n.message}</span>}
                    <span className="text-xs text-texte-3">{quand(n.cree_le)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>,
        document.body,
      )}
    </div>
  );
}
