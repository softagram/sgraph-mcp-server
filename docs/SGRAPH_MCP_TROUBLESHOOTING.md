# Sgraph MCP Troubleshooting Guide

Käytännön vinkit ja ratkaisut yleisiin ongelmiin.

## Pikaohje: Toimivuuden tarkistus

```bash
cd /mnt/c/code/sgraph-mcp-server
source .venv/bin/activate

# Testaa suoraan
python3 scripts/search.py CompanyIdentity --max 5

# Jos toimii, näet tuloksia ~25 sekunnin kuluttua (mallin lataus)
```

## Yleisimmät ongelmat

### 1. "Field required: input"

**Oire:**
```
Error executing tool sgraph_load_model: 1 validation error for sgraph_load_modelArguments
input
  Field required [type=missing, input_value={'path': '...'}, ...]
```

**Syy:** MCP-protokolla vaatii parametrit `input`-avaimen alle.

**Ratkaisu:** Parametrit pitää lähettää näin:
```python
# VÄÄRIN
await session.call_tool("sgraph_load_model", {"path": "/path/to/model.xml"})

# OIKEIN
await session.call_tool("sgraph_load_model", {"input": {"path": "/path/to/model.xml"}})
```

**Huom:** Claude Code MCP-integraatio saattaa hoitaa tämän automaattisesti - tarkista serverin logit.

---

### 2. Tyhjät hakutulokset

**Oire:** Haku palauttaa `0/0 matches` (tai legacy-profiilissa `{"results": [], "count": 0}`)

**Mahdolliset syyt:**

1. **Model_id puuttuu tai on väärä**
   - Varmista että malli on ladattu ja model_id on oikea
   - Model_id on session-kohtainen

2. **Hakupattern ei täsmää**
   - Käytä regex-syntaksia: `.*Manager.*` ei `*Manager*`
   - Case-insensitive: `(?i)invoice`

3. **Scope_path virheellinen**
   - Polun pitää olla täsmälleen oikein
   - Tarkista polku ensin: `scripts/structure.py /TalenomSoftware`

---

### 3. Serveri ei vastaa

**Oire:** Timeout tai ei yhteyttä

**Tarkistukset:**

```bash
# SSE-serverin tila
curl -s http://localhost:8008/health

# Onko prosessi käynnissä
ps aux | grep "sgraph-mcp-server" | grep -v grep

# Tapa ja käynnistä uudelleen
pkill -f "sgraph-mcp-server"
cd /mnt/c/code/sgraph-mcp-server
uv run python -m src.server --profile claude-code
```

---

### 4. Mallin lataus epäonnistuu

**Oire:** "File not found" tai timeout

**Tarkistukset:**

```bash
# Tiedosto olemassa?
ls -la /mnt/c/code/dependency-and-configuration-analyzer/analysis_model.xml

# Tiedoston koko (pitäisi olla ~376 MB)
du -h /mnt/c/code/dependency-and-configuration-analyzer/analysis_model.xml
```

**Latausaika:** Normaali latausaika on 20-25 sekuntia 376 MB mallille.

---

### 5. Impact-analyysi näyttää 0 riippuvuutta

**Oire:** `incoming (0): (none)` vaikka riippuvuuksia pitäisi olla (legacy-profiilissa `incoming_count: 0`)

**Syy:** Softagram-malli ei välttämättä sisällä kaikkia riippuvuustasoja:
- Tiedostotason riippuvuudet (import/using) - yleensä mukana
- Funktiotason riippuvuudet (kutsut) - vaatii syvemmän analyysin
- NuGet-pakettien sisäiset riippuvuudet - ei näy

**Ratkaisu:** Käytä `deps.py` ja tarkista eri tasoilla:
```bash
python3 scripts/deps.py /path/to/element --direction incoming --level 4
python3 scripts/deps.py /path/to/element --direction incoming  # raw level
```

---

## Hyödylliset polut

| Resurssi | Polku |
|----------|-------|
| Sgraph MCP Server | `/mnt/c/code/sgraph-mcp-server` |
| Analyysimalli | `/mnt/c/code/dependency-and-configuration-analyzer/analysis_model.xml` |
| Skriptit | `/mnt/c/code/sgraph-mcp-server/scripts/` |
| InvoicePayment API | `/TalenomSoftware/Online/talenom.online.invoicepayment5.api` |
| Talenom.Utilities | `/TalenomSoftware/Talenom.Utilities/talenom.utils.dotnet.core` |

---

## Skriptien käyttö

```bash
cd /mnt/c/code/sgraph-mcp-server
source .venv/bin/activate

# Hae elementtejä
python3 scripts/search.py ".*Service.*" --type class --max 20

# Näytä rakenne
python3 scripts/structure.py /TalenomSoftware/Online --depth 1

# Riippuvuudet
python3 scripts/deps.py /path/to/element --direction outgoing

# Vaikutusanalyysi
python3 scripts/impact.py /path/to/element
```

---

## MCP-konfiguraatio

Tiedosto: `/mnt/c/code/talenom.online.invoicepayment5.api/.mcp.json`

```json
{
  "mcpServers": {
    "sgraph": {
      "command": "uv",
      "args": ["run", "--project", "/mnt/c/code/sgraph-mcp-server",
               "python", "-m", "src.server",
               "--profile", "claude-code", "--transport", "stdio"],
      "cwd": "/mnt/c/code/sgraph-mcp-server"
    }
  }
}
```

**Huom:** `--transport stdio` on kriittinen Claude Code -integraatiolle.
