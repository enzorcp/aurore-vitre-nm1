import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re


URL = (
    "https://competitions.ffbb.com/ligues/bre/comites/0035/"
    "clubs/bre0035135/equipes/200000005342013"
)

OUTPUT = "calendrier-chatillon.ics"

TZ = ZoneInfo("Europe/Paris")

MONTHS = {
    "janv.": 1,
    "janv": 1,
    "févr.": 2,
    "févr": 2,
    "mars": 3,
    "avr.": 4,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juil.": 7,
    "juil": 7,
    "août": 8,
    "aout": 8,
    "sept.": 9,
    "sept": 9,
    "oct.": 10,
    "oct": 10,
    "nov.": 11,
    "nov": 11,
    "déc.": 12,
    "déc": 12,
    "dec.": 12,
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


def parse_date(text):

    pattern = re.compile(
        r"(\d{1,2})\s+"
        r"(janv\.?|févr\.?|mars|avr\.?|mai|juin|"
        r"juil\.?|août|aout|sept\.?|oct\.?|nov\.?|"
        r"déc\.?|dec\.?)\s+"
        r"(\d{1,2})h(\d{2})",
        re.IGNORECASE
    )

    match = pattern.search(text)

    if not match:
        return None

    day = int(match.group(1))
    month_text = match.group(2).lower()
    hour = int(match.group(3))
    minute = int(match.group(4))

    month = MONTHS.get(month_text)

    if month is None:
        return None

    if month >= 9:
        year = 2026
    else:
        year = 2027

    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=TZ
    )


def get_page_text():

    print("Téléchargement de la page FFBB...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9",
    }

    response = requests.get(
        URL,
        headers=headers,
        timeout=60
    )

    print(f"HTTP : {response.status_code}")
    print(f"Taille de la page : {len(response.text)} caractères")

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    return soup.get_text("\n")


def find_matches(text):

    lines = [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]

    try:
        start = next(
            i for i, line in enumerate(lines)
            if line == "Calendrier"
        )
    except StopIteration:

        raise RuntimeError(
            "Impossible de trouver la section 'Calendrier' "
            "sur la page FFBB."
        )

    end = len(lines)

    for i in range(start + 1, len(lines)):

        if "Datas de l'équipe" in lines[i]:
            end = i
            break

    lines = lines[start:end]

    matches = []
    current = None

    for line in lines:

        journey_match = re.fullmatch(
            r"J(\d+)",
            line
        )

        if journey_match:

            if current is not None:

                if (
                    current.get("date")
                    and current.get("opponent")
                    and current.get("domicile") is not None
                ):
                    matches.append(current)

            current = {
                "journee": int(
                    journey_match.group(1)
                ),
                "date": None,
                "domicile": None,
                "opponent": None,
            }

            continue

        if current is None:
            continue

        if current["date"] is None:

            parsed = parse_date(line)

            if parsed:

                current["date"] = parsed
                continue

        if line == "Domicile":

            current["domicile"] = True
            continue

        if line == "Extérieur":

            current["domicile"] = False
            continue

        if (
            current["date"] is not None
            and current["domicile"] is not None
            and current["opponent"] is None
        ):

            if line in [
                "00",
                "Résultat",
                "Resultat",
            ]:
                continue

            if line.startswith("#"):
                continue

            if len(line) >= 3:

                current["opponent"] = line

    if current is not None:

        if (
            current.get("date")
            and current.get("opponent")
            and current.get("domicile") is not None
        ):
            matches.append(current)

    return matches


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
        TZ
    ).strftime("%Y%m%dT%H%M%S")

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

        opponent = match["opponent"]

        if match["domicile"]:

            summary = (
                "Châtillon-en-Vendelais Basket 2 - "
                f"{opponent}"
            )

            location = "Châtillon-en-Vendelais"

        else:

            summary = (
                f"{opponent} - "
                "Châtillon-en-Vendelais Basket 2"
            )

            location = opponent

        uid = (
            f"chatillon-dm4-"
            f"j{match['journee']}-"
            f"{start.strftime('%Y%m%d%H%M')}"
            "@github"
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"DTSTART;TZID=Europe/Paris:{start_str}",
            f"DTEND;TZID=Europe/Paris:{end_str}",
            f"SUMMARY:{escape_ics(summary)}",
            f"LOCATION:{escape_ics(location)}",
            (
                "DESCRIPTION:"
                "Châtillon-en-Vendelais Basket 2 - DM4 - "
                f"Journée {match['journee']}"
            ),
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    print("================================")
    print("CALENDRIER CHÂTILLON DM4")
    print("================================")
    print()

    text = get_page_text()

    print("Analyse du calendrier FFBB...")

    matches = find_matches(text)

    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"],
            match["domicile"],
            match["opponent"],
        )

        unique[key] = match

    matches = list(unique.values())

    matches.sort(
        key=lambda x: x["date"]
    )

    print()
    print("================================")
    print(f"MATCHS TROUVÉS : {len(matches)}")
    print("================================")

    for match in matches:

        print(
            f"J{match['journee']} | "
            f"{match['date'].strftime('%d/%m/%Y %H:%M')} | "
            f"{'DOMICILE' if match['domicile'] else 'EXTÉRIEUR'} | "
            f"{match['opponent']}"
        )

    if len(matches) < 18:

        raise RuntimeError(
            f"Seulement {len(matches)} matchs récupérés. "
            "Le fichier ICS ne sera pas publié."
        )

    ics = generate_ics(matches)

    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(ics)

    print()
    print(
        f"✓ {OUTPUT} généré avec succès."
    )


if __name__ == "__main__":
    main()
