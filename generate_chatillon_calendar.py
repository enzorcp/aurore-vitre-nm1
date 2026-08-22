import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


URL = (
    "https://competitions.ffbb.com/ligues/bre/comites/0035/"
    "clubs/bre0035135/equipes/200000005342013"
)

TEAM = "CHÂTILLON-EN-VENDELAIS BASKET - 2"

OUTPUT = "calendrier-chatillon.ics"

TIMEZONE = ZoneInfo("Europe/Paris")

# Saison 2026-2027
SEASON_START_YEAR = 2026


MONTHS = {
    "janv": 1,
    "jan": 1,
    "févr": 2,
    "fevr": 2,
    "mars": 3,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7,
    "août": 8,
    "aout": 8,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "déc": 12,
    "dec": 12,
}


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def escape_ics(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def get_page():

    print("Récupération de la page FFBB...")

    response = requests.get(
        URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/131 Safari/537.36"
            )
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.text


def extract_matches(html):

    soup = BeautifulSoup(html, "html.parser")

    matches = []

    # Recherche des éléments contenant J1, J2, etc.
    journey_elements = soup.find_all(
        string=re.compile(r"^\s*J\d+\s*$")
    )

    print(
        f"Journées détectées dans la page : "
        f"{len(journey_elements)}"
    )

    for journey_element in journey_elements:

        journey_text = clean(
            journey_element
        )

        match_journey = re.search(
            r"J(\d+)",
            journey_text
        )

        if not match_journey:
            continue

        journee = int(
            match_journey.group(1)
        )

        # On remonte progressivement dans le DOM
        # jusqu'à trouver le bloc complet du match.
        container = journey_element.parent

        match_container = None

        for _ in range(10):

            if container is None:
                break

            text = clean(
                container.get_text(" ", strip=True)
            )

            has_location = (
                "Domicile" in text
                or "Extérieur" in text
            )

            # Le bloc doit contenir le statut
            # et suffisamment de texte.
            if has_location and len(text) > 20:

                match_container = container
                break

            container = container.parent

        if match_container is None:

            print(
                f"⚠ J{journee} : bloc non trouvé"
            )

            continue

        text = clean(
            match_container.get_text(
                " ",
                strip=True
            )
        )

        # Détermine domicile / extérieur.
        if "Domicile" in text:

            domicile = True

        elif "Extérieur" in text:

            domicile = False

        else:

            print(
                f"⚠ J{journee} : domicile/extérieur non trouvé"
            )

            continue

        # Recherche des liens d'équipes dans le bloc.
        links = match_container.find_all("a")

        teams = []

        for link in links:

            name = clean(
                link.get_text(
                    " ",
                    strip=True
                )
            )

            if not name:
                continue

            # On élimine les éléments qui ne sont
            # manifestement pas des noms d'équipe.
            if (
                len(name) >= 3
                and name not in teams
            ):
                teams.append(name)

        # Le premier nom qui n'est pas notre équipe
        # est normalement l'adversaire.
        opponent = None

        for team in teams:

            if (
                TEAM.lower()
                not in team.lower()
                and "CHÂTILLON" not in team.upper()
            ):

                # Évite les liens génériques.
                if not any(
                    word in team.lower()
                    for word in [
                        "classement",
                        "calendrier",
                        "compétition",
                        "fédération",
                    ]
                ):

                    opponent = team
                    break

        # Si aucun adversaire n'est trouvé dans les liens,
        # on cherche les noms de clubs dans le texte.
        if opponent is None:

            known_team_patterns = [
                r"NOYAL-SUR-VILAINE AS - 2",
                r"VITRE AURORE - 4",
                r"BALAZE JA - 2",
                r"ARGENTRE \(LES JEUNES\) - 3",
                r"LIFFRE US - 5",
                r"ERBREE AS BASKET - 2",
                r"JANZE \(VOLONTAIRES\) - 3",
                r"SERVON CS",
                r"CESSON OC BASKET - 3",
                r"POCÉ LES BOIS BASKET - 2",
            ]

            for pattern in known_team_patterns:

                found = re.search(
                    pattern,
                    text,
                    re.IGNORECASE
                )

                if found:

                    opponent = clean(
                        found.group(0)
                    )

                    break

        if opponent is None:

            print(
                f"⚠ J{journee} : adversaire non trouvé"
            )

            continue

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        date = None

        # Priorité aux attributs datetime des balises <time>.
        time_elements = match_container.find_all(
            attrs={"datetime": True}
        )

        for element in time_elements:

            value = element.get(
                "datetime"
            )

            if not value:
                continue

            try:

                parsed = value.replace(
                    "Z",
                    "+00:00"
                )

                date = datetime.fromisoformat(
                    parsed
                )

                if date.tzinfo is None:
                    date = date.replace(
                        tzinfo=TIMEZONE
                    )
                else:
                    date = date.astimezone(
                        TIMEZONE
                    )

                break

            except Exception:
                pass

        # Si aucune date datetime n'est disponible,
        # on cherche une date du type :
        # 27 sept. 02h00
        if date is None:

            date_pattern = re.compile(
                r"(\d{1,2})\s+"
                r"(janv?\.?|févr?\.?|mars|avr?\.?|mai|"
                r"juin|juil?\.?|août|aout|sept?\.?|"
                r"oct\.?|nov\.?|déc\.?|dec\.?)"
                r"(?:\s+(\d{1,2})h(\d{2}))?",
                re.IGNORECASE
            )

            date_match = date_pattern.search(
                text
            )

            if date_match:

                day = int(
                    date_match.group(1)
                )

                month_text = (
                    date_match.group(2)
                    .lower()
                    .replace(".", "")
                )

                month = MONTHS.get(
                    month_text
                )

                if month:

                    hour = 0
                    minute = 0

                    if date_match.group(3):

                        hour = int(
                            date_match.group(3)
                        )

                        minute = int(
                            date_match.group(4)
                        )

                    # Septembre à décembre = début de saison.
                    # Janvier à avril = année suivante.
                    if month >= 9:
                        year = SEASON_START_YEAR
                    else:
                        year = SEASON_START_YEAR + 1

                    date = datetime(
                        year,
                        month,
                        day,
                        hour,
                        minute,
                        tzinfo=TIMEZONE,
                    )

        if date is None:

            print(
                f"⚠ J{journee} : date non trouvée"
            )

            continue

        print()
        print(
            f"✓ J{journee}"
        )
        print(
            f"  Date : {date}"
        )
        print(
            f"  {'DOMICILE' if domicile else 'EXTÉRIEUR'}"
        )
        print(
            f"  Adversaire : {opponent}"
        )

        matches.append(
            {
                "journee": journee,
                "date": date,
                "domicile": domicile,
                "opponent": opponent,
            }
        )

    return matches


def generate_ics(matches):

    now = datetime.now(
        TIMEZONE
    ).strftime(
        "%Y%m%dT%H%M%S"
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chatillon-en-Vendelais Basket//DM4//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Châtillon-en-Vendelais Basket 2 - DM4",
        "X-WR-TIMEZONE:Europe/Paris",
    ]

    for match in sorted(
        matches,
        key=lambda x: x["date"]
    ):

        start = match["date"]

        # Si la FFBB ne donne pas encore d'heure,
        # l'événement reste à 00h00.
        # Il sera automatiquement corrigé lorsqu'une
        # heure sera publiée.
        end = start.replace(
            hour=(start.hour + 2) % 24
        )

        start_str = start.strftime(
            "%Y%m%dT%H%M%S"
        )

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

        opponent = match[
            "opponent"
        ]

        if match["domicile"]:

            summary = (
                "Châtillon-en-Vendelais Basket 2 "
                f"- {opponent}"
            )

            location = (
                "Châtillon-en-Vendelais"
            )

        else:

            summary = (
                f"{opponent} - "
                "Châtillon-en-Vendelais Basket 2"
            )

            location = opponent

        uid = (
            f"chatillon-dm4-"
            f"j{match['journee']}-"
            f"{start.strftime('%Y%m%d')}"
            "@github"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now}",
                f"DTSTART;TZID=Europe/Paris:{start_str}",
                f"DTEND;TZID=Europe/Paris:{end_str}",
                f"SUMMARY:{escape_ics(summary)}",
                f"LOCATION:{escape_ics(location)}",
                (
                    "DESCRIPTION:"
                    "DM4 - Départementale Masculine "
                    f"Seniors - Journée {match['journee']}"
                ),
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


def main():

    html = get_page()

    matches = extract_matches(
        html
    )

    print()
    print(
        "================================"
    )
    print(
        f"MATCHS TROUVÉS : {len(matches)}"
    )
    print(
        "================================"
    )

    # La FFBB affiche actuellement 20 matchs
    # sur la page : J7 et J18 sont des journées sans match.
    if len(matches) < 18:

        raise RuntimeError(
            "Trop peu de matchs récupérés. "
            "Le fichier ICS ne sera pas publié."
        )

    ics = generate_ics(
        matches
    )

    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            ics
        )

    print()
    print(
        f"✓ {OUTPUT} généré avec succès."
    )


if __name__ == "__main__":
    main()
