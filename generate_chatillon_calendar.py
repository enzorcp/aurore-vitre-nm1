from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

from ffbb_api_client_v2 import FFBBAPIClientV2, TokenManager


# ============================================================
# CONFIGURATION
# ============================================================

TEAM_ID = 200000005342013

OUTPUT_FILE = "calendrier-chatillon.ics"

TEAM_NAME = "Châtillon-en-Vendelais Basket 2"

TIMEZONE = ZoneInfo("Europe/Paris")

# Nombre minimum de rencontres attendu.
# On ne demande pas 22 obligatoirement car certaines rencontres
# peuvent ne pas encore être programmées dans FFBB.
MIN_MATCHES = 18


# ============================================================
# OUTILS
# ============================================================

def to_dict(value):
    """
    Convertit les objets retournés par l'API FFBB en dictionnaires
    de manière compatible avec différentes versions de Pydantic.
    """

    if value is None:
        return None

    if isinstance(value, dict):
        return {
            key: to_dict(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [
            to_dict(item)
            for item in value
        ]

    if hasattr(value, "model_dump"):
        return to_dict(value.model_dump())

    if hasattr(value, "dict"):
        return to_dict(value.dict())

    return value


def get_value(data, *keys, default=None):
    """
    Cherche successivement plusieurs noms de champs.
    """

    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def extract_id(value):
    """
    Extrait un identifiant depuis :
    - un entier
    - une chaîne
    - un dictionnaire contenant id
    """

    if value is None:
        return None

    if isinstance(value, (int, str)):
        return value

    if isinstance(value, dict):
        return value.get("id")

    return getattr(value, "id", None)


# ============================================================
# DATE / HEURE
# ============================================================

def parse_ffbb_datetime(value):
    """
    Convertit date_rencontre FFBB en heure locale Europe/Paris.

    Cas 1 :
        date avec fuseau / UTC
        -> conversion vers Europe/Paris

    Cas 2 :
        date sans fuseau
        -> considérée comme heure locale FFBB

    L'objectif est de conserver l'heure réellement affichée
    par FFBB dans le calendrier.
    """

    if value is None:
        return None

    if isinstance(value, datetime):

        dt = value

    else:

        text = str(value).strip()

        if not text:
            return None

        # Support du suffixe Z
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(text)

        except ValueError:

            # Quelques formats de secours
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
            ]

            dt = None

            for fmt in formats:

                try:
                    dt = datetime.strptime(
                        text,
                        fmt,
                    )
                    break

                except ValueError:
                    pass

            if dt is None:
                raise RuntimeError(
                    f"Format de date FFBB inconnu : {value}"
                )

    # Date avec fuseau
    if dt.tzinfo is not None:

        return dt.astimezone(TIMEZONE).replace(
            tzinfo=None
        )

    # Date sans fuseau :
    # on la considère directement comme heure locale FFBB.
    return dt


# ============================================================
# API FFBB
# ============================================================

def create_client():

    print("Connexion à l'API FFBB...")

    # Les jetons sont récupérés automatiquement depuis
    # la configuration publique FFBB.
    tokens = TokenManager.get_tokens(
        use_cache=False
    )

    client = FFBBAPIClientV2.create(
        api_bearer_token=tokens.api_token,
        meilisearch_bearer_token=tokens.meilisearch_token,
    )

    print("Connexion API FFBB OK.")

    return client


def get_matches(client):

    print()
    print(
        f"Récupération de l'équipe FFBB : {TEAM_ID}"
    )

    # L'identifiant présent dans l'URL FFBB correspond
    # à l'engagement de l'équipe.
    engagement = client.get_engagement(
        TEAM_ID
    )

    engagement = to_dict(engagement)

    if not engagement:
        raise RuntimeError(
            f"Impossible de récupérer l'engagement FFBB {TEAM_ID}."
        )

    print(
        "Engagement FFBB récupéré."
    )

    poule_data = get_value(
        engagement,
        "idPoule",
        "id_poule",
    )

    poule_id = extract_id(
        poule_data
    )

    if not poule_id:

        raise RuntimeError(
            "Impossible de trouver l'identifiant de la poule "
            "dans l'engagement FFBB."
        )

    print(
        f"Poule FFBB : {poule_id}"
    )

    poule = client.get_poule(
        poule_id
    )

    poule = to_dict(poule)

    if not poule:

        raise RuntimeError(
            f"Impossible de récupérer la poule FFBB {poule_id}."
        )

    rencontres = get_value(
        poule,
        "rencontres",
        default=[],
    )

    if not rencontres:

        raise RuntimeError(
            "La poule FFBB ne contient aucune rencontre."
        )

    print(
        f"Rencontres dans la poule : {len(rencontres)}"
    )

    matches = []

    for rencontre in rencontres:

        if not isinstance(rencontre, dict):
            continue

        # ----------------------------------------------------
        # Équipe 1 / équipe 2
        # ----------------------------------------------------

        equipe1 = get_value(
            rencontre,
            "nomEquipe1",
            "nom_equipe1",
            default="",
        )

        equipe2 = get_value(
            rencontre,
            "nomEquipe2",
            "nom_equipe2",
            default="",
        )

        equipe1 = str(equipe1).strip()
        equipe2 = str(equipe2).strip()

        # ----------------------------------------------------
        # Identifier Châtillon
        # ----------------------------------------------------

        is_team1 = False
        is_team2 = False

        if equipe1:
            if (
                "châtillon" in equipe1.lower()
                or "chatillon" in equipe1.lower()
            ):
                is_team1 = True

        if equipe2:
            if (
                "châtillon" in equipe2.lower()
                or "chatillon" in equipe2.lower()
            ):
                is_team2 = True

        if not is_team1 and not is_team2:
            continue

        # ----------------------------------------------------
        # Journée
        # ----------------------------------------------------

        journee = get_value(
            rencontre,
            "numeroJournee",
            "numero_journee",
            default=None,
        )

        if journee is None:

            # Certains formats peuvent contenir
            # le numéro sous forme de texte.
            journee = get_value(
                rencontre,
                "journee",
                "journée",
                default=0,
            )

        try:
            journee = int(journee)

        except (TypeError, ValueError):
            journee = 0

        # ----------------------------------------------------
        # Date / heure
        # ----------------------------------------------------

        date_value = get_value(
            rencontre,
            "date_rencontre",
            "dateRencontre",
            default=None,
        )

        if not date_value:

            print(
                f"J{journee} ignorée : aucune date."
            )

            continue

        date_match = parse_ffbb_datetime(
            date_value
        )

        if date_match is None:

            print(
                f"J{journee} ignorée : date invalide."
            )

            continue

        # ----------------------------------------------------
        # Adversaire
        # ----------------------------------------------------

        if is_team1:

            opponent = equipe2
            domicile = True

        else:

            opponent = equipe1
            domicile = False

        if not opponent:

            print(
                f"J{journee} ignorée : adversaire absent."
            )

            continue

        # ----------------------------------------------------
        # Salle / commune
        # ----------------------------------------------------

        salle = get_value(
            rencontre,
            "salle",
            default={},
        )

        salle = to_dict(salle)

        location = ""

        if isinstance(salle, dict):

            salle_nom = get_value(
                salle,
                "libelle",
                "nom",
                default="",
            )

            commune = get_value(
                salle,
                "commune",
                default={},
            )

            commune = to_dict(commune)

            commune_nom = ""

            if isinstance(commune, dict):

                commune_nom = get_value(
                    commune,
                    "libelle",
                    "nom",
                    default="",
                )

            if salle_nom and commune_nom:

                location = (
                    f"{salle_nom}, {commune_nom}"
                )

            elif salle_nom:

                location = salle_nom

            elif commune_nom:

                location = commune_nom

        # Si aucun lieu n'est fourni
        if not location:

            location = (
                "Châtillon-en-Vendelais"
                if domicile
                else opponent
            )

        # ----------------------------------------------------
        # Ajout
        # ----------------------------------------------------

        matches.append(
            {
                "journee": journee,
                "date": date_match,
                "domicile": domicile,
                "opponent": opponent,
                "location": location,
                "equipe1": equipe1,
                "equipe2": equipe2,
            }
        )

    # --------------------------------------------------------
    # Suppression des doublons
    # --------------------------------------------------------

    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"].strftime(
                "%Y%m%dT%H%M%S"
            ),
            match["opponent"],
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    # --------------------------------------------------------
    # Tri
    # --------------------------------------------------------

    matches.sort(
        key=lambda match: (
            match["date"],
            match["journee"],
        )
    )

    return matches


# ============================================================
# ICS
# ============================================================

def escape_ics(value):

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generate_ics(matches):

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chatillon-en-Vendelais Basket//DM4//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Châtillon-en-Vendelais Basket 2 - DM4",
        "X-WR-TIMEZONE:Europe/Paris",
    ]

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

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

        date_str = start.strftime(
            "%Y%m%d"
        )

        opponent = match["opponent"]

        if match["domicile"]:

            summary = (
                f"{TEAM_NAME} - {opponent}"
            )

        else:

            summary = (
                f"{opponent} - {TEAM_NAME}"
            )

        uid = (
            f"chatillon-dm4-"
            f"j{match['journee']}-"
            f"{date_str}-"
            f"{uuid.uuid5(uuid.NAMESPACE_URL, summary + start_str)}"
            f"@github"
        )

        description = (
            f"{TEAM_NAME} - DM4 - "
            f"Journée {match['journee']}"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{timestamp}",
                f"DTSTART:{start_str}",
                f"DTEND:{end_str}",
                f"SUMMARY:{escape_ics(summary)}",
                f"LOCATION:{escape_ics(match['location'])}",
                f"DESCRIPTION:{escape_ics(description)}",
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

    print(
        "========================================"
    )
    print(
        "Calendrier Châtillon-en-Vendelais DM4"
    )
    print(
        "API FFBB"
    )
    print(
        "========================================"
    )

    client = create_client()

    matches = get_matches(
        client
    )

    print()
    print(
        f"Matchs trouvés : {len(matches)}"
    )
    print()

    if len(matches) < MIN_MATCHES:

        print(
            "ERREUR : trop peu de matchs trouvés."
        )

        print(
            f"Minimum attendu : {MIN_MATCHES}"
        )

        raise RuntimeError(
            f"Seulement {len(matches)} matchs trouvés."
        )

    print(
        "Matchs détectés :"
    )

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
            f"{match['opponent']} | "
            f"{match['location']}"
        )

    ics_content = generate_ics(
        matches
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        file.write(
            ics_content
        )

    print()
    print(
        f"Calendrier généré : {OUTPUT_FILE}"
    )

    print(
        f"Nombre d'événements : {len(matches)}"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
