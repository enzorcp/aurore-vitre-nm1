from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

BASE_URL = "https://competitions.ffbb.com/competitions/nm1"
PHASE = "200000002897178"
POULE = "200000003054369"

TEAM = "AURORE VITRE BASKET BRETAGNE"

TZ = ZoneInfo("Europe/Paris")


# Toutes les équipes de la poule B.
TEAMS = [
    "CENTRE FEDERAL BB",
    "TOULOUSE BASKETBALL CLUB",
    "ETOILE ANGERS BASKET",
    "TOURS METROPOLE BASKET",
    "LES SABLES VENDEE BASKET",
    "C’CHARTRES METROPOLE BASKET",
    "C'CHARTRES METROPOLE BASKET",
    "UNION RENNES BASKET 35 (URB 35)",
    "AURORE VITRE BASKET BRETAGNE",
    "UNION TARBES LOURDES PYRENEES BASKET",
    "JSA BORDEAUX METROPOLE BASKET",
    "CEP LORIENT BREIZH BASKET",
    "US LAVAL BASKET",
    "VENDEE CHALLANS BASKET",
    "PAYS DE FOUGERES BASKET",
]


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def normalize(text):
    return clean(text).upper()


def parse_date(text):

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

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    return datetime(
        int(match.group(3)),
        mois[match.group(2).lower()],
        int(match.group(1)),
        int(match.group(4)),
        int(match.group(5)),
        tzinfo=TZ
    )


def get_match_container(page, team_element):

    """
    Remonte dans le DOM jusqu'au plus petit conteneur
    contenant exactement deux équipes de la poule.
    """

    current = team_element

    for niveau in range(12):

        try:

            current = current.locator("..")

            links = current.locator("a")

            found_teams = []

            for i in range(links.count()):

                try:

                    name = clean(
                        links.nth(i).inner_text()
                    )

                    name_upper = normalize(name)

                    for team in TEAMS:

                        if name_upper == normalize(team):

                            if name not in found_teams:
                                found_teams.append(name)

                            break

                except Exception:
                    pass

            # C'est notre bloc de match lorsqu'il contient
            # exactement deux équipes.
            if len(found_teams) == 2:

                if TEAM in [
                    normalize(x)
                    for x in found_teams
                ]:
                    return current, found_teams

        except Exception:
            break

    return None, []


def get_date_for_match(page, match_element):

    """
    Cherche le dernier titre de date avant le match.
    Les dates de la FFBB sont dans des titres H2.
    """

    date_pattern = re.compile(
        r"\d{1,2}\s+"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|"
        r"septembre|octobre|novembre|décembre)\s+"
        r"\d{4}\s+"
        r"\d{1,2}:\d{2}",
        re.IGNORECASE
    )

    headings = page.locator(
        "h1, h2, h3, h4"
    )

    candidates = []

    for i in range(headings.count()):

        heading = headings.nth(i)

        try:

            text = clean(
                heading.inner_text()
            )

            date = parse_date(text)

            if not date:
                continue

            # Vérifie que le titre est avant le match
            is_before = heading.evaluate(
                """
                (heading, match) => {
                    return !!(
                        heading.compareDocumentPosition(match)
                        & Node.DOCUMENT_POSITION_FOLLOWING
                    );
                }
                """,
                match_element
            )

            if is_before:
                candidates.append(date)

        except Exception:
            pass

    if candidates:
        return candidates[-1]

    # Sécurité : recherche dans le texte complet.
    body = page.locator("body").inner_text()

    match_text = clean(
        match_element.inner_text()
    )

    position = body.find(
        match_text
    )

    if position >= 0:

        before = body[:position]

        matches = list(
            date_pattern.finditer(before)
        )

        if matches:
            return parse_date(
                matches[-1].group(0)
            )

    return None


def find_match(page, journee):

    locator = page.get_by_text(
        TEAM,
        exact=True
    )

    count = locator.count()

    print(
        f"Occurrences de Vitré : {count}"
    )

    for i in range(count):

        try:

            team_element = locator.nth(i)

            match_element, teams = get_match_container(
                page,
                team_element
            )

            if not match_element:
                continue

            print(
                f"Bloc trouvé : {teams}"
            )

            if len(teams) != 2:
                continue

            # Détermine l'adversaire.
            opponent = None

            for team in teams:

                if normalize(team) != normalize(TEAM):

                    opponent = team
                    break

            if not opponent:
                continue

            # Date du match.
            date = get_date_for_match(
                page,
                match_element
            )

            if not date:

                print(
                    "⚠ Date non trouvée pour ce bloc"
                )

                continue

            # Ordre des équipes dans le bloc :
            # équipe 1 = domicile
            # équipe 2 = extérieur.
            if normalize(teams[0]) == normalize(TEAM):

                domicile = True

            else:

                domicile = False

            print(
                f"✓ DATE : {date}"
            )

            print(
                f"✓ ADVERSAIRE : {opponent}"
            )

            print(
                "✓",
                "DOMICILE" if domicile else "EXTÉRIEUR"
            )

            return {
                "journee": journee,
                "date": date,
                "opponent": opponent,
                "domicile": domicile,
            }

        except Exception as error:

            print(
                f"Erreur sur occurrence {i}: {error}"
            )

    return None


def escape(text):

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


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
            f"SUMMARY:{escape(summary)}",
            f"LOCATION:{escape(location)}",
            f"DESCRIPTION:NM1 2026-2027 - Journée {match['journee']}",
            "END:VEVENT",
        ])

    lines.append(
        "END:VCALENDAR"
    )

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

                page.wait_for_timeout(
                    2000
                )

                match = find_match(
                    page,
                    journee
                )

                if match:

                    matches.append(
                        match
                    )

                    print(
                        f"✓ MATCH : "
                        f"{match['date']} | "
                        f"{'DOMICILE' if match['domicile'] else 'EXTÉRIEUR'} | "
                        f"{match['opponent']}"
                    )

                else:

                    print(
                        "⚠ Match non trouvé"
                    )

            except Exception as error:

                print(
                    f"❌ Erreur : {error}"
                )

        browser.close()

    # Suppression des doublons.
    unique = {}

    for match in matches:

        key = (
            match["journee"],
            match["date"],
            match["opponent"],
            match["domicile"]
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

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

    ics = generate_ics(
        matches
    )

    with open(
        "calendrier.ics",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(ics)

    print(
        "✓ calendrier.ics généré avec succès."
    )


if __name__ == "__main__":
    main()
