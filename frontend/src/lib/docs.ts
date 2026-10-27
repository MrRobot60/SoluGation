import DOMPurify from "dompurify";
import { Marked, type Tokens } from "marked";

import { brut, slug } from "./aide";

// Documentation du dépôt (`docs/*.md`), embarquée à la construction : la même source sur GitHub et dans l'appli.
const fichiers = import.meta.glob("../../../docs/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

export type Titre = { niveau: number; texte: string; ancre: string };
export type PageDoc = { cle: string; titre: string; resume: string; source: string; titres: Titre[] };
export type Section = { page: PageDoc; titre: string; ancre: string; texte: string };

const echapper = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function ancre(texte: string, vues: Map<string, number>) {
  const base = slug(texte);
  const n = vues.get(base) ?? 0;
  vues.set(base, n + 1);
  return n ? `${base}-${n}` : base;
}

/** `07-ia.md#x` → `/aide/07-ia#x` ; `../README.md` → accueil de l'aide. */
function cible(href: string) {
  const page = href.match(/^(?:\.\/)?(\d\d-[\w-]+)\.md(#.*)?$/);
  if (page) return `/aide/${page[1]}${page[2] ?? ""}`;
  if (/^(?:\.\.\/)?README\.md$/.test(href)) return "/aide";
  return href;
}

function analyser(cle: string, source: string): PageDoc {
  const vues = new Map<string, number>();
  const titres: Titre[] = [];
  let titre = cle;
  let resume = "";
  for (const t of new Marked().lexer(source)) {
    if (t.type === "heading") {
      if (t.depth === 1) titre = brut(t.text);
      else titres.push({ niveau: t.depth, texte: brut(t.text), ancre: ancre(t.text, vues) });
    } else if (t.type === "paragraph" && !resume) resume = brut(t.text);
  }
  return { cle, titre, resume, source, titres };
}

export const PAGES: PageDoc[] = Object.entries(fichiers)
  .map(([chemin, source]) => analyser(chemin.split("/").pop()!.replace(/\.md$/, ""), source))
  .sort((a, b) => a.cle.localeCompare(b.cle));

export const page = (cle: string) => PAGES.find((p) => p.cle === cle);

export function rendre(p: PageDoc): string {
  const vues = new Map<string, number>();
  const marked = new Marked({ gfm: true });
  marked.use({
    renderer: {
      heading({ tokens, depth, text }: Tokens.Heading) {
        const contenu = this.parser.parseInline(tokens);
        return depth === 1 ? `<h1>${contenu}</h1>` : `<h${depth} id="${ancre(text, vues)}">${contenu}</h${depth}>`;
      },
      link({ href, tokens, title }: Tokens.Link) {
        const lien = cible(href);
        const externe = /^https?:/.test(lien);
        return `<a href="${echapper(lien)}"${title ? ` title="${echapper(title)}"` : ""}${externe ? ' target="_blank" rel="noopener noreferrer"' : ""}>${this.parser.parseInline(tokens)}</a>`;
      },
      code({ text, lang }: Tokens.Code) {
        return `<div class="doc-code"><button type="button" data-copier>Copier</button><pre><code${lang ? ` data-langage="${echapper(lang)}"` : ""}>${echapper(text)}</code></pre></div>`;
      },
    },
  });
  return DOMPurify.sanitize(marked.parse(p.source, { async: false }), { ADD_ATTR: ["target"] });
}

const normaliser = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

const SECTIONS: Section[] = PAGES.flatMap((p) => {
  const vues = new Map<string, number>();
  const sections: Section[] = [{ page: p, titre: p.titre, ancre: "", texte: "" }];
  for (const t of new Marked().lexer(p.source)) {
    if (t.type === "heading" && t.depth > 1) sections.push({ page: p, titre: brut(t.text), ancre: ancre(t.text, vues), texte: "" });
    else if (t.type !== "heading") sections[sections.length - 1].texte += ` ${brut(t.raw)}`;
  }
  return sections;
});

/** Recherche plein texte, insensible à la casse et aux accents ; titres d'abord. */
export function rechercher(q: string, max = 30): (Section & { extrait: string })[] {
  const mots = normaliser(q).split(/\s+/).filter((m) => m.length >= 2);
  if (!mots.length) return [];
  return SECTIONS
    .map((s) => {
      const titre = normaliser(s.titre);
      const texte = normaliser(s.texte);
      if (!mots.every((m) => titre.includes(m) || texte.includes(m))) return null;
      const score = mots.filter((m) => titre.includes(m)).length * 10 - (s.ancre ? 0 : 1);
      const i = texte.indexOf(mots[0]);
      const debut = Math.max(0, i - 60);
      const extrait = i < 0 ? s.texte.slice(0, 140) : `${debut ? "…" : ""}${s.texte.slice(debut, i + 100).replace(/\s+/g, " ").trim()}…`;
      return { ...s, extrait, score };
    })
    .filter((s): s is Section & { extrait: string; score: number } => s !== null)
    .sort((a, b) => b.score - a.score)
    .slice(0, max);
}
