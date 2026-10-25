from django.db.models import Model

from apps.audit.models import JournalAudit


def _valeur(v):
    if isinstance(v, Model):
        return str(v.pk)
    if isinstance(v, (list, tuple, set)) or hasattr(v, "all"):
        return sorted(_valeur(x) for x in (v.all() if hasattr(v, "all") else v))
    return v if isinstance(v, (str, int, float, bool, type(None))) else str(v)


def instantane(donnees):
    """Valeurs saisies à la création (fichiers exclus)."""
    return {k: _valeur(v) for k, v in donnees.items() if not hasattr(v, "read")}


def difference(instance, donnees):
    """Avant/après des seuls champs modifiés (fichiers exclus)."""
    diff = {}
    for champ, nouveau in donnees.items():
        if hasattr(nouveau, "read"):
            continue
        ancien = getattr(instance, champ, None)
        a, n = _valeur(ancien), _valeur(nouveau)
        if a != n:
            diff[champ] = {"avant": a, "apres": n}
    return diff


def journaliser(request, action, objet, projet=None, donnees=None):
    return JournalAudit.enregistrer(
        organisation=request.user.organisation,
        action=action,
        objet=objet,
        acteur=request.user,
        projet=projet,
        donnees=donnees,
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
