import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

BASE_URL = "https://competitions.ffbb.com/competitions/nm1"
PHASE = "200000002897178"
POULE = "200000003054369"

TEAM = "AURORE VITRE BASKET BRETAGNE"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

TZ = ZoneInfo("Europe/Paris")


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_page(journee):
    url = (
        f"{BASE_URL}"
        f"?journee={journee}"
        f"&phase={PHASE}"
        f"&poule={POULE}"
    )

    print(f"Lecture journée {journee}: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    text = clean(
        soup.get_text(" ", strip=True)
    )

    # Recherche de la date/heure de la journée
    date_match = re.search(
        r"(\d{1,2})\s+"
        r"(janvier|février|mars|avril|mai|juin|"
        r"juillet|août|septembre|octobre|novembre|décembre)"
        r"\s+2026\s+"
        r"(\d{1,2}:\d{2})",
        text,
        re.IGNORECASE
    )

    if not date_match:
        print("Date non trouvée")
        return None

    jour = int(date_match.group(1))
    mois_nom = date_match.group(2).lower()
    heure = date_match.group(3)

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
        "décembre": 12
    }

    dt = datetime(
        2026,
        mois[mois_nom],
        jour,
        int(heure[:2]),
        int(heure[3:]),
        tzinfo=TZ
    )

    # On cherche la zone contenant le match de Vitré
    pos = text.upper().find(TEAM)

    if pos == -1:
        print("Match de Vitré non trouvé")
        return None

    # On prend le texte autour du match
    contexte = text[
        max(0, pos - 500):
        pos + 500
    ]

    print("Match trouvé :", contexte)

    # Détection domicile / extérieur
    avant = contexte[:contexte.upper().find(TEAM)]
    apres = contexte[
        contexte.upper().find(TEAM) + len(TEAM):
    ]

    # Noms possibles d'adversaires
    equipes = [
        "UNION RENNES BASKET 35 (URB 35)",
        "ETOILE ANGERS BASKET",
        "TOURS METROPOLE BASKET",
        "LES SABLES VENDEE BASKET",
        "C’CHARTRES METROPOLE BASKET",
        "C'CHARTRES METROPOLE BASKET",
        "UNION TARBES LOURDES PYRENEES BASKET",
        "JSA BORDEAUX METROPOLE BASKET",
        "VENDEE CHALLANS BASKET",
        "PAYS DE FOUGERES BASKET",
        "CEP LORIENT BREIZH BASKET",
        "US LAVAL BASKET",
        "TOULOUSE BASKETBALL CLUB",
        "VAL DE SEINE BASKET",
        "POISSY BASKET ASSOCIATION",
        "LEVALLOIS METROPOLITANS BASKETBALL CLUB",
        "POLE FRANCE BASKETBALL"
    ]

    adversaire = None

    for equipe in equipes:
        if equipe in avant.upper():
            adversaire = equipe
            domicile = False

        if equipe in apres.upper():
            adversaire = equipe
            domicile = True

    if not adversaire:
        print("Adversaire non identifié")
        return None

    if domicile:
        summary = (
            f"Aurore Vitré NM1 - {adversaire}"
        )
    else:
        summary = (
            f"{adversaire} - Aurore Vitré NM1"
        )

    return {
        "journee": journee,
        "date": dt,
        "summary": summary,
        "adversaire": adversaire,
        "domicile": domicile
    }


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
        end = start + timedelta(hours=2)

        start_str = start.strftime(
            "%Y%m%dT%H%M%S"
        )

        end_str = end.strftime(
            "%Y%m%dT%H%M%S"
        )

        uid = (
            f"aurore-vitre-nm1-"
            f"{match['journee']}-"
            f"{start_str}@github"
        )

        location = (
            "Salle de la Poultière, Vitré"
            if match["domicile"]
            else match["adversaire"]
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"DTSTART;TZID=Europe/Paris:{start_str}",
            f"DTEND;TZID=Europe/Paris:{end_str}",
            f"SUMMARY:{escape(match['summary'])}",
            f"LOCATION:{escape(location)}",
            f"DESCRIPTION:NM1 2026-2027 - Journée {match['journee']}",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")

    return "\r\n".join(lines) + "\r\n"


def main():

    matches = []

    for journee in range(1, 27):

        try:
            match = parse_page(journee)

            if match:
                matches.append(match)

        except Exception as error:
            print(
                f"Erreur journée {journee}: {error}"
            )

    print()
    print(
        f"{len(matches)} match(s) trouvé(s)"
    )

    if len(matches) < 10:
        raise RuntimeError(
            "Trop peu de matchs trouvés. "
            "Le calendrier n'a pas été généré."
        )

    matches.sort(
        key=lambda x: x["date"]
    )

    ics = generate_ics(matches)

    with open(
        "calendrier.ics",
        "w",
        encoding="utf-8"
    ) as file:
        file.write(ics)

    print(
        "calendrier.ics généré avec succès."
    )


if __name__ == "__main__":
    main()
