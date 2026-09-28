from playwright.sync_api import sync_playwright
from datetime import datetime
import re


URL = "https://competitions.ffbb.com/ligues/bre/comites/0035/clubs/bre0035135/equipes/200000005342013"
OUTPUT_FILE = "calendrier-chatillon.ics"


MONTHS = {
    "janv.": 1,
    "févr.": 2,
    "mars": 3,
    "avr.": 4,
    "mai": 5,
    "juin": 6,
    "juil.": 7,
    "août": 8,
    "sept.": 9,
    "oct.": 10,
    "nov.": 11,
    "déc.": 12,
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

        # Laisser le temps à FFBB de charger complètement le calendrier
        page.wait_for_timeout(5000)

        text = page.locator("body").inner_text()

        print(f"Taille de la page : {len(text)} caractères")

        browser.close()

        return text


def parse_date(date_text):
    """
    Transforme par exemple :
    '27 sept. 02h00'
    en datetime.
    """

    match = re.search(
        r"(\d{1,2})\s+([a-zéû.]+)\s+(\d{1,2})h(\d{2})",
        date_text,
        re.IGNORECASE,
    )

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2).lower()
    hour = int(match.group(3))
    minute = int(match.group(4))

    month = MONTHS.get(month_name)

    if not month:
        return None

    # Saison 2026-2027
    # Septembre -> décembre = 2026
    # Janvier -> avril = 2027
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
    Analyse le texte de la page FFBB et récupère les matchs.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    matches = []

    for i, line in enumerate(lines):

        # Recherche d'une journée : J1, J2, J3...
        journee_match = re.fullmatch(r"J(\d+)", line)

        if not journee_match:
            continue

        journee = int(journee_match.group(1))

        date_value = None
        domicile = None
        opponent = None

        # On regarde les lignes suivantes
        for j in range(i + 1, min(i + 10, len(lines))):

            current = lines[j]

            # Date + heure
            if date_value is None:
                parsed = parse_date(current)

                if parsed:
                    date_value = parsed
                    continue

            # Domicile / extérieur
            if current in ("Domicile", "Extérieur"):
                domicile = current == "Domicile"
                continue

            # On ignore les résultats et éléments inutiles
            if current in (
                "00",
                "01",
                "02",
                "03",
                "04",
                "05",
                "#",
            ):
                continue

            if re.fullmatch(r"\d+", current):
                continue

            # Une fois la date et le statut trouvés,
            # la prochaine ligne correspond généralement à l'adversaire.
            if date_value and domicile is not None:
                if (
                    current
                    not in (
                        "Calendrier",
                        "Résultats",
                        "Classement",
                        "Domicile",
                        "Extérieur",
                    )
                    and not current.startswith("J")
                ):
                    opponent = current
                    break

        if date_value and domicile is not None and opponent:

            # Évite de récupérer une ligne qui n'est pas un adversaire
            if len(opponent) > 2:

                matches.append(
                    {
                        "journee": journee,
                        "date": date_value,
                        "domicile": domicile,
                        "opponent": opponent,
                    }
                )

    # Suppression des éventuels doublons
    unique = {}

    for match in matches:
        key = (
            match["journee"],
            match["date"].strftime("%Y-%m-%d"),
            match["opponent"],
        )

        unique[key] = match

    matches = list(unique.values())

    # Tri chronologique
    matches.sort(
        key=lambda x: (
            x["date"],
            x["journee"],
        )
    )

    return matches


def escape_ics(value):
    """
    Échappe les caractères spéciaux nécessaires au format ICS.
    """

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generate_ics(matches):
    """
    Génère le fichier ICS.

    IMPORTANT :
    Les heures sont volontairement écrites sans fuseau horaire
    afin d'éviter le décalage +1h en hiver / +2h en été.

    Les matchs Châtillon apparaîtront donc à 00h00.
    """

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chatillon-en-Vendelais Basket//DM4//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Châtillon-en-Vendelais Basket 2 - DM4",
    ]

    # DTSTAMP en UTC
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for match in matches:

        start = match["date"]

        date_str = start.strftime("%Y%m%d")

        # IMPORTANT :
        # Pas de TZID et pas de conversion UTC.
        # Le match reste donc à 00h00.
        start_str = date_str + "T000000"
        end_str = date_str + "T020000"

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

    print(f"Matchs trouvés : {len(matches)}")

    if len(matches) < 18:
        print()
        print("ERREUR : trop peu de matchs trouvés.")
        print("Le calendrier FFBB a peut-être changé.")
        print()
        raise RuntimeError(
            f"Seulement {len(matches)} matchs trouvés."
        )

    print()
    print("Matchs détectés :")

    for match in matches:
        statut = (
            "Domicile"
            if match["domicile"]
            else "Extérieur"
        )

        print(
            f"J{match['journee']} | "
            f"{match['date'].strftime('%d/%m/%Y')} | "
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
