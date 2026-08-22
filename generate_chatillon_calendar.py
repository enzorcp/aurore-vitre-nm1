from playwright.sync_api import sync_playwright
from datetime import datetime
from zoneinfo import ZoneInfo
import re


URL = (
    "https://competitions.ffbb.com/ligues/bre/comites/0035/"
    "clubs/bre0035135/equipes/200000005342013"
)

TEAM = "CHÂTILLON-EN-VENDELAIS BASKET - 2"
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

    # Saison 2026-2027
    # Septembre -> décembre 2026
    # Janvier -> avril 2027
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


def find_match_blocks(page):

    """
    La page FFBB contient une structure très régulière :

    J1
    27 sept. 02h00
    Extérieur
    ADVERSAIRE

    J2
    4 oct. 02h00
    Domicile
    ADVERSAIRE

    etc.

    On récupère directement les lignes visibles.
    """

    body = page.locator("body").inner_text()

    lines = [
        clean(line)
        for line in body.splitlines()
        if clean(line)
    ]

    matches = []

    current = None

    for line in lines:

        # Nouvelle journée
        journey_match = re.fullmatch(
            r"J(\d+)",
            line
        )

        if journey_match:

            # Sauvegarde le match précédent
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

        # Date / heure
        if current["date"] is None:

            parsed = parse_date(line)

            if parsed:

                current["date"] = parsed
                continue

        # Domicile / extérieur
        if line == "Domicile":

            current["domicile"] = True
            continue

        if line == "Extérieur":

            current["domicile"] = False
            continue

        # Une fois qu'on connaît date + domicile/extérieur,
        # le prochain nom d'équipe est l'adversaire.
        if (
            current["date"] is not None
            and current["domicile"] is not None
            and current["opponent"] is None
        ):

            # On ignore les éléments non pertinents.
            if line in [
                "00",
                "Résultat",
                "Resultat",
            ]:
                continue

            # On ignore les éléments de navigation.
            if line.startswith("#"):
                continue

            # L'adversaire est le nom du club.
            # On exclut les lignes manifestement hors match.
            if (
                len(line) >= 3
                and not line.startswith("J")
                and line != TEAM
            ):

                current["opponent"] = line

    # Dernier match
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

        # Durée par défaut de 2 heures.
        # Si l'heure est modifiée sur FFBB,
        # le calendrier sera automatiquement mis à jour.
        end = start.replace(
            hour=(start.hour + 2) % 24
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

    lines.append(
        "END:VCALENDAR"
    )

    return "\r\n".join(lines) + "\r\n"


def main():

    print("Ouverture de la page FFBB...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            locale="fr-FR",
            timezone_id="Europe/Paris"
        )

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(
            2000
        )

        matches = find_match_blocks(
            page
        )

        browser.close()

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

    for match in matches:

        print(
            f"J{match['journee']} | "
            f"{match['date']} | "
            f"{'DOMICILE' if match['domicile'] else 'EXTÉRIEUR'} | "
            f"{match['opponent']}"
        )

    # La page FFBB affiche actuellement 20 matchs :
    # J1-J6, J8-J17 et J19-J22.
    if len(matches) < 18:

        raise RuntimeError(
            "Trop peu de matchs récupérés. "
            "Le fichier ICS ne sera pas publié."
        )

    # Suppression des éventuels doublons.
    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"],
            match["domicile"],
            match["opponent"],
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    matches.sort(
        key=lambda x: x["date"]
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
