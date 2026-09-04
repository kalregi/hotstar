import csv
import html
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SOURCES = [
    {
        "url": "https://bopster.app/en/playlist?id=5288",
        "kind": "international",
        "max_take": 820,
    },
    {
        "url": "https://bopster.app/en/playlist?id=2748",
        "kind": "hungary",
        "max_take": 400,
    },
]

OUTPUT = "hitster_1000_curated.csv"
TARGET = 1000

# Ezeket direkt nem szeretném a pakliban.
BLOCKED_ARTISTS = {
    "retrofile",
}

# Tipikus nem-játékbarát verziók.
BLOCKED_TITLE_BITS = [
    "karaoke",
    "tribute",
    "workout",
    "sped up",
    "slowed",
    "nightcore",
]

# A magyar forrásban sok nemzetközi szám is van.
# Ezekkel a nevekkel biztosan magyar címkét kap a dal.
HUNGARIAN_ARTISTS = {
    "omega", "illes", "illés", "koncz zsuzsa", "zalatnay sarolta",
    "sarolta zalatnay", "locomotiv gt", "lgt", "presser gabor",
    "presser gábor", "zoran", "zorán", "mate peter", "máté péter",
    "szecsi pal", "szécsi pál", "korda gyorgy", "korda györgy",
    "neoton familia", "neoton família", "hungaria", "hungária",
    "kft", "edda művek", "edda muvek", "bikini", "beatrice",
    "demjen ferenc", "demjén ferenc", "ferenc demjén", "r-go", "r go",
    "zoltan erika", "zoltán erika", "bonanza banzai", "akos", "ákos",
    "pa-dö-dö", "pa-do-do", "republic", "zambo jimmy", "zámbó jimmy",
    "amokfutok", "ámokfutók", "emergency house", "carpe diem", "tnt",
    "soho party", "tankcsapda", "united", "groovehouse", "nox",
    "hooligans", "quimby", "magna cum laude", "fluor", "punnany massif",
    "majka", "curtis", "wellhello", "halott pénz", "halott penz",
    "bagossy brothers company", "azahriah", "desh", "follow the flow",
    "ruzsa magdolna", "rúzsa magdolna", "byealex és a slepp",
    "byealex es a slepp", "kelemen kabátban", "kelemen kabatban",
    "konyha", "napoleon boulevard", "pokolgép", "pokolgep", "ossian",
    "hip hop boyz", "v-tech", "crystal", "fiesta", "caramel",
    "molnár ferenc caramel", "molnar ferenc caramel", "krisz rudolf",
    "olah ibolya", "oláh ibolya", "ibolya oláh", "valmar", "zanzibár",
    "zanzibar", "rapülök", "rapulok", "happy gang", "baby sisters",
    "baby gabi", "4f-club", "ufo", "ihász gábor", "ihasz gabor",
    "karthago", "wolf kati", "beton.hofi", "pápai joci", "papai joci",
    "császár előd", "csaszar elod", "szandi", "cserháti zsuzsa",
    "cserhati zsuzsa", "kovács kati", "kovacs kati", "katona klári",
    "katona klari", "szűcs judit", "szucs judit", "fenyő miklós",
    "fenyo miklos", "bon-bon", "hevesi tamás", "hevesi tamas",
}


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def norm(text):
    text = clean(text).lower()
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ö": "o",
        "ő": "o", "ú": "u", "ü": "u", "ű": "u",
    }
    for a, b in replacements.items():
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def strip_version(title):
    # A cím marad felismerhető, de a remaster/radio edit sallangot levágjuk
    # csak a deduplikáláshoz.
    t = norm(title)
    for bit in [
        "remastered", "remaster", "radio edit", "single edit",
        "single version", "album version", "2011 remaster",
        "2012 remaster", "2013 remaster", "2015 remaster",
        "2018 remaster", "2001 remaster", "2002 remaster",
        "2004 remaster", "2009 remaster", "2022 remaster",
    ]:
        t = t.replace(bit, " ")
    return " ".join(t.split())


def decade(year):
    return f"{(year // 10) * 10}s"


def looks_hungarian(artist):
    a = norm(artist)
    return any(norm(x) in a or a in norm(x) for x in HUNGARIAN_ARTISTS)


def parse_bopster(url):
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n")

    lines = [clean(x) for x in text.splitlines()]
    lines = [x for x in lines if x]

    try:
        start = lines.index("Tracklist") + 1
    except ValueError:
        raise RuntimeError(f"Nem találom a Tracklist részt: {url}")

    rows = []
    i = start

    # Bopster mintázat:
    # sorszám
    # cím
    # előadó (év)
    while i < len(lines) - 2:
        if re.fullmatch(r"\d+", lines[i]):
            title = lines[i + 1]
            artist_year = lines[i + 2]

            m = re.match(r"^(.*?)\s+\((\d{4})\)$", artist_year)

            if m:
                artist = clean(m.group(1))
                year = int(m.group(2))

                rows.append({
                    "artist": artist,
                    "title": title,
                    "year": year,
                })
                i += 3
                continue

        i += 1

    return rows


def acceptable(row):
    if norm(row["artist"]) in BLOCKED_ARTISTS:
        return False

    title_low = row["title"].lower()

    if any(x in title_low for x in BLOCKED_TITLE_BITS):
        return False

    if not (1950 <= row["year"] <= 2026):
        return False

    return True


def key(row):
    # fő előadó + verzióktól megtisztított cím
    artist = re.split(
        r"\s*(?:feat\.?|ft\.?|&|,)\s*",
        row["artist"],
        maxsplit=1,
        flags=re.I,
    )[0]

    return norm(artist), strip_version(row["title"])


def main():
    pool = []

    for source in SOURCES:
        print(f"Letöltés: {source['url']}")
        rows = parse_bopster(source["url"])
        print(f"  talált dalok: {len(rows)}")

        taken = 0

        for row in rows:
            if not acceptable(row):
                continue

            row["source_kind"] = source["kind"]
            pool.append(row)
            taken += 1

            if taken >= source["max_take"]:
                break

    # Első forrás prioritást kap, majd a magyar lista tölti ki.
    unique = []
    seen = set()

    for row in pool:
        k = key(row)

        if k in seen:
            continue

        seen.add(k)
        unique.append(row)

    # Először az international forrásból jön a gerinc,
    # de a magyar forrásból a magyar előadókat előrébb vesszük.
    international = [
        r for r in unique
        if r["source_kind"] == "international"
    ]

    hungarian_source = [
        r for r in unique
        if r["source_kind"] == "hungary"
        and looks_hungarian(r["artist"])
    ]

    hungary_other = [
        r for r in unique
        if r["source_kind"] == "hungary"
        and not looks_hungarian(r["artist"])
    ]

    final = []
    final_seen = set()

    def add_rows(rows):
        for row in rows:
            if len(final) >= TARGET:
                return

            k = key(row)

            if k in final_seen:
                continue

            final_seen.add(k)
            final.append(row)

    # Kb. 75–80% széles nemzetközi Hitster gerinc.
    add_rows(international[:780])

    # Utána minden használható magyar sláger.
    add_rows(hungarian_source)

    # Ha még nincs 1000, a Hungary listában szereplő további
    # közismert nemzetközi dalokkal töltjük ki.
    add_rows(hungary_other)

    if len(final) < TARGET:
        raise RuntimeError(
            f"Csak {len(final)} egyedi dalt sikerült összerakni. "
            "Nem írok ki mesterségesen duplikált sorokat."
        )

    final = final[:TARGET]

    output_rows = []

    for row in final:
        is_hu = looks_hungarian(row["artist"])

        output_rows.append({
            "artist": row["artist"],
            "title": row["title"],
            "year": row["year"],
            "decade": decade(row["year"]),
            "style": "Mixed",  # ezt a következő körben finomítjuk
            "language": "hu" if is_hu else "international",
            "spotify_uri": "",
            "year_needs_review": "yes",
        })

    with open(
        OUTPUT,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "artist",
                "title",
                "year",
                "decade",
                "style",
                "language",
                "spotify_uri",
                "year_needs_review",
            ],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    hu_count = sum(
        row["language"] == "hu"
        for row in output_rows
    )

    print()
    print("==============================")
    print("KÉSZ")
    print("==============================")
    print(f"Dalok: {len(output_rows)}")
    print(f"Magyar előadó: {hu_count}")
    print(f"Nemzetközi: {len(output_rows) - hu_count}")
    print(f"Fájl: {OUTPUT}")
    print()
    print(
        "A Spotify URI-k szándékosan üresek. "
        "A következő lépésben külön resolver tölti ki őket."
    )


if __name__ == "__main__":
    main()
