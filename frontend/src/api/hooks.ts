import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, envoyerFichier, ErreurApi, toutesLesPages } from "./client";
import type { Acteur, AnalyseIA, ObjetEbios, Rapport, SuggestionEbios, SyntheseEbios, RecommandationIA, TypeAnalyse, Commentaire, EntreeJournal, NotificationApp, Tache, DocumentAttendu, DocumentDepose, EvaluationMesure, Mesure, Moi, Preuve, ResultatIA, NouveauProjet, Pagine, ProjetResume, Referentiel, Role, StatutConformite, StatutDocument, TableauDeBord, Utilisateur } from "./types";

const pasDeRelanceSiRefus = (essais: number, erreur: Error) =>
  !(erreur instanceof ErreurApi && [401, 403, 404].includes(erreur.statut)) && essais < 2;

export function useMoi() {
  return useQuery({ queryKey: ["moi"], queryFn: () => api<Moi>("/api/auth/moi/"), retry: pasDeRelanceSiRefus });
}

export function useProjets() {
  return useQuery({
    queryKey: ["projets"],
    queryFn: () => api<Pagine<ProjetResume>>("/api/projets/?taille=100"),
    retry: pasDeRelanceSiRefus,
  });
}

export function useTableauDeBord(projetId: string | undefined) {
  return useQuery({
    queryKey: ["tableau-de-bord", projetId],
    queryFn: () => api<TableauDeBord>(`/api/projets/${projetId}/tableau-de-bord/`),
    enabled: Boolean(projetId),
    retry: pasDeRelanceSiRefus,
  });
}

export function useConnexion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (identifiants: { email: string; password: string }) =>
      api<Moi>("/api/auth/connexion/", { methode: "POST", corps: identifiants }),
    onSuccess: (moi) => {
      client.clear();
      client.setQueryData(["moi"], moi);
    },
  });
}

export function useDeconnexion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/api/auth/deconnexion/", { methode: "POST" }),
    onSettled: () => client.clear(),
  });
}

export function useReferentiels() {
  return useQuery({ queryKey: ["referentiels"], queryFn: () => api<Referentiel[]>("/api/referentiels/"), staleTime: 5 * 60_000 });
}

export function useMembres() {
  return useQuery({
    queryKey: ["utilisateurs"],
    queryFn: () => api<Pagine<Utilisateur>>("/api/utilisateurs/?taille=500"),
    select: (d) => d.results.filter((u) => u.is_active),
  });
}

export function useRolesProjet() {
  return useQuery({ queryKey: ["roles", "projet"], queryFn: () => api<Role[]>("/api/roles/?portee=projet"), staleTime: 5 * 60_000 });
}

export function useCreerProjet() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (projet: NouveauProjet) => api<ProjetResume>("/api/projets/", { methode: "POST", corps: projet }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["projets"] }),
  });
}

export function useDocumentsAttendus(projetId: string | undefined) {
  return useQuery({
    queryKey: ["documents-attendus", projetId],
    queryFn: () => api<Pagine<DocumentAttendu>>(`/api/documents-attendus/?projet=${projetId}&taille=500`),
    select: (d) => d.results,
    enabled: Boolean(projetId),
  });
}

export function useDepots(projetId: string | undefined) {
  return useQuery({
    queryKey: ["documents-deposes", projetId],
    queryFn: () => api<Pagine<DocumentDepose>>(`/api/documents-deposes/?projet=${projetId}&taille=500`),
    select: (d) => d.results,
    enabled: Boolean(projetId),
  });
}

function invaliderDocuments(client: ReturnType<typeof useQueryClient>, projetId: string) {
  for (const cle of ["documents-attendus", "documents-deposes", "tableau-de-bord"]) {
    client.invalidateQueries({ queryKey: [cle, projetId] });
  }
}

export function useDeposer(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ fichier, documentAttendu, surProgression }: {
      fichier: File; documentAttendu?: string; surProgression?: (p: number) => void;
    }) =>
      envoyerFichier<DocumentDepose>(
        "/api/documents-deposes/",
        { projet: projetId, ...(documentAttendu ? { document_attendu: documentAttendu } : {}) },
        fichier,
        surProgression,
      ),
    onSuccess: () => invaliderDocuments(client, projetId),
  });
}

export function useStatutDocument(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, statut }: { id: string; statut: StatutDocument }) =>
      api<DocumentAttendu>(`/api/documents-attendus/${id}/`, { methode: "PATCH", corps: { statut } }),
    onSuccess: () => invaliderDocuments(client, projetId),
  });
}

export function useMesures(referentielId: string | undefined) {
  return useQuery({
    queryKey: ["mesures", referentielId],
    queryFn: () => toutesLesPages<Mesure>(`/api/mesures/?referentiel=${referentielId}`),
    enabled: Boolean(referentielId),
    staleTime: 10 * 60_000,
  });
}

export function useEvaluations(projetId: string) {
  return useQuery({
    queryKey: ["statuts-mesures", projetId],
    queryFn: () => toutesLesPages<EvaluationMesure>(`/api/statuts-mesures/?projet=${projetId}`),
  });
}

export function usePreuves(projetId: string) {
  return useQuery({ queryKey: ["preuves", projetId], queryFn: () => toutesLesPages<Preuve>(`/api/preuves/?projet=${projetId}`) });
}

export function useResultatsIA(projetId: string) {
  return useQuery({
    queryKey: ["resultats-ia", projetId],
    queryFn: () => toutesLesPages<ResultatIA>(`/api/resultats-ia/?projet=${projetId}&statut_validation=a_valider&actuels=1`),
  });
}

export function useAnalyses(projetId: string, type: TypeAnalyse) {
  return useQuery({
    queryKey: ["analyses-ia", projetId, type],
    queryFn: () => api<Pagine<AnalyseIA>>(`/api/analyses-ia/?projet=${projetId}&type_analyse=${type}&taille=5`).then((p) => p.results),
    enabled: Boolean(projetId),
    // Tant qu'une analyse tourne en arrière-plan, on suit son état.
    refetchInterval: (q) => (q.state.data?.some((a) => a.etat === "en_attente" || a.etat === "en_cours") ? 3000 : false),
  });
}

export function useLancerAnalyse(projetId: string, type: TypeAnalyse) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (selection: { taches?: string[]; documents?: string[] } = {}) =>
      api<AnalyseIA>("/api/analyses-ia/", { methode: "POST", corps: { projet: projetId, type_analyse: type, ...selection } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["analyses-ia", projetId, type] }),
  });
}

export function useRecommandations(projetId: string) {
  return useQuery({
    queryKey: ["recommandations-ia", projetId],
    queryFn: () => toutesLesPages<RecommandationIA>(`/api/recommandations-ia/?projet=${projetId}`),
    enabled: Boolean(projetId),
  });
}

export function useStatuerRecommandation(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "valide" | "rejete" }) =>
      api<RecommandationIA>(`/api/recommandations-ia/${id}/statuer/`, { methode: "POST", corps: { decision } }),
    onSuccess: (r) => {
      for (const cle of ["recommandations-ia", "taches"]) client.invalidateQueries({ queryKey: [cle, projetId] });
      if (r.tache) client.invalidateQueries({ queryKey: ["historique", r.tache] });
    },
  });
}

function invaliderMesures(client: ReturnType<typeof useQueryClient>, projetId: string) {
  for (const cle of ["statuts-mesures", "preuves", "resultats-ia", "tableau-de-bord"]) {
    client.invalidateQueries({ queryKey: [cle, projetId] });
  }
}

export function useEvaluer(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ existante, mesure, statut, justification }: {
      existante?: EvaluationMesure; mesure: string; statut: StatutConformite; justification: string;
    }) =>
      existante
        ? api<EvaluationMesure>(`/api/statuts-mesures/${existante.id}/`, { methode: "PATCH", corps: { statut, justification } })
        : api<EvaluationMesure>("/api/statuts-mesures/", { methode: "POST", corps: { projet: projetId, mesure, statut, justification } }),
    onSuccess: () => invaliderMesures(client, projetId),
  });
}

export function useDeposerPreuve(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ fichier, mesures, titre, serie, surProgression }: {
      fichier: File; mesures: string[]; titre: string; serie?: string; surProgression?: (p: number) => void;
    }) =>
      envoyerFichier<Preuve>("/api/preuves/", { projet: projetId, titre, mesures, ...(serie ? { serie } : {}) }, fichier, surProgression),
    onSuccess: () => invaliderMesures(client, projetId),
  });
}

export function useStatuerIA(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "valide" | "rejete" }) =>
      api<ResultatIA>(`/api/resultats-ia/${id}/statuer/`, { methode: "POST", corps: { decision } }),
    onSuccess: () => invaliderMesures(client, projetId),
  });
}

export function useActeurs(projetId: string) {
  return useQuery({ queryKey: ["acteurs", projetId], queryFn: () => toutesLesPages<Acteur>(`/api/acteurs/?projet=${projetId}`) });
}

export function useTaches(projetId: string) {
  return useQuery({ queryKey: ["taches", projetId], queryFn: () => toutesLesPages<Tache>(`/api/taches/?projet=${projetId}`) });
}

function invaliderTaches(client: ReturnType<typeof useQueryClient>, projetId: string) {
  for (const cle of ["taches", "tableau-de-bord", "historique", "commentaires"]) client.invalidateQueries({ queryKey: [cle] });
  client.invalidateQueries({ queryKey: ["taches", projetId] });
}

export function useEnregistrerTache(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...champs }: Partial<Tache> & { id?: string }) =>
      id
        ? api<Tache>(`/api/taches/${id}/`, { methode: "PATCH", corps: champs })
        : api<Tache>("/api/taches/", { methode: "POST", corps: { projet: projetId, ...champs } }),
    onSuccess: () => invaliderTaches(client, projetId),
  });
}

export function useGenererPlanAction(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ crees: number }>(`/api/projets/${projetId}/generer-plan-action/`, { methode: "POST" }),
    onSuccess: () => invaliderTaches(client, projetId),
  });
}

export function useCommentaires(tacheId: string | undefined) {
  return useQuery({
    queryKey: ["commentaires", tacheId],
    queryFn: () => toutesLesPages<Commentaire>(`/api/commentaires/?tache=${tacheId}`),
    enabled: Boolean(tacheId),
  });
}

export function useCommenter(projetId: string, tacheId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (texte: string) => api<Commentaire>("/api/commentaires/", { methode: "POST", corps: { projet: projetId, tache: tacheId, texte } }),
    onSuccess: () => invaliderTaches(client, projetId),
  });
}

export function useHistorique(objetId: string | undefined) {
  return useQuery({
    queryKey: ["historique", objetId],
    queryFn: () => toutesLesPages<EntreeJournal>(`/api/journal/?objet_id=${objetId}`),
    enabled: Boolean(objetId),
  });
}

export function useNotifications(active: boolean) {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Pagine<NotificationApp>>("/api/notifications/?taille=30"),
    select: (d) => d.results,
    enabled: active,
  });
}

export function useCompteurNotifications() {
  return useQuery({
    queryKey: ["notifications", "compteur"],
    queryFn: () => api<{ non_lues: number }>("/api/notifications/compteur/"),
    refetchInterval: 60_000,
  });
}

export function useLireNotifications() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id?: string) =>
      api<unknown>(id ? `/api/notifications/${id}/lue/` : "/api/notifications/tout-lu/", { methode: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useRapports(projetId: string) {
  return useQuery({
    queryKey: ["rapports", projetId],
    queryFn: () => toutesLesPages<Rapport>(`/api/rapports/?projet=${projetId}`),
    enabled: Boolean(projetId),
    // Rédaction par l'IA en arrière-plan : on suit son avancement.
    refetchInterval: (q) => (q.state.data?.some((r) => r.redaction.etat === "en_attente" || r.redaction.etat === "en_cours") ? 3000 : false),
  });
}

export function useGenererRapport(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<Rapport>("/api/rapports/", { methode: "POST", corps: { projet: projetId } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["rapports", projetId] }),
  });
}

export function useEditerRapport(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, sections }: { id: string; sections: { cle: string; texte: string }[] }) =>
      api<Rapport>(`/api/rapports/${id}/`, { methode: "PATCH", corps: { sections } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["rapports", projetId] }),
  });
}

export function useValiderRapport(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<Rapport>(`/api/rapports/${id}/valider/`, { methode: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["rapports", projetId] }),
  });
}

/* ---- EBIOS RM ---------------------------------------------------------------------------- */

function invaliderEbios(client: ReturnType<typeof useQueryClient>, projetId: string) {
  client.invalidateQueries({ queryKey: ["ebios", projetId] });
  client.invalidateQueries({ queryKey: ["taches", projetId] });
}

export function useObjetsEbios(projetId: string, ressource: string) {
  return useQuery({
    queryKey: ["ebios", projetId, ressource],
    queryFn: () => toutesLesPages<ObjetEbios>(`/api/ebios/${ressource}/?projet=${projetId}`),
    enabled: Boolean(projetId),
  });
}

/** Plusieurs ressources EBIOS en une fois : { ressource: objets }. */
export function useToutEbios(projetId: string, ressources: readonly string[]) {
  const resultats = useQueries({
    queries: ressources.map((r) => ({
      queryKey: ["ebios", projetId, r],
      queryFn: () => toutesLesPages<ObjetEbios>(`/api/ebios/${r}/?projet=${projetId}`),
      enabled: Boolean(projetId),
    })),
  });
  return Object.fromEntries(ressources.map((r, i) => [r, resultats[i].data ?? []])) as Record<string, ObjetEbios[]>;
}

export function useSyntheseEbios(projetId: string) {
  return useQuery({
    queryKey: ["ebios", projetId, "synthese"],
    queryFn: () => api<SyntheseEbios>(`/api/ebios/synthese/?projet=${projetId}`),
    enabled: Boolean(projetId),
    retry: pasDeRelanceSiRefus,
  });
}

export function useEnregistrerEbios(projetId: string, ressource: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...champs }: { id?: string; [champ: string]: unknown }) =>
      id
        ? api<ObjetEbios>(`/api/ebios/${ressource}/${id}/`, { methode: "PATCH", corps: champs })
        : api<ObjetEbios>(`/api/ebios/${ressource}/`, { methode: "POST", corps: { projet: projetId, ...champs } }),
    onSuccess: () => invaliderEbios(client, projetId),
  });
}

export function useSupprimerEbios(projetId: string, ressource: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/ebios/${ressource}/${id}/`, { methode: "DELETE" }),
    onSuccess: () => invaliderEbios(client, projetId),
  });
}

export function usePreremplirSocle(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ crees: number }>("/api/ebios/socle/", { methode: "POST", corps: { projet: projetId } }),
    onSuccess: () => invaliderEbios(client, projetId),
  });
}

export function useSuggestionsEbios(projetId: string) {
  return useQuery({
    queryKey: ["ebios", projetId, "suggestions"],
    queryFn: () => toutesLesPages<SuggestionEbios>(`/api/ebios/suggestions/?projet=${projetId}&statut_validation=a_valider`),
    enabled: Boolean(projetId),
  });
}

export function useDemanderSuggestions(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (atelier: number) =>
      api<{ analyse: string }>("/api/ebios/suggestions/demander/", { methode: "POST", corps: { projet: projetId, atelier } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["analyses-ia", projetId, "suggestion_ebios"] }),
  });
}

export function useStatuerSuggestion(projetId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, contenu }: { id: string; decision: "valide" | "rejete"; contenu?: Record<string, unknown> }) =>
      api<SuggestionEbios>(`/api/ebios/suggestions/${id}/statuer/`, { methode: "POST", corps: { decision, contenu } }),
    onSuccess: () => invaliderEbios(client, projetId),
  });
}
