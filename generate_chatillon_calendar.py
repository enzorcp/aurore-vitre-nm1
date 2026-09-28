from playwright.sync_api import sync_playwright
from datetime import datetime
import re


URL = "https://competitions.ffbb.com/ligues/bre/comites/0035/clubs/bre0035135/equipes/200000005342013"
OUTPUT_FILE = "calendrier-chatillon.ics"


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

        # Laisser FFBB charger complètement le calendrier
        page.wait_for_timeout(5000)

        text = page.locator("body").inner_text()

        print(f"Taille de la page : {len(text)} caractères")

        browser.close()

        return text


def parse_date_and_time(line):
    """
    Recherche une date et une heure directement dans une ligne.

    Exemples acceptés :
        27 sept. 20h15
        4 oct. 10h30
        8 nov. 01h00
        4 avr. 02h00
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
    Récupère les matchs à partir du calendrier affiché par FFBB.

    L'heure récupérée est l'heure affichée par FFBB.
    Aucune conversion de fuseau horaire n'est effectuée.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    matches = []

    for i, line in enumerate(lines):

        # Recherche d'une journée : J1, J2, J3...
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

        # On analyse uniquement le bloc correspondant à cette journée.
        # On s'arrête lorsqu'une nouvelle journée apparaît.
        for j in range(i + 1, min(i + 20, len(lines))):

            current = lines[j]

            # Nouvelle journée : fin du bloc actuel
            if re.fullmatch(
                r"J(\d+)",
                current,
                re.IGNORECASE,
            ):
                break

            # Recherche directe de la date + heure affichées
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

            # Une fois les informations principales récupérées,
            # la prochaine ligne pertinente est l'adversaire.
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

                if current.lower() not in ignored:

                    # On ignore les nombres seuls
                    if not re.fullmatch(r"\d+", current):

                        # On ignore les heures seules éventuelles
                        if not re.fullmatch(
                            r"\d{1,2}h\d{2}",
                            current,
                            re.IGNORECASE,
                        ):

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
    Échappe les caractères spéciaux du format ICS.
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
    Les heures sont des heures locales flottantes.

    Cela signifie que si FFBB indique 20h15,
    l'ICS contient exactement 20h15.

    Aucune conversion été/hiver n'est appliquée.
    """

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chatillon-en-Vendelais Basket//DM4//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Châtillon-en-Vendelais Basket 2 - DM4",
    ]

    # DTSTAMP n'est pas l'heure du match.
    # Il sert uniquement à indiquer quand l'événement a été généré.
    timestamp = datetime.utcnow().strftime(
        "%Y%m%dT%H%M%SZ"
    )

    for match in matches:

        start = match["date"]

        date_str = start.strftime("%Y%m%d")

        # IMPORTANT :
        # On utilise directement l'heure récupérée sur FFBB.
        #
        # Exemple :
        # FFBB = 20h15
        # ICS  = 20260927T201500
        #
        # Aucun TZID.
        # Aucune conversion UTC.
        start_str = start.strftime(
            "%Y%m%dT%H%M%S"
        )

        # Durée de 2 heures, sans modifier l'heure de début.
        end = start.replace(
            hour=start.hour,
            minute=start.minute,
        )

        # On ajoute 2 heures à la durée
        from datetime import timedelta

        end = start + timedelta(hours=2)

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

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

    print()
    print(f"Matchs trouvés : {len(matches)}")
    print()

    if len(matches) < 18:

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
