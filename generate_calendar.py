from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

BASE_URL = "https://competitions.ffbb.com/competitions/nm1"
PHASE = "200000002897178"
POULE = "200000003054369"

TEAM = "AURORE VITRE BASKET BRETAGNE"
TZ = ZoneInfo("Europe/Paris")


def escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def parse_datetime(text):
    mois = {
        "janvier": 1,
        "février": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "août": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "décembre": 12,
    }

    pattern = (
        r"(\d{1,2})\s+"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|"
        r"septembre|octobre|novembre|décembre)\s+"
        r"(\d{4})\s+"
        r"(\d{1,2}):(\d{2})"
    )

    m = re.search(pattern, text, re.IGNORECASE)

    if not m:
        return None

    return datetime(
        int(m.group(3)),
        mois[m.group(2).lower()],
        int(m.group(1)),
        int(m.group(4)),
        int(m.group(5)),
        tzinfo=TZ,
    )


def get_team_links(page):
    """
    Récupère directement les liens vers les équipes
    dans le HTML rendu par FFBB.
    """

    links = page.locator("a").all()

    result = []

    for link in links:

        try:
            text = link.inner_text().strip()
            href = link.get_attribute("href")

            if not href:
                continue

            if TEAM in text.upper():

                result.append({
                    "text": text,
                    "href": href
                })

        except Exception:
            pass

    return result


def extract_match_from_page(page, journee):

    # On cherche tous les éléments contenant exactement
    # le nom officiel de Vitré.
    locator = page.get_by_text(
        TEAM,
        exact=True
    )

    count = locator.count()

    print(
        f"Éléments '{TEAM}' trouvés : {count}"
    )

    if count == 0:
        return None

    # Le premier élément correspond normalement
    # au match de la journée.
    element = locator.first

    # On remonte dans les parents pour retrouver
    # le conteneur du match.
    current = element

    for _ in range(8):

        try:
            current = current.locator("..")

            text = current.inner_text()

            if (
                TEAM in text.upper()
                and (
                    "Résultat" in text
                    or "Resultat" in text
                )
            ):
                break

        except Exception:
            break

    text = current.inner_text()

    print("CONTENU DU BLOC :")
    print(text)

    date = parse_datetime(text)

    if not date:
        return None

    # On récupère les liens des équipes présents
    # dans le bloc du match.
    team_elements = current.locator("a")

    teams = []

    for i in range(team_elements.count()):

        try:

            name = team_elements.nth(i).inner_text().strip()

            if name and name not in teams:
                teams.append(name)

        except Exception:
            pass

    print("ÉQUIPES TROUVÉES :", teams)

    # On cherche Vitré dans les équipes.
    vitre_index = None

    for i, team in enumerate(teams):

        if TEAM in team.upper():

            vitre_index = i
            break

    if vitre_index is None:
        return None

    # Le match doit contenir exactement deux équipes.
    # On prend les deux premières équipes pertinentes.
    if len(teams) < 2:
        return None

    if vitre_index == 0:
        opponent = teams[1]
        domicile = True
    else:
        opponent = teams[0]
        domicile = False

    # Évite de récupérer des liens parasites.
    if (
        "CLASSEMENT" in opponent.upper()
        or "RÉSULTAT" in opponent.upper()
        or "RESULTAT" in opponent.upper()
    ):
        return None

    return {
        "journee": journee,
        "date": date,
        "opponent": opponent,
        "domicile": domicile,
    }


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
        end = start + timedelta(hours=2)

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
            f"{match['journee']}-"
            f"{start_str}@github"
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"DTSTART;TZID=Europe/Paris:{start_str}",
            f"DTEND;TZID=Europe/Paris:{end_str}",
            f"SUMMARY:{escape(summary)}",
            f"LOCATION:{escape(location)}",
            f"DESCRIPTION:NM1 2026-2027 - Journée {match['journee']}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    matches = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            locale="fr-FR",
            timezone_id="Europe/Paris"
        )

        for journee in range(1, 27):

            print()
            print(
                "================================"
            )
            print(
                f"JOURNÉE {journee}"
            )
            print(
                "================================"
            )

            url = (
                f"{BASE_URL}"
                f"?journee={journee}"
                f"&phase={PHASE}"
                f"&poule={POULE}"
            )

            print(url)

            try:

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=60000
                )

                # Petite sécurité pour laisser
                # le rendu FFBB terminer.
                page.wait_for_timeout(2000)

                match = extract_match_from_page(
                    page,
                    journee
                )

                if match:

                    matches.append(match)

                    print(
                        "✓ MATCH TROUVÉ :",
                        match["date"],
                        "|",
                        (
                            "DOMICILE"
                            if match["domicile"]
                            else "EXTÉRIEUR"
                        ),
                        "|",
                        match["opponent"]
                    )

                else:

                    print(
                        "⚠ Match non trouvé"
                    )

            except Exception as error:

                print(
                    "❌ Erreur :",
                    error
                )

        browser.close()

    # Suppression des doublons
    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"],
            match["opponent"],
            match["domicile"],
        )

        unique[key] = match

    matches = list(unique.values())

    matches.sort(
        key=lambda x: x["date"]
    )

    print()
    print(
        "================================"
    )
    print(
        f"TOTAL : {len(matches)} MATCHS"
    )
    print(
        "================================"
    )

    if len(matches) < 20:

        raise RuntimeError(
            "Moins de 20 matchs récupérés. "
            "Le fichier ICS ne sera pas publié."
        )

    ics = generate_ics(matches)

    with open(
        "calendrier.ics",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(ics)

    print(
        "✓ calendrier.ics généré."
    )


if __name__ == "__main__":
    main()
