# A jelenlegi dalkatalógus statisztikája

Forrás: `songs.csv`, amelyet a `streamlit_app.py` betölt. A számok a fájl jelenlegi tartalmát írják le, nem egy adott játék kiválasztott dalait.

- Dalok száma: **1366**
- Különböző előadói mezők száma: **620** (a közreműködők kombinációi külön értékek).
- Évhatárok: **1954–2025**

## Évtizedek

| Évtized | Dal | Arány | Magyar címke | Nemzetközi címke |
|---|---:|---:|---:|---:|
| 1950s | 25 | 1,8% | 1 | 24 |
| 1960s | 111 | 8,1% | 18 | 93 |
| 1970s | 176 | 12,9% | 32 | 144 |
| 1980s | 218 | 16,0% | 44 | 174 |
| 1990s | 226 | 16,5% | 47 | 179 |
| 2000s | 243 | 17,8% | 36 | 207 |
| 2010s | 248 | 18,2% | 21 | 227 |
| 2020s | 119 | 8,7% | 14 | 105 |

## Nyelvi címkék

Az `international` nem konkrét nyelv. Angol, spanyol stb. szerinti pontos megoszlás ebből az adatból nem készíthető. A címkéket nem ellenőriztük a hangfelvételek alapján.

| Címke | Dal | Arány |
|---|---:|---:|
| international | 1153 | 84,4% |
| hu | 213 | 15,6% |

## Stílusok – eredeti címkék

A vegyes címkéket külön kategóriaként számoljuk, így minden dal egyszer szerepel. A Pop / Rock és Rock / Pop külön érték; a Curated nem zenei műfaj. A címkék nem függetlenül ellenőrzött műfaji besorolások.

| Stílus | Dal | Arány |
|---|---:|---:|
| Pop | 496 | 36,3% |
| Rock | 213 | 15,6% |
| Dance | 85 | 6,2% |
| Pop / Rock | 71 | 5,2% |
| Alternative | 59 | 4,3% |
| Hip-hop | 53 | 3,9% |
| Alternative / Rock | 48 | 3,5% |
| Soul / R&B | 30 | 2,2% |
| Alternative / Pop | 23 | 1,7% |
| Pop / R&B | 22 | 1,6% |
| Pop / Hip-hop | 19 | 1,4% |
| Soul / Pop | 17 | 1,2% |
| R&B | 17 | 1,2% |
| Hip-hop / Pop | 16 | 1,2% |
| Rock & Roll | 15 | 1,1% |
| Disco | 14 | 1,0% |
| Folk / Pop | 13 | 1,0% |
| Dance / Pop | 13 | 1,0% |
| Electronic | 13 | 1,0% |
| Rock / Pop | 11 | 0,8% |
| Latin Pop | 11 | 0,8% |
| Pop / Dance | 10 | 0,7% |
| R&B / Pop | 9 | 0,7% |
| Country / Pop | 8 | 0,6% |
| Funk / Pop | 6 | 0,4% |
| Disco / Funk | 5 | 0,4% |
| Rock & Roll / Pop | 5 | 0,4% |
| Hip-hop / R&B | 5 | 0,4% |
| Folk / Rock | 5 | 0,4% |
| Disco / Pop | 4 | 0,3% |
| Pop / Disco | 4 | 0,3% |
| Pop / Funk | 4 | 0,3% |
| Curated | 3 | 0,2% |
| Soul / Funk | 3 | 0,2% |
| Pop / Country | 3 | 0,2% |
| Pop / Soul | 3 | 0,2% |
| Dance / Electronic | 3 | 0,2% |
| Electronic / Pop | 3 | 0,2% |
| Folk | 2 | 0,1% |
| Afrobeats / Pop | 2 | 0,1% |
| Latin / Hip-hop | 2 | 0,1% |
| Country | 2 | 0,1% |
| Alternative / Hip-hop | 2 | 0,1% |
| Dancehall / Pop | 2 | 0,1% |
| Reggae / Pop | 2 | 0,1% |
| Funk | 1 | 0,1% |
| New Wave | 1 | 0,1% |
| Jazz / Pop | 1 | 0,1% |
| Hip-hop / Latin | 1 | 0,1% |
| Hip-hop / Country | 1 | 0,1% |
| Electronic / Dance | 1 | 0,1% |
| Afrobeats / R&B | 1 | 0,1% |
| Afrobeats | 1 | 0,1% |
| Pop / Comedy | 1 | 0,1% |
| Rock / Blues | 1 | 0,1% |

## Adatminőség

- Nincs üres mező a katalógusban.
- Az összes évtizedcímke megfelel az évszámnak.
- Az előadó és cím párosa alapján nincs ismétlődés (kis- és nagybetűtől, szélső szóközöktől eltekintve).
- Két Spotify URI két-két külön sorban szerepel; a felvételek megfelelőségét ellenőrizni kell.

- `spotify:track:49dpGiiE2LKH199LzXGHrA`: Pa-Dö-Dö – Bye-Bye Szása (1990); Pa-Dö-Dö – Bye Bye Szása (1990)
- `spotify:track:5GHY1DFWKz3Prg2V0Iodqo`: Sinéad O'Connor – Nothing Compares 2 U (1990); Sinead O'Connor – Nothing Compares 2 U (1990)

## Az app jelenlegi működése

A betöltés megőrzi az előadót, címet, évet és Spotify URI-t, az évtizedet az évből számítja. A style és language oszlopot jelenleg nem tölti be a SONGS rekordjaiba; stílus- és nyelvi szűréshez ezt bővíteni kell.
