from datetime import datetime, timedelta, timezone
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

# Sécurité :
# On refuse de générer un calendrier si FFBB ne renvoie
# pas au minimum 18 matchs.
MIN_MATCHES = 18


# ============================================================
# OUTILS
# ============================================================

def get_object_value(obj, *names, default=None):
    """
    Récupère proprement un attribut sur un objet FFBB.

    La v1.4.0 utilise des modèles typés.
    On privilégie donc getattr() plutôt qu'une conversion
    récursive en dictionnaire.
    """

    if obj is None:
        return default

    for name in names:

        if hasattr(obj, name):

            value = getattr(obj, name)

            if value is not None:
                return value

    return default


def get_nested_id(obj):
    """
    Récupère l'identifiant d'un objet FFBB ou d'un identifiant
    qui peut être retourné directement sous forme de chaîne.
    """

    if obj is None:
        return None

    # Identifiant directement fourni
    if isinstance(obj, (int, str)):
        return obj

    # Objet FFBB avec attribut id
    value = getattr(
        obj,
        "id",
        None,
    )

    if value is not None:
        return value

    # Certains objets peuvent avoir idEngagement / idPoule
    for name in (
        "idEngagement",
        "idPoule",
        "idEquipe",
    ):

        value = getattr(
            obj,
            name,
            None,
        )

        if value is not None:

            if isinstance(
                value,
                (int, str),
            ):
                return value

            nested_id = getattr(
                value,
                "id",
                None,
            )

            if nested_id is not None:
                return nested_id

    return None


def parse_datetime(value):
    """
    Transforme une date FFBB en datetime local.

    Si FFBB fournit une date avec fuseau :
    conversion vers Europe/Paris.

    Si FFBB fournit une date sans fuseau :
    l'heure est conservée telle quelle.

    Cela permet notamment de conserver :
        20h15 -> 20h15
        10h30 -> 10h30
    """

    if value is None:
        return None

    if isinstance(value, datetime):

        dt = value

    else:

        text = str(value).strip()

        if not text:
            return None

        # FFBB peut fournir une date ISO terminée par Z
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
                    continue

            if dt is None:

                raise RuntimeError(
                    f"Date FFBB impossible à lire : {value}"
                )

    # Si un fuseau est fourni par FFBB,
    # on convertit vers Paris.
    if dt.tzinfo is not None:

        return dt.astimezone(
            TIMEZONE
        ).replace(
            tzinfo=None
        )

    # Si aucune information de fuseau n'est fournie,
    # on conserve exactement l'heure FFBB.
    return dt


# ============================================================
# CLIENT FFBB
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
# ENGAGEMENT
# ============================================================

def get_engagement(client):

    print()
    print(
        f"Récupération de l'équipe FFBB : {TEAM_ID}"
    )

    engagement = client.get_engagement(
        TEAM_ID
    )

    if engagement is None:

        raise RuntimeError(
            f"Impossible de récupérer "
            f"l'engagement FFBB {TEAM_ID}."
        )

    print(
        "Engagement FFBB récupéré."
    )

    return engagement


# ============================================================
# POULE
# ============================================================

def get_poule(client, engagement):

    # --------------------------------------------------------
    # idPoule
    # --------------------------------------------------------

    id_poule = get_object_value(
        engagement,
        "idPoule",
        "id_poule",
    )

    poule_id = get_nested_id(
        id_poule
    )

    print()
    print(
        "Recherche de la poule FFBB..."
    )

    print(
        f"idPoule brut : {id_poule}"
    )

    print(
        f"idPoule utilisé : {poule_id}"
    )

    if poule_id is None:

        raise RuntimeError(
            "Impossible de récupérer idPoule "
            "depuis l'engagement FFBB."
        )

    poule = client.get_poule(
        int(poule_id)
    )

    if poule is None:

        raise RuntimeError(
            f"Impossible de récupérer "
            f"la poule FFBB {poule_id}."
        )

    print(
        "Poule FFBB récupérée."
    )

    return poule


# ============================================================
# RENCONTRES
# ============================================================

def get_rencontres(poule):

    rencontres = get_object_value(
        poule,
        "rencontres",
        default=None,
    )

    if rencontres is None:

        raise RuntimeError(
            "La poule FFBB ne contient pas "
            "de liste de rencontres."
        )

    print(
        f"Rencontres récupérées dans la poule : "
        f"{len(rencontres)}"
    )

    return rencontres


# ============================================================
# MATCHS DE CHÂTILLON
# ============================================================

def extract_matches(rencontres):

    matches = []

    print()
    print(
        "Analyse des rencontres..."
    )

    for rencontre in rencontres:

        # ----------------------------------------------------
        # Équipes
        # ----------------------------------------------------

        equipe1 = get_object_value(
            rencontre,
            "nomEquipe1",
            default="",
        )

        equipe2 = get_object_value(
            rencontre,
            "nomEquipe2",
            default="",
        )

        equipe1 = str(
            equipe1 or ""
        ).strip()

        equipe2 = str(
            equipe2 or ""
        ).strip()

        if not equipe1 or not equipe2:
            continue

        # ----------------------------------------------------
        # Engagements des équipes
        # ----------------------------------------------------

        engagement1 = get_object_value(
            rencontre,
            "idEngagementEquipe1",
            default=None,
        )

        engagement2 = get_object_value(
            rencontre,
            "idEngagementEquipe2",
            default=None,
        )

        engagement1_id = get_nested_id(
            engagement1
        )

        engagement2_id = get_nested_id(
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
        # Sécurité supplémentaire avec le nom
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

        journee = get_object_value(
            rencontre,
            "numeroJournee",
            "numero_journee",
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
        # Date du match
        # ----------------------------------------------------

        date_raw = get_object_value(
            rencontre,
            "date_rencontre",
            "dateRencontre",
            default=None,
        )

        if date_raw is None:

            print(
                f"J{journee} ignorée : "
                "date absente."
            )

            continue

        try:

            date_match = parse_datetime(
                date_raw
            )

        except Exception as error:

            print(
                f"J{journee} ignorée : "
                f"date invalide : {error}"
            )

            continue

        if date_match is None:
            continue

        # ----------------------------------------------------
        # Adversaire / domicile
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

        location = get_object_value(
            rencontre,
            "lieu",
            "nomSalle",
            "salle",
            default=None,
        )

        if location is None:

            location = (
                "Châtillon-en-Vendelais"
                if domicile
                else opponent
            )

        else:

            # Si salle est un objet FFBB
            salle_nom = get_object_value(
                location,
                "nom",
                "libelle",
                default=None,
            )

            if salle_nom:

                location = salle_nom

            else:

                location = str(
                    location
                )

        # ----------------------------------------------------
        # Match
        # ----------------------------------------------------

        match = {
            "journee": journee,
            "date": date_match,
            "domicile": domicile,
            "opponent": opponent,
            "location": location,
        }

        matches.append(
            match
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
        .replace(
            "\\",
            "\\\\",
        )
        .replace(
            ";",
            "\\;",
        )
        .replace(
            ",",
            "\\,",
        )
        .replace(
            "\n",
            "\\n",
        )
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

    # DTSTAMP = moment de génération du calendrier.
    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    for match in matches:

        start = match["date"]

        # Durée de 2 heures
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

        description = (
            f"{TEAM_NAME} - "
            f"DM4 - Journée {match['journee']}"
        )

        # UID stable pour éviter la création
        # de doublons dans les calendriers abonnés.
        uid_source = (
            f"chatillon-dm4|"
            f"J{match['journee']}|"
            f"{date_str}|"
            f"{opponent}"
        )

        uid = (
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    uid_source,
                )
            )
            + "@chatillon-dm4"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{timestamp}",

                # IMPORTANT :
                # Heure locale flottante.
                # Pas de Z.
                # Pas de conversion UTC.
                # Pas de TZID.
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
        "API FFBB - ffbb-api-client-v2 1.4.0"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # Connexion
    # --------------------------------------------------------

    client = create_client()

    # --------------------------------------------------------
    # Engagement
    # --------------------------------------------------------

    engagement = get_engagement(
        client
    )

    # --------------------------------------------------------
    # Poule
    # --------------------------------------------------------

    poule = get_poule(
        client,
        engagement,
    )

    # --------------------------------------------------------
    # Rencontres
    # --------------------------------------------------------

    rencontres = get_rencontres(
        poule
    )

    # --------------------------------------------------------
    # Matchs Châtillon
    # --------------------------------------------------------

    matches = extract_matches(
        rencontres
    )

    print()
    print(
        f"Matchs Châtillon trouvés : "
        f"{len(matches)}"
    )

    # --------------------------------------------------------
    # Sécurité
    # --------------------------------------------------------

    if len(matches) < MIN_MATCHES:

        print()
        print(
            "ERREUR : trop peu de matchs trouvés."
        )

        print(
            f"Minimum attendu : {MIN_MATCHES}"
        )

        print(
            "Le calendrier ICS ne sera PAS généré."
        )

        raise RuntimeError(
            f"Seulement {len(matches)} matchs trouvés."
        )

    # --------------------------------------------------------
    # Affichage des matchs
    # --------------------------------------------------------

    print()
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
            f"{match['opponent']}"
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
