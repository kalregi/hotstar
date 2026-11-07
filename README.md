# 🎈 Blank app template

### Játék visszakeresése és lezárása hostként

A kezdőképernyő „HOST / JÁTÉKOK” fülén a meglévő host jelszóval
lekérhetők a folyamatban lévő és utolsó körös játékok. A lista tartalmazza
a játékkódot, csapatneveket, pontszámokat és a DJ utolsó kapcsolódásának
budapesti idejét. A megszakadt DJ-kapcsolatú játékok is megjelennek.

A „FOLYTATÁS DJ-KÉNT” gomb visszatölti a játékállapotot, és átveszi a
DJ-szerepet, játékkód beírása nélkül. A „Lezárás” menüben külön
megerősítéssel zárható le egy játék. A lezárás megőrzi az adatokat, de
`closed` állapotot állít be, és megszünteti a DJ-hozzárendelést. Az ilyen
játék eltűnik a folyamatban lévők közül, nem csatlakozható újra, és a
csatlakozott böngészők a következő állapotfrissítéskor lezárási üzenetet kapnak.

A jelszót minden lista-, visszacsatlakozási és lezárási művelet szerveroldalon
ellenőrzi. A lezárás és visszacsatlakozás csak továbbra is aktív játékra
alkalmazható, így az időközben lezárt játékot nem nyitják meg újra.

### Spotify-lejátszás

Az app az aktív, vezérelhető Spotify-eszközt célozza meg, és az albumot
a kiválasztott dal URI-jára pozicionálva indítja. Ez megkerüli azt az
asztali Spotify-hibát, amikor a közvetlen dalindítás sikeres API-válasz
ellenére csak leállítja a korábbi zenét. Az app a lejátszási állapotból
ellenőrzi, hogy tényleg a kért dal indult el a megfelelő eszközön.
Aktív eszköz hiányában először kézzel kell elindítani egy dalt a Spotifyban.

A DJ nyitva tartott játékoldala a dal végén megakadályozza az album
további dalainak folytatását. A meglévő 1,5 másodperces frissítési ciklus
miatt a következő dal röviden megszólalhat. Bezárt vagy felfüggesztett DJ
böngészőlap esetén ez a leállítás nem garantált.

### Dalok nehézsége

A `songs.csv` minden sora saját `difficulty` értéket kapott:

- **1 – Könnyű:** széles körben ismert, több generációban vagy bulikból,
  rádióból könnyen felismerhető sláger.
- **2 – Közepes:** ismert dal, de a felismerése inkább generációtól,
  műfaji érdeklődéstől vagy rendszeres zenehallgatástól függ.
- **3 – Nehéz:** a magyar, vegyes generációjú játékosközönség számára
  várhatóan kevésbé ismert, szűkebb rajongói vagy műfaji körhöz kötődő dal.

A besorolás dalonkénti szerkesztői becslés, nem Spotify-hallgatottsági
adat, és nem az évszám kitalálásának nehézségét méri. Az előadó, az év
vagy a műfaj önmagában nem határozza meg a szintet. A címkék a későbbi
játékostapasztalatok alapján módosíthatók. A betöltés megőrzi a nehézséget.

Részletes összesítés: [reports/difficulty_statistics.md](reports/difficulty_statistics.md).

### Nehézség és nyelv kiválasztása

Az Új játék képernyő Nehézség mezőjében egy, kettő vagy mindhárom szint
kijelölhető. Üresen hagyva minden szint elérhető. A Nyelv / dalkör mezőben
Magyar és Nemzetközi választható; üres választás vagy mindkettő kijelölése
a teljes nyelvi kínálatot engedélyezi. A Nemzetközi nem konkrét nyelv:
a katalógus minden nem magyar címkéjét együtt kezeli.

A stílus, a nehézség és a nyelv szűrői egyszerre érvényesülnek. Egy mezőn
belül bármely kijelölt érték elegendő. Az évtizedenkénti kínálat és a
csúszkák az összes szűrőhöz igazodnak. A kezdőkártyák és a visszavágók is
ezeket a feltételeket követik, a DJ visszacsatlakozása után is. A korábbi
játékok hiányzó nehézség- és nyelvbeállítása korlátozás nélküli választás.

### Stílusválasztás

Az Új játék képernyőn a Zenei stílusok mező több stílust is elfogad.
Az induló képernyőn a host jelszó, a csapatok száma és a négy eloszlásgomb
közvetlenül látható. A stílus-, nehézség- és nyelvválasztó a „Stílus,
nehézség és nyelv”, a csúszkák a „Részletes évtizedes eloszlás” panelben
találhatók; mindkét panel alapból összecsukott. Az eloszlásgombok csukott
panelen is beállítják a csúszkákat.

Üres választásnál a teljes katalógusból válogat az app. Több választásnál
elég az egyik stílus egyezése: a Pop / Rock dal Pop és Rock / Alternative
játékban is szerepelhet. A hét választható csoport:

- Pop
- Rock / Alternative (Rock & Roll, New Wave és Blues is)
- Dance / Electronic / Disco
- Hip-hop
- Soul / R&B / Funk
- Egyéb (Folk, Country, Latin Pop, Latin, Afrobeats, Dancehall, Reggae,
  Comedy, Jazz, valamint a besorolatlan vagy csak Curated címkéjű dalok)
- Karácsonyi slágerek

Egy dal több csoportba is tartozhat, de egy csoporton belül és a játék
dalainak kiválasztásakor csak egyszer szerepel. A korábban elmentett,
részletes stílusokat használó játékok szűrése továbbra is működik.

Az évtizedenkénti csúszkák a szűrt kínálathoz igazodnak. Ha a kínálat
csökken, a korábban megadott darabszámot az app szükség esetén csökkenti;
bővüléskor a mennyiségeket kézzel lehet emelni. A kezdőkártyák és a
visszavágó dalai is a választott stílusokból kerülnek ki.

A csúszkák közös skálát használnak, amelynek maximuma a legnagyobb,
aktuális szűrők után elérhető évtizedes dalkészlet. Így ugyanannyi dal
minden évtizednél ugyanolyan hosszú kijelölt sávot jelent. A helyi kínálat
feletti szakasz szürke és sávozott; oda húzva a csúszka elengedéskor a
helyi maximumra áll vissza. Az üres évtizedek csúszkája letiltva látható.
Teljesen üres kínálatnál a letiltott csúszkák technikai skálája 0–1,
és minden kiválasztott érték 0 marad.

Az évtizedek fölött a Régebbi, Alapértelmezett és Újabb gomb előre
beállított eloszlást alkalmaz; az Összes gomb kikapcsolja az évtizedes kvótákat.
Az értékek sorrendje az 1950-es évektől a 2020-as évekig tart:

| Beállítás | 1950 | 1960 | 1970 | 1980 | 1990 | 2000 | 2010 | 2020 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Régebbi | 10 | 20 | 30 | 25 | 15 | 10 | 5 | 0 |
| Alapértelmezett | 5 | 10 | 15 | 20 | 20 | 20 | 15 | 10 |
| Újabb | 0 | 5 | 10 | 15 | 20 | 30 | 25 | 15 |

A Régebbi és az Alapértelmezett 115, az Újabb 120 dalt céloz; a stílus, nehézség és nyelv szűrése után
elérhető mennyiségnél egyik évtizedből sem választ többet. A hiányt nem
osztja át más évtizedekre. A gombok felülírják a csúszkák aktuális
értékeit; utána ezek kézzel tovább módosíthatók.

Az Összes módban minden, a stílus-, nehézség- és nyelvszűrőknek megfelelő
dal bekerül, véletlen sorrendben. A letiltott csúszkák az aktuális kínálatot
mutatják, és a szűrők módosítását is követik. A mód a visszavágóhoz is
elmentődik. Másik eloszlásgomb visszaállítja a kézzel állítható csúszkákat.

A beállítások a meglévő Supabase `teams` JSON mezőben, az egyik csapat
`game_settings` értékében maradnak meg, így DJ-visszacsatlakozáskor és a
csapatok sorrendjének változásakor is visszatölthetők. Nincs szükség
adatbázisséma-módosításra.

### Karácsonyi válogatás

A Karácsonyi slágerek csoport 150 Spotify-felvételt tartalmaz: 20 magyart
és 130 nemzetközit. Ez szerkesztett válogatás, nem hivatalos világranglista;
néhány klasszikus több előadó változatában szerepel. A korábbi Last Christmas
címkét kapott, ezért 149 új sor került a katalógusba, amely így 1515 soros.
Az új felvételek csak a karácsonyi csoportot kapják; a korábbi dal eredeti
stílusa megmarad. Üres stílusválasztásnál a karácsonyi dalok is elérhetők.

- Forráslista: `christmas_catalog.csv`
- Spotify-találatok, metaadatok és egyezési pontszámok: `reports/christmas_spotify_matches.csv`
- Teljes, Spotify-linkes lista és összesítés: [reports/christmas_catalog.md](reports/christmas_catalog.md)

A kereső a korábbi Spotify-resolverek normalizálását használja, a helyi
`.streamlit/secrets.toml` Spotify-beállításaival. Az eredményt minden dal
után menti; az újrafuttatás a kész találatokat kihagyja. A katalógusba csak
akkor importál, ha mind a 150 felvételhez elfogadott, különböző URI tartozik:

```sh
.venv/bin/python scripts/import_christmas.py --resolve
.venv/bin/python scripts/import_christmas.py --merge
```

Az import ismételhető, és a meglévő dalok adatait megőrzi. Az év a választott
előadó változatának szerkesztett megjelenési éve; a Spotify újrakiadási
albumdátuma külön adat. Azonos című újrafelvételek végleges ellenőrzéséhez
meghallgatás vagy kiadói felvételadat szükséges. A nehézség itt is
szerkesztői ismertségi becslés.

### A ’90-es évek rock/alternatív bővítése

A `rock_90s_catalog.csv` 60 új felvételt tartalmaz (50 nemzetközi, 10 magyar),
Spotify URI-val és nehézségi besorolással. A ’90-es évek Rock / Alternative
kínálata 65-ről 125 dalra, a teljes katalógus 1575 sorra bővült. A korábban
meglévő sorok nem változtak.

A kereső a közös Spotify-resolverre épül; megőrzi a találatokat és csak
akkor importál, ha mind a 60 felvétel azonosítása sikeres:

```sh
.venv/bin/python scripts/import_90s_rock.py --resolve
.venv/bin/python scripts/import_90s_rock.py --merge
```

[Teljes új lista, Spotify-linkek és ellenőrzési támpontok](reports/rock_90s_expansion.md).
A találatok metaadatai: `reports/rock_90s_spotify_matches.csv`.

A katalógus- és játéklogika tesztjei külső szolgáltatások nélkül futtathatók:

```sh
python3 -m unittest discover -s tests -v
```

A simple Streamlit app template for you to modify!

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/)

### How to run it on your own machine

Prerequisite: install `uv` if you don't already have it.

```
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Sync the dependencies

   ```
   $ uv sync
   ```

2. Run the app

   ```
   $ uv run streamlit run streamlit_app.py
   ```
