from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import re


URL = "https://competitions.ffbb.com/ligues/bre/comites/0035/clubs/bre0035110/equipes/200000005334552"
OUTPUT_FILE = "calendrier.ics"


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
    print("Téléchargement de la page FFBB...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            locale="fr-FR",
            timezone_id="Europe/Paris",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        page = context.new_page()

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        if response:
            print(f"HTTP : {response.status}")

        page.wait_for_timeout(5000)

        text = page.locator("body").inner_text()

        print(f"Taille de la page : {len(text)} caractères")

        browser.close()

        return text


def parse_date_and_time(line):
    """
    Recherche une date + heure directement dans la ligne.

    Exemples :
    18 sept. 22h00
    25 sept. 22h30
    29 sept. 22h30
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
    """
    Récupère les matchs directement depuis le calendrier FFBB.

    L'heure récupérée est exactement celle affichée par FFBB.
    Aucune conversion de fuseau horaire.
    """

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

        # Analyse du bloc de cette journée
        for j in range(i + 1, min(i + 20, len(lines))):

            current = lines[j]

            # Nouvelle journée = fin du bloc
            if re.fullmatch(
                r"J(\d+)",
                current,
                re.IGNORECASE,
            ):
                break

            # Date + heure affichées par FFBB
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

            # Recherche de l'adversaire
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
                }

                if current.lower() in ignored:
                    continue

                if re.fullmatch(r"\d+", current):
                    continue

                if re.fullmatch(
                    r"\d{1,2}h\d{2}",
                    current,
                    re.IGNORECASE,
                ):
                    continue

                opponent = current
                break

        if date_value and domicile is not None and opponent:

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
        "PRODID:-//Aurore Vitré Basket Bretagne//NM1//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Aurore Vitré Basket Bretagne - NM1",
    ]

    timestamp = datetime.utcnow().strftime(
        "%Y%m%dT%H%M%SZ"
    )

    for match in matches:

        start = match["date"]

        # Heure EXACTEMENT identique à celle de FFBB
        start_str = start.strftime(
            "%Y%m%dT%H%M%S"
        )

        # Durée de 2 heures
        end = start + timedelta(hours=2)

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

        opponent = match["opponent"]

        if match["domicile"]:

            summary = (
                "Aurore Vitré Basket - "
                + opponent
            )

            location = "Vitré"

        else:

            summary = (
                opponent
                + " - Aurore Vitré Basket"
            )

            location = opponent

        uid = (
            f"aurore-vitre-nm1-j"
            f"{match['journee']}-"
            f"{start.strftime('%Y%m%d')}@github"
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
                    "Aurore Vitré Basket Bretagne - "
                    f"NM1 - Journée {match['journee']}"
                ),
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    print("========================================")
    print("Calendrier Aurore Vitré Basket NM1")
    print("========================================")

    text = get_page_text()

    matches = find_matches(text)

    print()
    print(f"Matchs trouvés : {len(matches)}")
    print()

    if len(matches) < 20:

        print("ERREUR : trop peu de matchs trouvés.")
        print("Le calendrier FFBB a peut-être changé.")
        print()

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
    print(f"Calendrier généré : {OUTPUT_FILE}")
    print(f"Nombre d'événements : {len(matches)}")
    print("========================================")


if __name__ == "__main__":
    main()
