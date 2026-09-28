from playwright.sync_api import sync_playwright
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

    year = 2026 if month >= 9 else 2027

    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=TZ
    )


def get_page_text():

    print("Ouverture de la page FFBB avec Chromium...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            locale="fr-FR",
            timezone_id="Europe/Paris",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1920,
                "height": 1080
            }
        )

        print("Chargement de la page...")

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response:
            print(
                f"HTTP : {response.status}"
            )

        page.wait_for_timeout(5000)

        text = page.locator("body").inner_text(
            timeout=30000
        )

        print(
            f"Taille du texte récupéré : "
            f"{len(text)} caractères"
        )

        if len(text) < 1000:

            print(
                "ATTENTION : contenu FFBB très court."
            )

            print(text[:2000])

        browser.close()

    return text


def find_matches(text):

    lines = [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]

    print(
        f"Nombre de lignes analysables : {len(lines)}"
    )

    start = None

    for i, line in enumerate(lines):

        if line.lower() == "calendrier":

            start = i
            break

    if start is None:

        raise RuntimeError(
            "Section 'Calendrier' introuvable "
            "dans la page FFBB."
        )

    end = len(lines)

    for i in range(start + 1, len(lines)):

        if "Datas de l'équipe" in lines[i]:

            end = i
            break

    calendar_lines = lines[start:end]

    print(
        f"Lignes de calendrier : "
        f"{len(calendar_lines)}"
    )

    matches = []
    current = None

    for line in calendar_lines:

        match_j = re.fullmatch(
            r"J(\d+)",
            line
        )

        if match_j:

            if current is not None:

                if (
                    current["date"]
                    and current["domicile"] is not None
                    and current["opponent"]
                ):
                    matches.append(current)

            current = {
                "journee": int(match_j.group(1)),
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

            if line.startswith("#"):
                continue

            if line in [
                "00",
                "Résultat",
                "Resultat",
            ]:
                continue

            if len(line) >= 3:

                current["opponent"] = line

    if current is not None:

        if (
            current["date"]
            and current["domicile"] is not None
            and current["opponent"]
        ):
            matches.append(current)

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

    return matches


def generate_ics(matches):

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chatillon-en-Vendelais Basket//DM4//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Châtillon-en-Vendelais Basket 2 - DM4",
    ]

    # DTSTAMP doit être en UTC
    timestamp = datetime.now(
        ZoneInfo("UTC")
    ).strftime("%Y%m%dT%H%M%SZ")

    for match in matches:

        # On conserve exactement 00h00,
        # sans aucun fuseau horaire.
        start = match["date"]

        date_str = start.strftime("%Y%m%d")

        start_str = date_str + "T000000"
        end_str = date_str + "T020000"

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
            f"chatillon-dm4-j"
            f"{match['journee']}-"
            f"{date_str}@github"
        )

        lines.extend([
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
        ])

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"
    
    
    def main():

    print("========================================")
    print("CALENDRIER CHÂTILLON DM4")
    print("========================================")

    text = get_page_text()

    print()
    print("Analyse du calendrier...")

    matches = find_matches(text)

    print()
    print("========================================")
    print(f"MATCHS TROUVÉS : {len(matches)}")
    print("========================================")

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
