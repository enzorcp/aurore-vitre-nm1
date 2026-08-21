from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

BASE_URL = "https://competitions.ffbb.com/competitions/nm1"
PHASE = "200000002897178"
POULE = "200000003054369"

TEAM = "AURORE VITRE BASKET BRETAGNE"

TZ = ZoneInfo("Europe/Paris")


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def normalize(text):
    text = clean(text)
    return text.upper()


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


def get_team_names(page):
    """
    Récupère les noms des équipes directement
    depuis les liens présents sur la page FFBB.
    """

    names = []

    links = page.locator("a")

    for i in range(links.count()):

        try:
            text = clean(
                links.nth(i).inner_text()
            )

            if not text:
                continue

            upper = normalize(text)

            # Les équipes de NM1 apparaissent généralement
            # comme des liens en majuscules.
            if (
                len(text) > 5
                and len(text) < 100
                and (
                    "BASKET" in upper
                    or "BASKETBALL" in upper
                    or "UNION" in upper
                    or "ETOILE" in upper
                    or "TOURS" in upper
                    or "RENNES" in upper
                    or "VITRE" in upper
                    or "ANGERS" in upper
                    or "LORIENT" in upper
                    or "LAVAL" in upper
                    or "FOUGERES" in upper
                    or "BORDEAUX" in upper
                    or "TARBES" in upper
                    or "CHARTRES" in upper
                    or "CHALLANS" in upper
                    or "SABLES" in upper
                )
            ):
                if text not in names:
                    names.append(text)

        except Exception:
            pass

    return names


def find_match(page, journee):

    body = page.locator("body").inner_text()

    body = body.replace("\xa0", " ")

    # Toutes les dates présentes sur la page.
    date_pattern = re.compile(
        r"\d{1,2}\s+"
        r"(?:janvier|février|mars|avril|mai|juin|juillet|août|"
        r"septembre|octobre|novembre|décembre)\s+"
        r"\d{4}\s+"
        r"\d{1,2}:\d{2}",
        re.IGNORECASE
    )

    dates = list(date_pattern.finditer(body))

    print(
        f"Dates trouvées sur la page : {len(dates)}"
    )

    team_names = get_team_names(page)

    print(
        f"Équipes détectées : {len(team_names)}"
    )

    team_upper = normalize(TEAM)

    # On recherche Vitré dans le texte.
    positions = []

    start = 0

    while True:

        pos = normalize(body).find(
            team_upper,
            start
        )

        if pos == -1:
            break

        positions.append(pos)
        start = pos + len(team_upper)

    print(
        f"Occurrences de Vitré : {len(positions)}"
    )

    if not positions:
        return None

    # On analyse chaque occurrence.
    for team_pos in positions:

        # -------------------------------------------------
        # 1. Trouver la dernière date AVANT Vitré
        # -------------------------------------------------

        current_date = None

        for date_match in dates:

            if date_match.start() < team_pos:

                current_date = parse_date(
                    date_match.group(0)
                )

            else:
                break

        if not current_date:
            print(
                "⚠ Date impossible à déterminer"
            )
            continue

        print(
            f"Date associée : {current_date}"
        )

        # -------------------------------------------------
        # 2. Chercher l'adversaire autour de Vitré
        # -------------------------------------------------

        # On prend une grande fenêtre autour du nom.
        before = body[
            max(0, team_pos - 300):
            team_pos
        ]

        after = body[
            team_pos + len(TEAM):
            team_pos + len(TEAM) + 300
        ]

        before_upper = normalize(before)
        after_upper = normalize(after)

        candidates = []

        for name in team_names:

            name_upper = normalize(name)

            if name_upper == team_upper:
                continue

            # Équipe avant Vitré
            pos_before = before_upper.rfind(
                name_upper
            )

            if pos_before >= 0:

                candidates.append(
                    (
                        "before",
                        pos_before,
                        name
                    )
                )

            # Équipe après Vitré
            pos_after = after_upper.find(
                name_upper
            )

            if pos_after >= 0:

                candidates.append(
                    (
                        "after",
                        pos_after,
                        name
                    )
                )

        if not candidates:
            print(
                "⚠ Aucun adversaire détecté"
            )
            continue

        # Le candidat le plus proche de Vitré.
        before_candidates = [
            c for c in candidates
            if c[0] == "before"
        ]

        after_candidates = [
            c for c in candidates
            if c[0] == "after"
        ]

        opponent = None
        domicile = None

        if after_candidates:

            # L'équipe juste après Vitré
            # est l'adversaire.
            after_candidates.sort(
                key=lambda x: x[1]
            )

            opponent = after_candidates[0][2]
            domicile = True

        elif before_candidates:

            before_candidates.sort(
                key=lambda x: x[1],
                reverse=True
            )

            opponent = before_candidates[0][2]
            domicile = False

        if opponent:

            print(
                "✓ ADVERSAIRE :",
                opponent
            )

            print(
                "✓",
                (
                    "DOMICILE"
                    if domicile
                    else "EXTÉRIEUR"
                )
            )

            return {
                "journee": journee,
                "date": current_date,
                "opponent": opponent,
                "domicile": domicile
            }

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
        "X-WR-TIMEZONE:Europe/Paris"
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
            "END:VEVENT"
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
                        "✓ MATCH :",
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
