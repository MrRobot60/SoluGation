import { useAPropos } from "../api/hooks";

/** « Logiciel libre » et lien vers le code source : obligation de l'AGPL-3.0 pour toute version proposée en ligne. */
export function MentionLicence({ className = "" }: { className?: string }) {
  const { data } = useAPropos();
  return (
    <p className={`text-center text-xs text-texte-3 ${className}`}>
      SoluGation, logiciel libre ({data?.licence_libelle ?? "GNU AGPL-3.0 ou licence commerciale"})
      {data?.code_source && (
        <>
          {" · "}
          <a href={data.code_source} target="_blank" rel="noopener noreferrer" className="font-medium text-texte-2 underline underline-offset-2">
            Code source
          </a>
        </>
      )}
    </p>
  );
}
