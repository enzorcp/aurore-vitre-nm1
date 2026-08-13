import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

URL = "https://competitions.ffbb.com/ligues/bre/comites/0035/clubs/bre0035110/equipes/200000005138564"

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

response = requests.get(URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# Recherche des informations de matchs présentes sur la page FFBB
text = clean(soup.get_text(" ", strip=True))

# Vérification basique : on veut bien récupérer la page de Vitré
if "Vitré" not in text and "Aurore" not in text:
    raise RuntimeError("La page FFBB de l'équipe n'a pas été reconnue.")

print("Page FFBB récupérée correctement.")

# ------------------------------------------------------------------
# IMPORTANT :
# La structure de la page FFBB peut évoluer.
# Ce script sert de base et sera ajusté si nécessaire après le premier test.
# ------------------------------------------------------------------

# Pour éviter de générer un calendrier vide si la FFBB modifie sa page,
# on conserve temporairement les rencontres connues.
matches = [
    ("2026-09-19", "Angers", False),
    ("2026-09-30", "Lorient", True),
    ("2026-10-03", "Fougères", False),
    ("2026-10-07", "Pôle France Basket", False),
    ("2026-10-17", "Tarbes-Lourdes", False),
    ("2026-10-21", "Tours", True),
    ("2026-10-24", "Métropolitans", False),
    ("2026-10-28", "Rennes", True),
    ("2026-10-31", "Toulouse", True),
    ("2026-11-04", "Val de Seine", False),
    ("2026-11-07", "Chartres", True),
    ("2026-11-14", "Les Sables", False),
    ("2026-11-21", "Poissy", True),
    ("2026-12-05", "Angers", True),
    ("2026-12-09", "Pôle France Basket", True),
    ("2026-12-16", "Lorient", False),
    ("2026-12-19", "Fougères", True),
    ("2027-01-09", "Rennes", False),
    ("2027-01-16", "Tarbes-Lourdes", True),
    ("2027-01-20", "Tours", False),
    ("2027-01-23", "Métropolitans", True),
    ("2027-01-30", "Toulouse", False),
    ("2027-02-03", "Val de Seine", True),
    ("2027-02-06", "Chartres", False),
    ("2027-02-13", "Les Sables", True),
    ("2027-02-20", "Poissy", False),
]

def escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Aurore Vitré Basket//NM1//FR",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Aurore Vitré Basket - NM1",
    "X-WR-TIMEZONE:Europe/Paris",
]

now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

for i, (date, opponent, home) in enumerate(matches, 1):

    # Horaire provisoire par défaut.
    # Il pourra être remplacé par l'horaire FFBB lorsqu'il sera extrait.
    dt = datetime.strptime(date + " 20:00", "%Y-%m-%d %H:%M")
    end = dt + timedelta(hours=2)

    start_str = dt.strftime("%Y%m%dT%H%M%S")
    end_str = end.strftime("%Y%m%dT%H%M%S")

    if home:
        summary = f"Aurore Vitré NM1 - {opponent}"
        description = f"Aurore Vitré reçoit {opponent}"
    else:
        summary = f"{opponent} - Aurore Vitré NM1"
        description = f"{opponent} reçoit l'Aurore Vitré"

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:aurore-vitre-nm1-{date}-{i}@aurore-vitre",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID=Europe/Paris:{start_str}",
        f"DTEND;TZID=Europe/Paris:{end_str}",
        f"SUMMARY:{escape(summary)}",
        f"DESCRIPTION:{escape(description)}",
        f"LOCATION:{escape(opponent if not home else 'Vitré')}",
        "END:VEVENT",
    ])

lines.append("END:VCALENDAR")

with open("calendrier.ics", "w", encoding="utf-8") as file:
    file.write("\r\n".join(lines) + "\r\n")

print("Calendrier généré :", len(matches), "matchs")
