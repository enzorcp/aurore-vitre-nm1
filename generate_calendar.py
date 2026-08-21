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
    return re.sub(r"[ \t]+", " ", text).strip()


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

    jour = int(match.group(1))
    mois_num = mois[match.group(2).lower()]
    annee = int(match.group(3))
    heure = int(match.group(4))
    minute = int(match.group(5))

    return datetime(
        annee,
        mois_num,
        jour,
        heure,
        minute,
        tzinfo=TZ
    )


def extract_matches(page_text, journee):
    """
    Analyse le texte rendu par la page FFBB.

    Une journée contient plusieurs blocs :
    DATE/HEURE
    EQUIPE 1
    EQUIPE 2
    Résultat

    On cherche le bloc contenant Vitré.
    """

    lines = [
        clean(line)
        for line in page_text.splitlines()
        if clean(line)
    ]

    # On repère les lignes contenant une date/heure.
    date_indexes = []

    for index, line in enumerate(lines):
        if parse_date(line):
            date_indexes.append(index)

    matches = []

    for i, start in enumerate(date_indexes):

        end = (
            date_indexes[i + 1]
            if i + 1 < len(date_indexes)
            else len(lines)
        )

        block = lines[start:end]

        date = parse_date(block[0])

        if not date:
            continue

        # Recherche de Vitré dans le bloc.
        vitre_index = None

        for j, line in enumerate(block):
            if TEAM in line.upper():
                vitre_index = j
                break

        if vitre_index is None:
            continue

        # On cherche l'adversaire autour de Vitré.
        before = None
        after = None

        if vitre_index > 0:
            before = block[vitre_index - 1]

        if vitre_index + 1 < len(block):
            after = block[vitre_index + 1]

        # Certaines pages peuvent insérer des éléments
        # supplémentaires. On élimine les lignes inutiles.
        ignored = {
            "Résultat",
            "Resultat",
            "0 0",
        }

        if before in ignored:
            before = None

        if after in ignored:
            after = None

        # Cas Vitré à domicile :
        # AURORE VITRE
        # ADVERSAIRE
        if after and after.upper() != TEAM:
            opponent = after
            domicile = True

        # Cas Vitré à l'extérieur :
        # ADVERSAIRE
        # AURORE VITRE
        elif before:
            opponent = before
            domicile = False

        else:
            continue

        # Évite de récupérer "Résultat" ou des éléments du menu.
        if (
            opponent.lower() in [
                "résultat",
                "resultat",
                "classement officiel",
            ]
            or "AURORE VITRE" in opponent.upper()
        ):
            continue

        matches.append({
            "journee": journee,
            "date": date,
            "opponent": opponent,
            "domicile": domicile,
        })

    return matches


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
            location = "Vitré"
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

        description = (
            f"NM1 2026-2027 - "
            f"Journée {match['journee']}"
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"DTSTART;TZID=Europe/Paris:{start_str}",
            f"DTEND;TZID=Europe/Paris:{end_str}",
            f"SUMMARY:{escape(summary)}",
            f"LOCATION:{escape(location)}",
            f"DESCRIPTION:{escape(description)}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    all_matches = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )

        for journee in range(1, 27):

            url = (
                f"{BASE_URL}"
                f"?journee={journee}"
                f"&phase={PHASE}"
                f"&poule={POULE}"
            )

            print()
            print(
                f"========== JOURNÉE {journee} =========="
            )
            print(url)

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                # Le calendrier est chargé dynamiquement.
                page.wait_for_timeout(3000)

                text = page.locator(
                    "body"
                ).inner_text()

                matches = extract_matches(
                    text,
                    journee
                )

                if matches:

                    for match in matches:

                        print(
                            f"✓ {match['date']} | "
                            f"{'DOMICILE' if match['domicile'] else 'EXTÉRIEUR'} | "
                            f"{match['opponent']}"
                        )

                    all_matches.extend(matches)

                else:

                    print(
                        "⚠ Aucun match de Vitré trouvé "
                        f"pour la journée {journee}"
                    )

                    # Affiche le contexte autour de Vitré
                    # pour faciliter le diagnostic si nécessaire.
                    position = text.upper().find(
                        "AURORE VITRE"
                    )

                    if position >= 0:
                        print(
                            text[
                                max(0, position - 300):
                                position + 500
                            ]
                        )

            except Exception as error:

                print(
                    f"❌ Erreur journée {journee}: {error}"
                )

        browser.close()

    # Suppression des éventuels doublons.
    unique = {}

    for match in all_matches:

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
    print("==============================")
    print(
        f"TOTAL : {len(matches)} MATCH(S)"
    )
    print("==============================")

    if len(matches) < 20:
        raise RuntimeError(
            "Moins de 20 matchs trouvés. "
            "Le calendrier n'a pas été généré "
            "afin d'éviter de publier un calendrier incomplet."
        )

    ics = generate_ics(matches)

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
