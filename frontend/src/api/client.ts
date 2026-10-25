/**
 * Client de l'API Django : session (cookie HttpOnly) + jeton CSRF relu dans le cookie à chaque écriture
 * (Django le renouvelle à la connexion). Aucune donnée d'authentification n'est stockée côté navigateur.
 */

export class ErreurApi extends Error {
  constructor(
    public statut: number,
    public donnees: unknown,
    message: string,
  ) {
    super(message);
  }
}

function lireCookie(nom: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${nom}=`))
    ?.split("=")[1];
}

let csrfEnCours: Promise<void> | null = null;

async function assurerCsrf() {
  if (lireCookie("csrftoken")) return;
  csrfEnCours ??= fetch("/api/auth/csrf/", { credentials: "same-origin" }).then(() => undefined);
  await csrfEnCours;
}

function messageErreur(donnees: unknown, statut: number): string {
  if (donnees && typeof donnees === "object") {
    const d = donnees as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    const premier = Object.values(d)[0];
    if (Array.isArray(premier) && typeof premier[0] === "string") return premier[0];
  }
  return statut >= 500 ? "Le serveur a rencontré une erreur." : "La requête n'a pas abouti.";
}

export async function api<T>(chemin: string, options: { methode?: string; corps?: unknown } = {}): Promise<T> {
  const methode = options.methode ?? "GET";
  const entetes: Record<string, string> = { Accept: "application/json" };
  if (methode !== "GET") {
    await assurerCsrf();
    entetes["X-CSRFToken"] = lireCookie("csrftoken") ?? "";
  }
  if (options.corps !== undefined) entetes["Content-Type"] = "application/json";

  const reponse = await fetch(chemin, {
    method: methode,
    credentials: "same-origin",
    headers: entetes,
    body: options.corps === undefined ? undefined : JSON.stringify(options.corps),
  });
  if (reponse.status === 204) return undefined as T;
  const donnees = reponse.headers.get("content-type")?.includes("json") ? await reponse.json() : null;
  if (!reponse.ok) throw new ErreurApi(reponse.status, donnees, messageErreur(donnees, reponse.status));
  return donnees as T;
}

/** Envoi multipart avec progression (0 à 1). `fetch` ne remonte pas la progression d'un envoi. */
export async function envoyerFichier<T>(
  chemin: string,
  champs: Record<string, string | string[]>,
  fichier: File,
  surProgression?: (part: number) => void,
): Promise<T> {
  await assurerCsrf();
  const corps = new FormData();
  Object.entries(champs).forEach(([cle, valeur]) =>
    (Array.isArray(valeur) ? valeur : [valeur]).forEach((v) => corps.append(cle, v)));
  corps.append("fichier", fichier, fichier.name);
  return new Promise<T>((resoudre, rejeter) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", chemin);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRFToken", lireCookie("csrftoken") ?? "");
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => e.lengthComputable && surProgression?.(e.loaded / e.total);
    xhr.onerror = () => rejeter(new ErreurApi(0, null, "Envoi interrompu : vérifiez la connexion."));
    xhr.onload = () => {
      let donnees: unknown = null;
      try {
        donnees = JSON.parse(xhr.responseText);
      } catch {
        /* réponse non JSON (coupure par le serveur, page d'erreur) */
      }
      if (xhr.status >= 200 && xhr.status < 300) resoudre(donnees as T);
      else rejeter(new ErreurApi(xhr.status, donnees, messageErreur(donnees, xhr.status)));
    };
    xhr.send(corps);
  });
}

/** Toutes les pages d'une liste paginée (par numéro de page : le lien `next` vise l'hôte interne). */
export async function toutesLesPages<T>(chemin: string): Promise<T[]> {
  const resultats: T[] = [];
  const separateur = chemin.includes("?") ? "&" : "?";
  for (let page = 1; ; page++) {
    const d = await api<{ results: T[]; next: string | null }>(`${chemin}${separateur}taille=500&page=${page}`);
    resultats.push(...d.results);
    if (!d.next) return resultats;
  }
}
