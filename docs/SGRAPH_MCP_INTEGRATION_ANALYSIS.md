# Sgraph MCP Integration: Syvällinen analyysi

Dokumentti kuvaa kaikki vaikeudet ja opitut asiat sgraph-mcp-serverin integroinnissa Claude Codeen.

## Yhteenveto

Integraatio onnistui lopulta, mutta prosessissa kohdattiin useita abstraktiotasojen ongelmia:

1. **MCP-protokollan parametrirakenne** - suurin ongelma
2. **Sgraph-kirjaston API-erot** - dokumentaatio vs. todellisuus
3. **Async/await -kontekstit** - Python asyncio -haasteet
4. **Mallin rakenne** - hierarkian ymmärtäminen

---

## 1. MCP-protokollan parametrirakenne (KRIITTINEN)

### Ongelma

FastMCP käyttää Pydantic-malleja parametrien validointiin. Kun työkalu määritellään näin:

```python
class LoadModelInput(BaseModel):
    path: str

@mcp.tool()
async def sgraph_load_model(input: LoadModelInput):
    ...
```

MCP-protokolla odottaa parametrit **`input`-avaimen alle**:

```json
{"input": {"path": "/path/to/model.xml"}}
```

Mutta intuitiivinen oletus on lähettää:

```json
{"path": "/path/to/model.xml"}
```

### Miksi tämä on ongelma

1. **Dokumentaatio ei kerro tästä selvästi** - FastMCP:n README ei korosta tätä
2. **Virheilmoitus on epäselvä** - "Field required: input" ei kerro mitä tehdä
3. **Claude Code saattaa tehdä tämän automaattisesti** - mutta ei aina

### Ratkaisu

Joko:
- Lähetä parametrit `{"input": {...}}`-rakenteessa
- TAI muuta työkalun signatuuri käyttämään suoria parametreja (ei Pydantic-mallia)

### Opittu

MCP-protokolla on vielä nuori ja käytännöt vaihtelevat. Testaa aina protokollatasolla ennen kuin syytät logiikkaa.

---

## 2. Sgraph-kirjaston API-erot

### Ongelma

Sgraph-kirjaston dokumentaatio ja esimerkit käyttävät eri metodinimiä kuin toteutus:

| Oletettu | Todellinen |
|----------|------------|
| `SGraph.load()` | Ei ole |
| `SGraph.parse_xml()` | Ei ole |
| `model.root` | `model.rootNode` |

### Tutkimuspolku

1. Yritettiin `SGraph.load("file.xml")` → AttributeError
2. Yritettiin `SGraph.parse_xml("file.xml")` → AttributeError
3. Käytettiin `dir(SGraph)` selvittämään oikeat metodit
4. Löydettiin `SGraph.parse_xml_or_zipped_xml()`

### Opittu

Kun kirjaston dokumentaatio on epäselvä:
```python
# Listaa kaikki metodit
for name in dir(SGraph):
    if not name.startswith('_'):
        print(name)
```

---

## 3. Async/Await -kontekstit

### Ongelma

ModelManager.load_model() on async-metodi, mutta tätä ei ole merkitty selvästi:

```python
model_id = mm.load_model(path)  # Palauttaa coroutine, ei model_id:tä!
```

Virheilmoitus:
```
RuntimeWarning: coroutine 'ModelManager.load_model' was never awaited
```

### Korjaus

```python
model_id = await mm.load_model(path)
```

### Opittu

Python-koodissa async-funktiot pitää tunnistaa:
- Tarkista `async def` määrittelyssä
- Jos palautusarvo on `<coroutine object>`, tarvitaan await

---

## 4. Mallin hierarkian ymmärtäminen

### Ongelma

Softagram-malli käyttää hierarkkista polkurakennetta:

```
/TalenomSoftware/Online/talenom.online.invoicepayment5.api/Talenom.Online.InvoicePayment.Api/Controllers
```

Mutta:
- Root-elementillä on tyhjä nimi (`""`)
- Ensimmäinen oikea solmu on `/TalenomSoftware`
- Polut eivät vastaa suoraan tiedostojärjestelmän polkuja

### Tutkimuspolku

```python
root = graph.rootNode
print(f"Root name: '{root.name}'")  # Tyhjä!
print(f"Children: {[c.name for c in root.children]}")  # ['TalenomSoftware']
```

### Opittu

Älä oleta mallin rakennetta - tutki se ensin:
```bash
python3 scripts/structure.py / --depth 2
```

---

## 5. Riippuvuustietojen puutteet

### Ongelma

Impact-analyysi näytti 0 riippuvuutta vaikka niitä piti olla. (Aiemmassa JSON-formaatissa tämä näkyi kenttänä `incoming_count: 0`, nykyisessä plain text -formaatissa `incoming (0): (none)`.)

### Syy

Softagram-malli sisältää eri tarkkuustasoja:
- **Tiedostotaso**: NuGet-paketit, projektireferenssit → mukana
- **Luokkataso**: using-lauseet → mukana
- **Funktiotaso**: metodikutsut → ei aina mukana
- **NuGet-pakettien sisäiset**: ei näy ollenkaan

### Mitä malli sisältää

```python
# Elementin riippuvuudet
for assoc in element.outgoing:
    print(f"{element.name} -> {assoc.toElement.name} ({assoc.deptype})")
```

Tyypilliset `deptype`-arvot:
- `copy`, `from`, `apt` (Docker)
- `import`, `uses` (koodi)
- `project_reference`, `package_reference` (.NET)

### Opittu

Sgraph-malli ei ole kaikkitietävä - se näyttää sen mitä Softagram-analyzer on kerännyt. Tarkista ensin mitä riippuvuuksia on olemassa:

```bash
python3 scripts/deps.py /path/to/element --direction both --json
```

---

## 6. Serverin käynnistysmoodi

### Ongelma

Serveri käynnistyi SSE-modessa kun odotettiin stdio:ta:

```
INFO: Uvicorn running on http://0.0.0.0:8008
```

### Syy

Oletusmoodi on SSE, stdio vaatii eksplisiittisen lipun.

### Korjaus

```bash
uv run python -m src.server --profile claude-code --transport stdio
```

### MCP-konfiguraatiossa

```json
{
  "args": ["run", "python", "-m", "src.server", "--profile", "claude-code", "--transport", "stdio"]
}
```

---

## 7. Skriptien vs. kertakäyttökoodin ero

### Ongelma

Debugatessa tuotettiin paljon kertakäyttöistä Python-koodia heredoc-blokeissa, mikä:
- Täyttää kontekstin
- Ei ole uudelleenkäytettävää
- Vaikea lukea

### Ratkaisu

Luotiin uudelleenkäytettävät skriptit:
- `sgraph_client.py` - yhteinen kirjasto
- `search.py`, `structure.py`, `deps.py`, `impact.py` - CLI-työkalut

### Opittu

Kun debuggaat uutta integraatiota:
1. **Ensimmäinen iteraatio**: Kertakäyttökoodi ok tutkimiseen
2. **Kun ymmärrät rakenteen**: Tee skriptit
3. **Dokumentoi**: Kirjoita troubleshooting-guide

---

## Aikajana

| Vaihe | Aika | Ongelma |
|-------|------|---------|
| 1 | 0-10 min | Serverin käynnistys, SSE vs stdio |
| 2 | 10-20 min | Sgraph API:n selvittäminen |
| 3 | 20-30 min | Mallin lataus, async-ongelmat |
| 4 | 30-45 min | Hakutulokset tyhjiä - parametrirakenne |
| 5 | 45-55 min | MCP input-wrapper löytyi |
| 6 | 55-65 min | Toimivuuden varmistus |
| 7 | 65-80 min | Skriptien luonti |

**Kokonaisaika:** ~80 minuuttia

**Suurin ajansyöppö:** Parametrirakenteen selvittäminen (~25 min)

---

## Suositukset tulevaisuuteen

### 1. MCP-integraatioiden testaus

Luo aina testiskripti joka:
```python
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(tools)  # Varmista että työkalut näkyvät
```

### 2. Parametrien rakenne

Jos työkalu ei toimi, testaa molemmat:
```python
{"param": "value"}           # Suora
{"input": {"param": "value"}} # Wrapattuna
```

### 3. Dokumentoi heti

Kun löydät ratkaisun, kirjoita se ylös ennen kuin unohdat miksi se toimi.

---

## Lopputulos

Sgraph MCP toimii nyt:
- ✅ Malli latautuu (~20s, 376 MB)
- ✅ Haku toimii (TOON-muoto)
- ✅ Rakenne-navigointi toimii
- ✅ Riippuvuuskyselyt toimivat
- ⚠️ Impact-analyysi rajoitettu (mallin tarkkuustaso)

Skriptit käytettävissä: `/mnt/c/code/sgraph-mcp-server/scripts/`
