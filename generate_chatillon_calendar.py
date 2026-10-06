from datetime import datetime, timedelta
from ffbb_api_client_v2 import FFBBAPIClientV2, TokenManager


# ============================================================
# CONFIGURATION
# ============================================================

TEAM_ID = "200000005342013"

TEAM_NAME = "Châtillon-en-Vendelais Basket 2"

OUTPUT_FILE = "calendrier-chatillon.ics"

MIN_MATCHES = 18


# ============================================================
# OUTILS
# ============================================================

def value(obj, name, default=None):
    """Récupère un attribut sur un objet FFBB."""
    return getattr(obj, name, default)


def object_id(obj):
    """Récupère l'ID d'un objet FFBB ou une valeur déjà sous forme d'ID."""

    if obj is None:
        return None

    if isinstance(obj, (str, int)):
        return str(obj)

    identifiant = getattr(obj, "id", None)

    if identifiant is not None:
        return str(identifiant)

    return None


def parse_date(value):
    """Convertit la date FFBB en datetime sans modifier l'heure affichée."""

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    text = str(value).strip()

    if text.endswith("Z"):
        text = text[:-1]

    # ISO classique FFBB
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        pass

    # Formats de secours
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    raise RuntimeError(
        f"Impossible de lire la date FFBB : {value}"
    )


def escape_ics(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


# ============================================================
# API FFBB
# ============================================================

def create_client():

    print("Connexion à l'API FFBB...")

    tokens = TokenManager.get_tokens()

    client = FFBBAPIClientV2.create(
        api_bearer_token=tokens.api_token,
        meilisearch_bearer_token=tokens.meilisearch_token,
    )

    print("Connexion API FFBB OK.")

    return client


def find_engagement(client):

    print()
    print(f"Recherche de l'engagement {TEAM_ID}...")

    # La v1.4.0 possède une recherche d'engagements.
    result = client.search_engagements(
        TEAM_ID
    )

    hits = getattr(result, "hits", [])

    for engagement in hits:

        identifiant = object_id(engagement)

        if identifiant == TEAM_ID:
            print("Engagement trouvé.")
            return engagement

    # Recherche supplémentaire par nom si l'ID n'est
    # pas directement présent dans les résultats.
    result = client.search_engagements(
        "Châtillon-en-Vendelais"
    )

    hits = getattr(result, "hits", [])

    for engagement in hits:

        identifiant = object_id(engagement)

        nom = str(
            value(
                engagement,
                "nom",
                "",
            )
        )

        if (
            identifiant == TEAM_ID
            or "châtillon" in nom.lower()
            or "chatillon" in nom.lower()
        ):
            print(
                f"Engagement trouvé : {nom}"
            )
            return engagement

    raise RuntimeError(
        f"Impossible de trouver l'engagement FFBB {TEAM_ID}."
    )


def get_poule(client, engagement):

    engagement_id = object_id(engagement)

    if not engagement_id:
        raise RuntimeError(
            "Impossible de récupérer l'identifiant de l'engagement."
        )

    print()
    print(
        f"Récupération de l'engagement complet {engagement_id}..."
    )

    # Récupération complète de l'engagement
    full_engagement = client.get_engagement(
        int(engagement_id)
    )

    if full_engagement is None:
        raise RuntimeError(
            f"Impossible de récupérer l'engagement {engagement_id}."
        )

    id_poule = value(
        full_engagement,
        "idPoule",
    )

    poule_id = object_id(id_poule)

    print(
        f"idPoule récupéré : {poule_id}"
    )

    if not poule_id:
        raise RuntimeError(
            "L'engagement complet ne contient pas d'idPoule."
        )

    print(
        f"Récupération de la poule {poule_id}..."
    )

    poule = client.get_poule(
        int(poule_id)
    )

    if poule is None:
        raise RuntimeError(
            f"Impossible de récupérer la poule {poule_id}."
        )

    print(
        f"Poule récupérée : {value(poule, 'nom', 'Poule inconnue')}"
    )

    return poule

# ============================================================
# MATCHS
# ============================================================

def get_matches(poule):

    rencontres = value(
        poule,
        "rencontres",
        [],
    )

    print(
        f"Rencontres dans la poule : {len(rencontres)}"
    )

    matches = []

    for rencontre in rencontres:

        equipe1 = str(
            value(
                rencontre,
                "nomEquipe1",
                "",
            )
        ).strip()

        equipe2 = str(
            value(
                rencontre,
                "nomEquipe2",
                "",
            )
        ).strip()

        engagement1 = object_id(
            value(
                rencontre,
                "idEngagementEquipe1",
            )
        )

        engagement2 = object_id(
            value(
                rencontre,
                "idEngagementEquipe2",
            )
        )

        # Identification principale par ID
        team_is_1 = engagement1 == TEAM_ID
        team_is_2 = engagement2 == TEAM_ID

        # Sécurité supplémentaire par le nom
        if not team_is_1 and not team_is_2:

            if "châtillon" in equipe1.lower() or \
               "chatillon" in equipe1.lower():

                team_is_1 = True

            elif "châtillon" in equipe2.lower() or \
                 "chatillon" in equipe2.lower():

                team_is_2 = True

        if not team_is_1 and not team_is_2:
            continue

        date_raw = value(
            rencontre,
            "date_rencontre",
        )

        if date_raw is None:
            continue

        date_match = parse_date(
            date_raw
        )

        journee = value(
            rencontre,
            "numeroJournee",
            0,
        )

        if team_is_1:

            opponent = equipe2
            domicile = True

        else:

            opponent = equipe1
            domicile = False

        matches.append(
            {
                "journee": int(journee),
                "date": date_match,
                "opponent": opponent,
                "domicile": domicile,
            }
        )

    # Suppression des doublons
    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"],
            match["opponent"],
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    matches.sort(
        key=lambda x: x["date"]
    )

    return matches


# ============================================================
# ICS
# ============================================================

def generate_ics(matches):

    timestamp = datetime.utcnow().strftime(
        "%Y%m%dT%H%M%SZ"
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chatillon-en-Vendelais Basket//DM4//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Châtillon-en-Vendelais Basket 2 - DM4",
    ]

    for match in matches:

        start = match["date"]

        end = start + timedelta(
            hours=2
        )

        start_str = start.strftime(
            "%Y%m%dT%H%M%S"
        )

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

        if match["domicile"]:

            summary = (
                f"{TEAM_NAME} - "
                f"{match['opponent']}"
            )

            location = "Châtillon-en-Vendelais"

        else:

            summary = (
                f"{match['opponent']} - "
                f"{TEAM_NAME}"
            )

            location = match["opponent"]

        uid = (
            f"chatillon-dm4-"
            f"j{match['journee']}-"
            f"{start.strftime('%Y%m%d')}-"
            f"{start.strftime('%H%M')}@github"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{timestamp}",

                # Heure locale FFBB.
                # Pas de conversion UTC.
                f"DTSTART:{start_str}",
                f"DTEND:{end_str}",

                f"SUMMARY:{escape_ics(summary)}",
                f"LOCATION:{escape_ics(location)}",

                (
                    "DESCRIPTION:"
                    f"{escape_ics(TEAM_NAME)} - "
                    f"DM4 - Journée {match['journee']}"
                ),

                "END:VEVENT",
            ]
        )

    lines.append(
        "END:VCALENDAR"
    )

    return "\r\n".join(lines) + "\r\n"


# ============================================================
# MAIN
# ============================================================

def main():

    print("========================================")
    print("Calendrier Châtillon-en-Vendelais DM4")
    print("========================================")

    client = create_client()

    engagement = find_engagement(
        client
    )

    poule = get_poule(
        client,
        engagement
    )

    matches = get_matches(
        poule
    )

    print()
    print(
        f"Matchs Châtillon trouvés : {len(matches)}"
    )

    if len(matches) < MIN_MATCHES:

        raise RuntimeError(
            f"Seulement {len(matches)} matchs trouvés."
        )

    print()
    print("Matchs détectés :")
    print()

    for match in matches:

        statut = (
            "Domicile"
            if match["domicile"]
            else "Extérieur"
        )

        print(
            f"J{match['journee']} | "
            f"{match['date'].strftime('%d/%m/%Y')} | "
            f"{match['date'].strftime('%Hh%M')} | "
            f"{statut} | "
            f"{match['opponent']}"
        )

    ics = generate_ics(
        matches
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        file.write(ics)

    print()
    print(
        f"Calendrier généré : {OUTPUT_FILE}"
    )

    print(
        f"Nombre d'événements : {len(matches)}"
    )

    print("========================================")


if __name__ == "__main__":
    main()
