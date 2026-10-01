import requests
from datetime import datetime, timedelta
import re
import time


URL = "https://competitions.ffbb.com/ligues/bre/comites/0035/clubs/bre0035135/equipes/200000005342013"
OUTPUT_FILE = "calendrier-chatillon.ics"

# Relais permettant de récupérer la page FFBB malgré le 403
READER_URL = "https://r.jina.ai/" + URL


MONTHS = {
    "janv.": 1,
    "janvier": 1,
    "févr.": 2,
    "février": 2,
    "mars": 3,
    "avr.": 4,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil.": 7,
    "juillet": 7,
    "août": 8,
    "sept.": 9,
    "septembre": 9,
    "oct.": 10,
    "octobre": 10,
    "nov.": 11,
    "novembre": 11,
    "déc.": 12,
    "décembre": 12,
}


def get_page_text():
    """
    Récupère le contenu de la page FFBB via le lecteur Jina AI.

    Le site FFBB renvoie actuellement HTTP 403 aux runners GitHub.
    Le relais permet de récupérer le contenu public de la page.
    """

    print("Récupération du calendrier FFBB...")
    print(f"URL : {URL}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/plain,text/html,*/*",
    }

    for attempt in range(3):

        try:

            response = requests.get(
                READER_URL,
                headers=headers,
                timeout=60,
            )

            print(
                f"Réponse du relais : HTTP {response.status_code}"
            )

            if response.status_code == 200:

                text = response.text

                print(
                    f"Taille de la page : {len(text)} caractères"
                )

                if len(text) < 500:

                    print(
                        "Réponse trop courte, nouvelle tentative..."
                    )

                else:

                    return text

        except requests.RequestException as error:

            print(
                f"Erreur de connexion : {error}"
            )

        if attempt < 2:

            time.sleep(5)

    raise RuntimeError(
        "Impossible de récupérer la page FFBB après 3 tentatives."
    )


def parse_date_and_time(line):
    """
    Recherche une date et une heure dans une ligne.

    Exemples :
        27 sept. 20h15
        4 oct. 10h30
    """

    match = re.search(
        r"(\d{1,2})\s+([A-Za-zÀ-ÿ.]+)\s+(\d{1,2})h(\d{2})",
        line,
        re.IGNORECASE,
    )

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2).lower()
    hour = int(match.group(3))
    minute = int(match.group(4))

    month = MONTHS.get(month_name)

    if month is None:
        return None

    # Saison 2026-2027
    year = 2026 if month >= 9 else 2027

    return datetime(
        year,
        month,
        day,
        hour,
        minute,
    )


def find_matches(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    matches = []

    for i, line in enumerate(lines):

        journee_match = re.fullmatch(
            r"J(\d+)",
            line,
            re.IGNORECASE,
        )

        if not journee_match:
            continue

        journee = int(journee_match.group(1))

        date_value = None
        domicile = None
        opponent = None

        for j in range(
            i + 1,
            min(i + 25, len(lines)),
        ):

            current = lines[j]

            # Nouvelle journée
            if re.fullmatch(
                r"J(\d+)",
                current,
                re.IGNORECASE,
            ):
                break

            # Date + heure
            if date_value is None:

                parsed = parse_date_and_time(current)

                if parsed:
                    date_value = parsed
                    continue

            # Domicile / extérieur
            if current.lower() == "domicile":

                domicile = True
                continue

            if current.lower() == "extérieur":

                domicile = False
                continue

            # Adversaire
            if (
                date_value is not None
                and domicile is not None
                and opponent is None
            ):

                ignored = {
                    "calendrier",
                    "résultats",
                    "classement",
                    "domicile",
                    "extérieur",
                    "date",
                }

                if current.lower() in ignored:
                    continue

                if re.fullmatch(
                    r"\d+",
                    current,
                ):
                    continue

                if re.fullmatch(
                    r"\d{1,2}h\d{2}",
                    current,
                    re.IGNORECASE,
                ):
                    continue

                # Certains éléments FFBB accolent un score
                # à l'adversaire : "ROMAGNE BC00"
                opponent = re.sub(
                    r"\d+$",
                    "",
                    current,
                ).strip()

                if opponent:
                    break

        if (
            date_value
            and domicile is not None
            and opponent
        ):

            matches.append(
                {
                    "journee": journee,
                    "date": date_value,
                    "domicile": domicile,
                    "opponent": opponent,
                }
            )

    # Suppression des doublons
    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"].strftime("%Y-%m-%d"),
            match["date"].strftime("%H:%M"),
            match["opponent"],
        )

        unique[key] = match

    matches = list(unique.values())

    matches.sort(
        key=lambda x: (
            x["date"],
            x["journee"],
        )
    )

    return matches


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
    ]

    timestamp = datetime.utcnow().strftime(
        "%Y%m%dT%H%M%SZ"
    )

    for match in matches:

        start = match["date"]

        date_str = start.strftime("%Y%m%d")

        # Heure locale flottante.
        # Aucune conversion de fuseau horaire.
        start_str = start.strftime(
            "%Y%m%dT%H%M%S"
        )

        end = start + timedelta(hours=2)

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

        opponent = match["opponent"]

        if match["domicile"]:

            summary = (
                "Châtillon-en-Vendelais Basket 2 - "
                + opponent
            )

            location = "Châtillon-en-Vendelais"

        else:

            summary = (
                opponent
                + " - Châtillon-en-Vendelais Basket 2"
            )

            location = opponent

        uid = (
            f"chatillon-dm4-j"
            f"{match['journee']}-"
            f"{date_str}@github"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{timestamp}",
                f"DTSTART:{start_str}",
                f"DTEND:{end_str}",
                f"SUMMARY:{escape_ics(summary)}",
                f"LOCATION:{escape_ics(location)}",
                (
                    "DESCRIPTION:"
                    "Châtillon-en-Vendelais Basket 2 - "
                    f"DM4 - Journée {match['journee']}"
                ),
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    print("========================================")
    print("Calendrier Châtillon-en-Vendelais DM4")
    print("========================================")

    text = get_page_text()

    matches = find_matches(text)

    print()
    print(f"Matchs trouvés : {len(matches)}")
    print()

    if len(matches) < 18:

        print(
            "ERREUR : moins de 18 matchs trouvés."
        )

        print(
            "Le calendrier FFBB a peut-être changé "
            "ou le relais n'a pas récupéré la page."
        )

        raise RuntimeError(
            f"Seulement {len(matches)} matchs trouvés."
        )

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

    ics_content = generate_ics(matches)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        file.write(ics_content)

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
