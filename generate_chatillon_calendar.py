from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid
import json

from ffbb_api_client_v2 import FFBBAPIClientV2, TokenManager


# ============================================================
# CONFIGURATION
# ============================================================

TEAM_ID = 200000005342013

OUTPUT_FILE = "calendrier-chatillon.ics"

TEAM_NAME = "Châtillon-en-Vendelais Basket 2"

TIMEZONE = ZoneInfo("Europe/Paris")

# Sécurité :
# On refuse de générer un calendrier si trop peu de matchs
# sont récupérés.
MIN_MATCHES = 18


# ============================================================
# OUTILS
# ============================================================

def to_dict(value):
    """
    Convertit récursivement les objets retournés par l'API
    FFBB en dictionnaires Python.
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
        return to_dict(
            value.model_dump()
        )

    if hasattr(value, "dict"):
        return to_dict(
            value.dict()
        )

    # Certains modèles possèdent __dict__
    if hasattr(value, "__dict__"):
        return to_dict(
            vars(value)
        )

    return value


def get_value(data, *keys, default=None):
    """
    Recherche plusieurs noms de champs possibles.
    """

    if not isinstance(data, dict):
        return default

    for key in keys:

        if key in data and data[key] is not None:

            return data[key]

    return default


def extract_id(value):
    """
    Extrait un identifiant depuis différentes formes
    possibles retournées par l'API.
    """

    if value is None:
        return None

    if isinstance(value, (int, str)):
        return value

    if isinstance(value, dict):

        return get_value(
            value,
            "id",
            default=None,
        )

    if hasattr(value, "id"):

        return value.id

    return None


def unwrap_response(data):
    """
    Certaines méthodes du client peuvent retourner un objet
    enveloppant la ressource.

    Cette fonction essaie de retrouver automatiquement
    la ressource réelle.
    """

    if not isinstance(data, dict):
        return data

    # Cas classiques
    for key in (
        "data",
        "item",
        "result",
        "engagement",
        "organisme",
        "poule",
    ):

        value = data.get(key)

        if value is not None:

            return value

    return data


# ============================================================
# DATE / HEURE
# ============================================================

def parse_ffbb_datetime(value):
    """
    Convertit la date FFBB en heure locale Europe/Paris.

    Si l'API fournit un fuseau :
        conversion vers Europe/Paris.

    Si l'API ne fournit pas de fuseau :
        l'heure est conservée telle quelle.
    """

    if value is None:
        return None

    if isinstance(value, datetime):

        dt = value

    else:

        text = str(value).strip()

        if not text:
            return None

        # Format UTC avec Z
        if text.endswith("Z"):

            text = (
                text[:-1]
                + "+00:00"
            )

        try:

            dt = datetime.fromisoformat(
                text
            )

        except ValueError:

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

        return dt.astimezone(
            TIMEZONE
        ).replace(
            tzinfo=None
        )

    # Date sans fuseau :
    # on conserve directement l'heure fournie.
    return dt


# ============================================================
# CONNEXION API FFBB
# ============================================================

def create_client():

    print(
        "Connexion à l'API FFBB..."
    )

    tokens = TokenManager.get_tokens()

    client = FFBBAPIClientV2.create(
        api_bearer_token=tokens.api_token,
        meilisearch_bearer_token=tokens.meilisearch_token,
    )

    print(
        "Connexion API FFBB OK."
    )

    return client


# ============================================================
# RECUPERATION DES MATCHS
# ============================================================

def get_matches(client):

    print()
    print(
        f"Récupération de l'engagement FFBB : {TEAM_ID}"
    )

    # --------------------------------------------------------
    # 1. Récupération de l'engagement
    # --------------------------------------------------------

    raw_engagement = client.get_engagement(
        TEAM_ID
    )

    engagement = to_dict(
        raw_engagement
    )

    engagement = unwrap_response(
        engagement
    )

    if not engagement:

        raise RuntimeError(
            f"Impossible de récupérer l'engagement FFBB {TEAM_ID}."
        )

    print(
        "Engagement FFBB récupéré."
    )

    # --------------------------------------------------------
    # 2. Recherche de idPoule
    # --------------------------------------------------------

    id_poule_data = get_value(
        engagement,
        "idPoule",
        "id_poule",
        "poule",
        default=None,
    )

    poule_id = extract_id(
        id_poule_data
    )

    # Certains retours peuvent directement contenir
    # l'identifiant sous forme de chaîne.
    if poule_id is None:

        if isinstance(
            id_poule_data,
            (int, str),
        ):

            poule_id = id_poule_data

    # --------------------------------------------------------
    # 3. Si idPoule absent : affichage diagnostic
    # --------------------------------------------------------

    if not poule_id:

        print()
        print(
            "========== DIAGNOSTIC API FFBB =========="
        )

        try:

            print(
                json.dumps(
                    engagement,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

        except Exception:

            print(
                repr(engagement)
            )

        print(
            "=========================================="
        )
        print()

        raise RuntimeError(
            "Impossible de trouver l'identifiant de la poule "
            "dans l'engagement FFBB."
        )

    print(
        f"Poule FFBB : {poule_id}"
    )

    # --------------------------------------------------------
    # 4. Récupération de la poule
    # --------------------------------------------------------

    raw_poule = client.get_poule(
        int(poule_id)
    )

    poule = to_dict(
        raw_poule
    )

    poule = unwrap_response(
        poule
    )

    if not poule:

        raise RuntimeError(
            f"Impossible de récupérer la poule FFBB {poule_id}."
        )

    print(
        "Poule FFBB récupérée."
    )

    # --------------------------------------------------------
    # 5. Récupération des rencontres
    # --------------------------------------------------------

    rencontres = get_value(
        poule,
        "rencontres",
        default=None,
    )

    if rencontres is None:

        print()
        print(
            "Structure de la poule reçue :"
        )

        print(
            json.dumps(
                poule,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        raise RuntimeError(
            "Impossible de trouver les rencontres dans la poule FFBB."
        )

    print(
        f"Rencontres dans la poule : {len(rencontres)}"
    )

    # --------------------------------------------------------
    # 6. Filtrage des matchs de Châtillon
    # --------------------------------------------------------

    matches = []

    for rencontre_raw in rencontres:

        rencontre = to_dict(
            rencontre_raw
        )

        if not isinstance(
            rencontre,
            dict,
        ):
            continue

        # ----------------------------------------------------
        # Équipes
        # ----------------------------------------------------

        equipe1 = str(
            get_value(
                rencontre,
                "nomEquipe1",
                "nom_equipe1",
                default="",
            )
        ).strip()

        equipe2 = str(
            get_value(
                rencontre,
                "nomEquipe2",
                "nom_equipe2",
                default="",
            )
        ).strip()

        if not equipe1 or not equipe2:
            continue

        # ----------------------------------------------------
        # Engagements des équipes
        # ----------------------------------------------------

        engagement1 = get_value(
            rencontre,
            "idEngagementEquipe1",
            "id_engagement_equipe1",
            default=None,
        )

        engagement2 = get_value(
            rencontre,
            "idEngagementEquipe2",
            "id_engagement_equipe2",
            default=None,
        )

        engagement1_id = extract_id(
            engagement1
        )

        engagement2_id = extract_id(
            engagement2
        )

        is_team1 = (
            str(engagement1_id)
            == str(TEAM_ID)
        )

        is_team2 = (
            str(engagement2_id)
            == str(TEAM_ID)
        )

        # ----------------------------------------------------
        # Sécurité par le nom
        # ----------------------------------------------------

        if not is_team1 and not is_team2:

            nom1 = equipe1.lower()
            nom2 = equipe2.lower()

            if (
                "châtillon" in nom1
                or "chatillon" in nom1
            ):

                is_team1 = True

            elif (
                "châtillon" in nom2
                or "chatillon" in nom2
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

            journee = get_value(
                rencontre,
                "journee",
                "journée",
                default=0,
            )

        try:

            journee = int(
                journee
            )

        except (
            TypeError,
            ValueError,
        ):

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

        try:

            date_match = parse_ffbb_datetime(
                date_value
            )

        except Exception as error:

            print(
                f"J{journee} ignorée : "
                f"date invalide ({error})"
            )

            continue

        if date_match is None:
            continue

        # ----------------------------------------------------
        # Domicile / extérieur
        # ----------------------------------------------------

        if is_team1:

            opponent = equipe2
            domicile = True

        else:

            opponent = equipe1
            domicile = False

        # ----------------------------------------------------
        # Lieu
        # ----------------------------------------------------

        location = ""

        salle = to_dict(
            get_value(
                rencontre,
                "salle",
                default=None,
            )
        )

        if isinstance(
            salle,
            dict,
        ):

            salle_nom = get_value(
                salle,
                "libelle",
                "nom",
                default="",
            )

            commune = to_dict(
                get_value(
                    salle,
                    "commune",
                    default=None,
                )
            )

            commune_nom = ""

            if isinstance(
                commune,
                dict,
            ):

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

        if not location:

            location = (
                "Châtillon-en-Vendelais"
                if domicile
                else opponent
            )

        # ----------------------------------------------------
        # Match
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
                "%Y-%m-%d %H:%M"
            ),
            match["opponent"],
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    # --------------------------------------------------------
    # Tri chronologique
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

        # UID stable :
        # le même match conserve toujours le même identifiant.
        unique_string = (
            f"chatillon-dm4-"
            f"j{match['journee']}-"
            f"{date_str}-"
            f"{opponent}"
        )

        uid = (
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    unique_string,
                )
            )
            + "@chatillon-dm4"
        )

        description = (
            f"{TEAM_NAME} - "
            f"DM4 - Journée {match['journee']}"
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

    return (
        "\r\n".join(lines)
        + "\r\n"
    )


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

    # --------------------------------------------------------
    # Sécurité
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Affichage
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Génération ICS
    # --------------------------------------------------------

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
