import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

BASE_URL = "https://api.ffbb.com"
CLUB_CODE = "BRE0035110"
TEAM_KEYWORDS = ["NM1", "NATIONALE MASCULINE 1"]
SEASON_KEYWORDS = ["2026-2027", "2026 / 2027", "2026–2027"]

TZ = ZoneInfo("Europe/Paris")


def api_get(path, params=None, token=None):
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(
        BASE_URL + path,
        params=params,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()["data"]


def get_token():
    response = requests.get(
        f"{BASE_URL}/items/configuration",
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()["data"]

    if not data.get("key_dh"):
        raise RuntimeError("Impossible de récupérer le token FFBB.")

    return data["key_dh"]


def get_club(token):
    params = [
        ("filter[code][_eq]", CLUB_CODE),
        ("fields[]", "id"),
        ("fields[]", "nom"),
        ("fields[]", "code"),
    ]

    clubs = api_get(
        "/items/ffbbserver_organismes",
        params=params,
        token=token,
    )

    if not clubs:
        raise RuntimeError(
            f"Club introuvable avec le code {CLUB_CODE}"
        )

    return clubs[0]


def get_engagements(token, club_id):
    params = [
        ("filter[idOrganisme][_eq]", club_id),
        ("limit", "100"),
        ("fields[]", "id"),
        ("fields[]", "nom"),
        ("fields[]", "idPoule"),
        ("fields[]", "idCompetition"),
        ("fields[]", "idCompetition.nom"),
        ("fields[]", "idCompetition.code"),
        ("fields[]", "idCompetition.categorie.code"),
        ("fields[]", "idCompetition.saison.id"),
        ("fields[]", "idCompetition.saison.nom"),
    ]

    return api_get(
        "/items/ffbbserver_engagements",
        params=params,
        token=token,
    )


def find_nm1_engagement(engagements):
    candidates = []

    for engagement in engagements:

        competition = engagement.get("idCompetition") or {}

        competition_name = str(
            competition.get("nom", "")
        ).upper()

        competition_code = str(
            competition.get("code", "")
        ).upper()

        category = competition.get("categorie") or {}

        category_code = str(
            category.get("code", "")
        ).upper()

        season = competition.get("saison") or {}

        season_name = str(
            season.get("nom", "")
        ).upper()

        is_nm1 = (
            "NM1" in competition_name
            or "NATIONALE MASCULINE 1" in competition_name
            or competition_code == "NM1"
            or category_code == "NM1"
        )

        if not is_nm1:
            continue

        is_current_season = (
            "2026" in season_name
            and "2027" in season_name
        )

        if is_current_season:
            candidates.insert(0, engagement)
        else:
            candidates.append(engagement)

    if not candidates:
        raise RuntimeError(
            "Impossible de trouver l'engagement NM1 2026-2027."
        )

    return candidates[0]


def get_poule(token, poule_id):
    fields = [
        "id",
        "nom",
        "rencontres.id",
        "rencontres.numero",
        "rencontres.numeroJournee",
        "rencontres.nomEquipe1",
        "rencontres.nomEquipe2",
        "rencontres.date_rencontre",
        "rencontres.resultatEquipe1",
        "rencontres.resultatEquipe2",
        "rencontres.salle.libelle",
        "rencontres.salle.commune.libelle",
        "rencontres.idEngagementEquipe1.id",
        "rencontres.idEngagementEquipe1.nom",
        "rencontres.idEngagementEquipe1.idOrganisme.id",
        "rencontres.idEngagementEquipe1.idOrganisme.code",
        "rencontres.idEngagementEquipe2.id",
        "rencontres.idEngagementEquipe2.nom",
        "rencontres.idEngagementEquipe2.idOrganisme.id",
        "rencontres.idEngagementEquipe2.idOrganisme.code",
    ]

    params = [
        ("fields[]", field)
        for field in fields
    ]

    params.append(
        ("deep[rencontres][_limit]", "1000")
    )

    params.append(
        ("deep[rencontres][_sort]", "date_rencontre")
    )

    return api_get(
        f"/items/ffbbserver_poules/{poule_id}",
        params=params,
        token=token,
    )


def parse_date(value):
    if not value:
        return None

    value = str(value)

    # ISO FFBB
    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)

        return dt.astimezone(TZ)

    except ValueError:
        pass

    # Quelques formats de secours
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            ).replace(tzinfo=TZ)

        except ValueError:
            continue

    return None


def escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def make_ics(matches):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Aurore Vitré Basket//NM1//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Aurore Vitré Basket - NM1",
        "X-WR-TIMEZONE:Europe/Paris",
    ]

    now = datetime.now(
        tz=TZ
    ).strftime("%Y%m%dT%H%M%S")

    for match in matches:

        date = parse_date(
            match.get("date_rencontre")
        )

        if not date:
            print(
                "Match ignoré : date inconnue",
                match
            )
            continue

        team1 = str(
            match.get("nomEquipe1", "")
        ).strip()

        team2 = str(
            match.get("nomEquipe2", "")
        ).strip()

        if not team1 or not team2:
            continue

        is_vitre_home = (
            CLUB_CODE in str(
                (match.get("idEngagementEquipe1") or {})
                .get("idOrganisme", {})
                .get("code", "")
            )
        )

        if is_vitre_home:
            opponent = team2
            summary = f"Aurore Vitré NM1 - {opponent}"
        else:
            opponent = team1
            summary = f"{opponent} - Aurore Vitré NM1"

        location = ""

        salle = match.get("salle") or {}

        if salle.get("libelle"):
            location = str(
                salle["libelle"]
            )

        commune = (
            salle.get("commune") or {}
        )

        if commune.get("libelle"):
            if location:
                location += ", "

            location += str(
                commune["libelle"]
            )

        end = date + timedelta(hours=2)

        start_str = date.strftime(
            "%Y%m%dT%H%M%S"
        )

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

        journee = (
            match.get("numeroJournee")
            or match.get("numero")
            or ""
        )

        description = (
            f"NM1 2026-2027"
            f"\\nJournée {journee}"
            f"\\n{team1} - {team2}"
        )

        uid = (
            f"aurore-vitre-nm1-"
            f"{match.get('id', start_str)}"
            f"@aurore-vitre"
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART;TZID=Europe/Paris:{start_str}",
            f"DTEND;TZID=Europe/Paris:{end_str}",
            f"SUMMARY:{escape(summary)}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{escape(location)}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    print("Récupération du token FFBB...")
    token = get_token()

    print("Recherche du club VITRE AURORE...")
    club = get_club(token)

    print(
        f"Club trouvé : {club['nom']} "
        f"({club['code']})"
    )

    print("Recherche de l'engagement NM1...")
    engagements = get_engagements(
        token,
        club["id"]
    )

    print(
        f"{len(engagements)} engagement(s) trouvé(s)"
    )

    engagement = find_nm1_engagement(
        engagements
    )

    print(
        "Engagement sélectionné :",
        engagement.get("nom")
    )

    poule = engagement.get("idPoule")

    if isinstance(poule, dict):
        poule_id = poule.get("id")
    else:
        poule_id = poule

    if not poule_id:
        raise RuntimeError(
            "Impossible de trouver la poule NM1."
        )

    print(
        f"Récupération de la poule {poule_id}..."
    )

    poule_data = get_poule(
        token,
        poule_id
    )

    rencontres = (
        poule_data.get("rencontres")
        or []
    )

    # On garde uniquement les matchs de Vitré.
    matches = []

    for match in rencontres:

        e1 = match.get(
            "idEngagementEquipe1"
        ) or {}

        e2 = match.get(
            "idEngagementEquipe2"
        ) or {}

        code1 = (
            (e1.get("idOrganisme") or {})
            .get("code", "")
        )

        code2 = (
            (e2.get("idOrganisme") or {})
            .get("code", "")
        )

        if code1 == CLUB_CODE or code2 == CLUB_CODE:
            matches.append(match)

    matches.sort(
        key=lambda m: (
            parse_date(
                m.get("date_rencontre")
            )
            or datetime.max.replace(
                tzinfo=TZ
            )
        )
    )

    if not matches:
        raise RuntimeError(
            "Aucun match de l'Aurore Vitré trouvé."
        )

    print(
        f"{len(matches)} match(s) NM1 trouvé(s)."
    )

    ics = make_ics(matches)

    with open(
        "calendrier.ics",
        "w",
        encoding="utf-8"
    ) as file:
        file.write(ics)

    print(
        "calendrier.ics généré avec succès."
    )


if __name__ == "__main__":
    main()
