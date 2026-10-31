# Alvert.se – reklamfri kopia

Hämtar alla inlägg och bilder från alvert.se (blogg.se) och publicerar dem som en egen,
reklamfri blogg på GitHub Pages: **https://valfrid.github.io/alvert/**

Adresserna följer blogg.se, t.ex. `/2021/july/hon-har-ett-namn.html`.

## Så fungerar det

1. `scraper/scrape.py` hämtar alla inlägg och sparar dem som JSON i `data/posts/`.
   Bara rubrik, datum, kategorier, text, bilder och YouTube-klipp sparas.
   Reklam, delningsknappar och kommentarer följer inte med.
2. `scraper/images.py` laddar ner bilderna och krymper de största till 1400 px breda.
   Bilderna sparas i GitHubs cache mellan körningarna, inte i repot.
3. `scraper/build.py` bygger sajten i `dist/`, som publiceras på GitHub Pages.

## Förberedelser (en gång)

Settings → Pages → under *Build and deployment*, välj **Source: GitHub Actions**.

(GitHub Pages kräver att repot är publikt om du har ett gratiskonto.)

## Köra

Actions → *Hämta och publicera bloggen* → Run workflow.

- **Först en testkörning** med `limit` = `5`, och titta på https://valfrid.github.io/alvert/
- **Sedan hela bloggen** med `limit` = `0`. Det tar ungefär en till två timmar.
  Om körningen avbryts sparas det som hunnit hämtas, och nästa körning fortsätter där den slutade.

## Om något ser fel ut

Ändrar man tolkningen i `scrape.py` hämtar man om allt med `refresh` ikryssat.
Bilder som inte gick att hämta listas i `data/saknade-bilder.txt` och länkas i stället till blogg.se.

GitHub Pages tillåter högst 1 GB per sajt. Byggsteget skriver ut storleken och varnar om den närmar sig gränsen.

## Senare: Cloudflare och egen domän

Innehållet i `dist/` kan senare publiceras på Cloudflare i stället, med domänen alvert.se.
