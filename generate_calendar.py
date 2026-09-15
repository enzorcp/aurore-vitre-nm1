from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re


# ============================================================
# CONFIGURATION
# ============================================================

URL = (
    "https://competitions.ffbb.com/ligues/bre/comites/0035/"
    "clubs/bre0035110/equipes/200000005334552"
)

TEAM = "VITRE"

OUTPUT = "calendrier.ics"

TZ = ZoneInfo("Europe/Paris")


# Mois affichés par la FFBB
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


# ============================================================
# OUTILS
# ============================================================

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
    """
    La FFBB affiche par exemple :

    18 sept. 22h00
    25 sept. 22h30
    29 sept. 22h30

    L'année n'est pas affichée.
    On utilise donc la saison 2026-2027.
    """

    pattern = re.compile(
        r"^(\d{1,2})\s+"
        r"(janv\.?|févr\.?|mars|avr\.?|mai|juin|"
        r"juil\.?|août|aout|sept\.?|oct\.?|nov\.?|"
        r"déc\.?|dec\.?)\s+"
        r"(\d{1,2})h(\d{2})$",
        re.IGNORECASE
    )

    match = pattern.match(clean(text))

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


# ============================================================
# RECUPERATION DES MATCHS
# ============================================================

def get_matches(page):

    print()
    print("================================")
    print("LECTURE DU CALENDRIER FFBB")
    print("================================")
    print(URL)
    print()

    body = page.locator("body").inner_text()

    lines = [
        clean(line)
        for line in body.splitlines()
        if clean(line)
    ]

    matches = []

    current_journee = None
    current_date = None
    current_domicile = None

    # On commence réellement au premier J1
    started = False

    i = 0

    while i < len(lines):

        line = lines[i]

        # ----------------------------------------------------
        # FIN DU CALENDRIER
        # ----------------------------------------------------

        if line.startswith("Datas de l'équipe"):
            break

        # ----------------------------------------------------
        # JOURNEE
        # ----------------------------------------------------

        match_j = re.fullmatch(
            r"J(\d+)",
            line
        )

        if match_j:

            started = True

            current_journee = int(
                match_j.group(1)
            )

            current_date = None
            current_domicile = None

            print(
                f"JOURNÉE {current_journee}"
            )

            i += 1
            continue

        if not started:
            i += 1
            continue

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        parsed_date = parse_date(line)

        if parsed_date:

            current_date = parsed_date

            print(
                f"  DATE : {current_date}"
            )

            i += 1
            continue

        # ----------------------------------------------------
        # DOMICILE / EXTERIEUR
        # ----------------------------------------------------

        if line == "Domicile":

            current_domicile = True

            i += 1

            # L'adversaire est normalement juste après.
            if i < len(lines):

                opponent = lines[i]

                # Protection contre les éléments parasites
                if (
                    opponent not in [
                        "00",
                        "Résultat",
                        "Resultat",
                    ]
                    and not re.fullmatch(
                        r"#\d+",
                        opponent
                    )
                    and not opponent.startswith("J")
                ):

                    if current_date is not None:

                        matches.append({
                            "journee": current_journee,
                            "date": current_date,
                            "domicile": True,
                            "opponent": opponent,
                        })

                        print(
                            f"  ✓ DOMICILE : {opponent}"
                        )

            i += 1
            continue

        if line == "Extérieur":

            current_domicile = False

            i += 1

            # L'adversaire est normalement juste après.
            if i < len(lines):

                opponent = lines[i]

                if (
                    opponent not in [
                        "00",
                        "Résultat",
                        "Resultat",
                    ]
                    and not re.fullmatch(
                        r"#\d+",
                        opponent
                    )
                    and not opponent.startswith("J")
                ):

                    if current_date is not None:

                        matches.append({
                            "journee": current_journee,
                            "date": current_date,
                            "domicile": False,
                            "opponent": opponent,
                        })

                        print(
                            f"  ✓ EXTÉRIEUR : {opponent}"
                        )

            i += 1
            continue

        i += 1

    return matches


# ============================================================
# GENERATION ICS
# ============================================================

def generate_ics(matches):

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Aurore Vitré Basket//NM1//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Aurore Vitré Basket - NM1",
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
                f"Aurore Vitré NM1 - {opponent}"
            )

            location = (
                "Salle de la Poultière, Vitré"
            )

        else:

            summary = (
                f"{opponent} - Aurore Vitré NM1"
            )

            location = opponent

        uid = (
            f"aurore-vitre-nm1-"
            f"j{match['journee']}-"
            f"{start_str}@github"
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
                f"DESCRIPTION:"
                f"NM1 2026-2027 - "
                f"Journée {match['journee']}"
            ),
            "END:VEVENT",
        ])

    lines.append(
        "END:VCALENDAR"
    )

    return "\r\n".join(lines) + "\r\n"


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            locale="fr-FR",
            timezone_id="Europe/Paris"
        )

        print("Ouverture de la page FFBB...")

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(
            3000
        )

        matches = get_matches(
            page
        )

        browser.close()

    # --------------------------------------------------------
    # SUPPRESSION DES DOUBLONS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # RESULTAT
    # --------------------------------------------------------

    print()
    print("================================")
    print(
        f"TOTAL : {len(matches)} MATCHS"
    )
    print("================================")

    for match in matches:

        print(
            f"J{match['journee']} | "
            f"{match['date']} | "
            f"{'DOMICILE' if match['domicile'] else 'EXTÉRIEUR'} | "
            f"{match['opponent']}"
        )

    # --------------------------------------------------------
    # SECURITE
    # --------------------------------------------------------

    if len(matches) < 20:

        raise RuntimeError(
            f"Seulement {len(matches)} matchs récupérés. "
            "Le fichier ICS ne sera pas publié."
        )

    # --------------------------------------------------------
    # GENERATION
    # --------------------------------------------------------

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
        "✓ calendrier.ics généré avec succès."
    )


if __name__ == "__main__":
    main()
