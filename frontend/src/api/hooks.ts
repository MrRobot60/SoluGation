import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, envoyerFichier, ErreurApi } from "./client";
import type { DocumentAttendu, DocumentDepose, Moi, NouveauProjet, Pagine, ProjetResume, Referentiel, Role, StatutDocument, TableauDeBord, Utilisateur } from "./types";

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
