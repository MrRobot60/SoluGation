import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { useVisite } from "../api/hooks";
import { Disposition } from "../composants/Disposition";
import { IconeRecherche } from "../composants/Icones";
import { MentionLicence } from "../composants/MentionLicence";
import { oublierVisite } from "../composants/VisiteGuidee";
import { page as trouverPage, PAGES, rechercher, rendre } from "../lib/docs";

function Recherche({ q, setQ }: { q: string; setQ: (q: string) => void }) {
  return (
    <label className="flex h-11 min-w-0 items-center gap-2.5 rounded-full bg-groupe px-4 shadow-groupe">
      <IconeRecherche taille={17} className="shrink-0 text-texte-2" />
      <span className="sr-only">Rechercher dans la documentation</span>
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher : installation, dérogation, clé d'API…"
        className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-texte-3" />
    </label>
  );
}

function Resultats({ q, choisir }: { q: string; choisir: () => void }) {
  const resultats = useMemo(() => rechercher(q), [q]);
  if (q.trim().length < 2) return null;
  return (
    <section aria-label="Résultats de la recherche" aria-live="polite" className="flex flex-col gap-2">
      <p className="text-[13px] text-texte-2">{resultats.length ? `${resultats.length} résultat${resultats.length > 1 ? "s" : ""}` : "Aucun résultat."}</p>
      <ul className="flex flex-col gap-1.5">
        {resultats.map((r) => (
          <li key={`${r.page.cle}#${r.ancre}`}>
            <Link to={`/aide/${r.page.cle}${r.ancre ? `#${r.ancre}` : ""}`} onClick={choisir}
              className="flex flex-col gap-0.5 rounded-2xl bg-groupe px-4 py-3 shadow-groupe hover:bg-remplissage">
              <span className="text-xs font-semibold text-texte-2">{r.page.titre}</span>
              <span className="text-[15px] font-semibold">{r.titre}</span>
              {r.extrait && <span className="line-clamp-2 text-[13px] text-texte-2">{r.extrait}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Sommaire() {
  const visite = useVisite();
  return (
    <div className="flex flex-col gap-4">
      <button type="button" disabled={visite.isPending} onClick={() => { oublierVisite(); visite.mutate("revoir"); }}
        className="self-start rounded-full bg-remplissage px-4 py-2 text-sm font-semibold text-accent-texte">
        Revoir la visite guidée
      </button>
      <ul className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {PAGES.map((p) => (
          <li key={p.cle}>
            <Link to={`/aide/${p.cle}`} className="flex h-full flex-col gap-1 rounded-groupe bg-groupe px-4 py-3.5 shadow-groupe hover:bg-remplissage">
              <span className="text-xs font-semibold text-texte-3 tabular-nums">{p.cle.slice(0, 2)}</span>
              <span className="text-[17px] font-bold">{p.titre}</span>
              <span className="line-clamp-2 text-[13px] text-texte-2">{p.resume}</span>
            </Link>
          </li>
        ))}
      </ul>
      <MentionLicence className="pt-2" />
    </div>
  );
}

function Contenu({ cle }: { cle: string }) {
  const p = trouverPage(cle)!;
  const html = useMemo(() => rendre(p), [p]);
  const { hash } = useLocation();
  const naviguer = useNavigate();

  useEffect(() => {
    const cible = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    if (cible) cible.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [cle, hash]);

  // Liens internes : navigation sans rechargement ; boutons « Copier » des blocs de commandes.
  const clic = (e: MouseEvent) => {
    const el = e.target as HTMLElement;
    const copier = el.closest<HTMLButtonElement>("[data-copier]");
    if (copier) {
      void navigator.clipboard?.writeText(copier.parentElement?.querySelector("pre")?.textContent ?? "").then(() => {
        copier.textContent = "Copié";
        setTimeout(() => (copier.textContent = "Copier"), 1500);
      });
      return;
    }
    const lien = el.closest("a");
    const href = lien?.getAttribute("href");
    if (href?.startsWith("/") && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
      e.preventDefault();
      naviguer(href);
    }
  };

  const index = PAGES.indexOf(p);
  const [avant, apres] = [PAGES[index - 1], PAGES[index + 1]];
  return (
    <div className="flex min-w-0 flex-1 gap-8">
      <article className="min-w-0 max-w-[780px] flex-1">
        <section onClick={clic} className="doc" dangerouslySetInnerHTML={{ __html: html }} />
        <nav aria-label="Pages voisines" className="mt-10 flex flex-wrap justify-between gap-3 border-t border-separateur pt-5">
          {avant ? <Link to={`/aide/${avant.cle}`} className="text-sm font-semibold text-accent-texte">← {avant.titre}</Link> : <span />}
          {apres && <Link to={`/aide/${apres.cle}`} className="text-sm font-semibold text-accent-texte">{apres.titre} →</Link>}
        </nav>
      </article>
      {p.titres.length > 2 && (
        <nav aria-label="Sur cette page" className="sticky top-6 hidden max-h-[calc(100dvh-48px)] w-[220px] shrink-0 self-start overflow-y-auto xl:block">
          <p className="mb-2 text-xs font-semibold tracking-wide text-texte-3 uppercase">Sur cette page</p>
          <ul className="flex flex-col gap-1 border-l border-separateur">
            {p.titres.filter((t) => t.niveau <= 3).map((t) => (
              <li key={t.ancre}>
                <a href={`#${t.ancre}`} onClick={(e) => { e.preventDefault(); naviguer(`#${t.ancre}`); }}
                  className={`-ml-px block border-l py-0.5 text-[13px] hover:text-texte ${hash === `#${t.ancre}` ? "border-accent font-semibold text-accent-texte" : "border-transparent text-texte-2"} ${t.niveau === 3 ? "pl-6" : "pl-3"}`}>
                  {t.texte}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}

export function PageAide() {
  const { page: cle } = useParams();
  const [q, setQ] = useState("");
  const naviguer = useNavigate();
  const courante = cle ? trouverPage(cle) : undefined;

  useEffect(() => {
    if (cle && !courante) naviguer("/aide", { replace: true });
  }, [cle, courante, naviguer]);

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <Link to="/aide" className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Aide</Link>
          {!courante && (
            <p className="max-w-[720px] text-[15px] text-texte-2">
              Installation, utilisation, intelligence artificielle, dépannage et développement : la documentation complète de SoluGation,
              identique à celle du dépôt.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-[240px] flex-1"><Recherche q={q} setQ={setQ} /></div>
          {courante && (
            <select aria-label="Page de la documentation" value={courante.cle} onChange={(e) => naviguer(`/aide/${e.target.value}`)}
              className="max-w-full rounded-full bg-groupe px-4 py-2.5 text-[14px] shadow-groupe outline-none">
              {PAGES.map((p) => <option key={p.cle} value={p.cle}>{p.titre}</option>)}
            </select>
          )}
        </div>
        <Resultats q={q} choisir={() => setQ("")} />
        {q.trim().length < 2 && (courante ? (
          <Contenu cle={courante.cle} />
        ) : <Sommaire />)}
      </div>
    </Disposition>
  );
}
