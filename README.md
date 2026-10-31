# Alvert.se – reklamfri kopia

Hämtar alla inlägg och bilder från alvert.se (blogg.se) och publicerar dem som en egen,
reklamfri blogg på Cloudflare. Adresserna är desamma som på blogg.se, så gamla länkar fungerar.

## Så fungerar det

1. `scraper/scrape.py` hämtar alla inlägg och sparar dem som JSON i `data/posts/`.
   Bara rubrik, datum, kategorier, text och bilder sparas. Reklam och kommentarer följer inte med.
2. `scraper/images.py` kopierar bilderna till R2-bucketen `alvert-bilder`.
3. `scraper/build.py` bygger den statiska sajten i `dist/`.
4. En Cloudflare Worker (`worker/index.js`) serverar sidorna och bilderna.

## Förberedelser (en gång)

**1. Gör repot privat.** Settings → General → Danger Zone → Change visibility.

**2. Skapa R2-bucketen.** I Cloudflare: R2 Object Storage → Create bucket → namn `alvert-bilder`.

**3. Skapa en R2-nyckel.** R2 Object Storage → Manage API tokens → Create API token.
   Välj *Object Read & Write*, begränsa till bucketen `alvert-bilder`.
   Spara *Access Key ID* och *Secret Access Key*.

**4. Skapa en Cloudflare API-token.** My Profile → API Tokens → Create Token →
   mallen *Edit Cloudflare Workers*.

**5. Hitta ditt konto-ID.** Det står i högerspalten på översiktssidan i Cloudflare
   (eller under Workers & Pages).

**6. Lägg in fyra secrets i GitHub.** Repo → Settings → Secrets and variables → Actions → New repository secret:

| Namn | Värde |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | konto-ID från steg 5 |
| `CLOUDFLARE_API_TOKEN` | token från steg 4 |
| `R2_ACCESS_KEY_ID` | från steg 3 |
| `R2_SECRET_ACCESS_KEY` | från steg 3 |

## Köra

Actions → *Hämta och publicera bloggen* → Run workflow.

- **Först en testkörning** med `limit` = `5`. Öppna sedan sajten på adressen som visas
  sist i loggen (`alvert.<ditt-namn>.workers.dev`) och kontrollera att inläggen ser rätt ut.
- **Sedan hela bloggen** med `limit` = `0`. Det tar ungefär en till två timmar.
  Om körningen avbryts sparas det som hunnit hämtas, och nästa körning fortsätter där den slutade.

## Om något ser fel ut

Kör lokalt för att se exakt vad som plockas ut ur ett inlägg:

```
pip install -r requirements.txt
python scraper/scrape.py --debug https://alvert.se/2021/july/hon-har-ett-namn.html
```

Ändrar man tolkningen i `scrape.py` hämtar man om allt med `refresh` ikryssat.

Bilder som inte gick att hämta listas i `data/saknade-bilder.txt`.

## Egen domän

När kopian är klar: Workers & Pages → `alvert` → Settings → Domains & Routes → Add custom domain.
Domänen måste då ligga i ditt Cloudflare-konto, och den behöver flyttas bort från blogg.se.
