import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ErreurApi } from "./client";
import type { Moi, Pagine, ProjetResume, TableauDeBord } from "./types";

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
