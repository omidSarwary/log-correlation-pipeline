Här är en strukturerad plan för projektet **Multi-Platform Log Correlation Pipeline**, utformad enligt den professionella metodik och det utvecklingsflöde som beskrivs i kursmaterialet.

### **1. Planering (Utvecklingsflöde)**

Enligt kursens metodik ska varje automationsprojekt följa kedjan: **Problem → Scenario → Skript → CI/CD → Leverans**.

- **Vad skriptet ska lösa:** Systemet ska ersätta manuell, tidskrävande granskning av säkerhetsloggar. Målet är att automatiskt korrelera data från både Linux och Windows för att upptäcka brute-force-attacker, inloggningar från okända maskiner och anomalier som avviker från en fastställd baslinje.
- **Vilken data som används:**
  - **Linux:** Inloggningsdata från `/var/log/auth.log`.
  - **Windows:** Misslyckade inloggningshändelser (Event ID 4625) från Security Log i Event Viewer.
  - **Baslinje:** En lokal fil `known_machines.csv` som definierar auktoriserade IP-adresser och maskinnamn.
- **Risker:** Felaktig exekvering som leder till missade hot, exponering av känslig information i loggar, samt risken att skriptet kraschar vid korrupta loggfiler eller tomma dataset.
- **Val av språk:**
  - **Bash:** Används som "Linux-sensor" för att den har direkt tillgång till systemverktyg och `/var/log`.
  - **PowerShell:** Används som "Windows-sensor" för sin förmåga att hantera Event Viewer som objekt snarare än ren text.
  - **Python:** Fungerar som "Central Intelligence Engine" för att korrelera stora datamängder, parsa JSON/CSV och generera den slutliga rapporten.
- **Loggning:** Resultat loggas löpande med tidsstämplar till en delad fil `anomalies.log`. Slutresultatet presenteras i en professionell `final_security_report.txt`.
- **Testning:** Skripten testas genom "torrkörningar" (dry runs) och verifiering av logik med både normala och manipulerade indata (t.ex. en fil med >5 misslyckade inloggningar för att trigga brute-force-regeln).

---

### **2. Pseudokod för skripten**

Följande sektioner beskriver logiken och flödet utan att använda faktiska kod-syntax.

#### **A) Bash-skript: Linux Security Collector**

1.  **Initiering:** Definiera sökvägar till `auth.log`, utdatafil (`linux_data.json`) och den delade anomali-loggen.
2.  **Validering:** Kontrollera att `auth.log` existerar och att verktyget `jq` är installerat.
3.  **Extraktion:**
    - Läs `auth.log` rad för rad.
    - Använd mönstermatchning (Regex) för att hitta rader som innehåller "Failed password".
    - Extrahera tidsstämpel, användarnamn och käll-IP för varje träff.
4.  **Loggning:** Om misstänkta mönster (t.ex. root-inloggningsförsök) upptäcks, skriv omedelbart en varning till `anomalies.log`.
5.  **Export:** Formatera de insamlade objekten till en strukturerad **JSON-fil** som Python-skriptet kan läsa.

#### **B) PowerShell-skript: Windows Security Collector**

1.  **Initiering:** Sätt sökvägar för CSV-export och anomali-loggen.
2.  **Hämtning:** Använd systemkommandon för att hämta de senaste händelserna med ID 4625 (misslyckad inloggning) från Security-loggen.
3.  **Filtrering:** Filtrera bort händelser som är äldre än 24 timmar för att endast analysera relevant data.
4.  **Bearbetning:** Skapa objekt som innehåller `TargetUserName`, `IpAddress` och `TimeCreated`.
5.  **Export:** Exportera datan till en ren **CSV-fil** utan metadata (`-NoTypeInformation`) för enkel läsning i Python.

#### **C) Python-skript: Correlation & Analysis Engine**

1.  **Datainläsning:**
    - Ladda in `known_machines.csv` till en dictionary för snabba uppslag.
    - Läs in JSON-datan från Bash-skriptet och CSV-datan från PowerShell-skriptet.
2.  **Korrelationslogik:**
    - **Loopa** igenom alla logghändelser från båda källorna.
    - **Regel 1 (Okänd maskin):** Om en IP-adress inte finns i baslinjen, flagga som **CRITICAL**.
    - **Regel 2 (Brute-force):** Räkna misslyckade försök per IP. Om antalet är $\ge 5$, flagga som **HIGH**.
    - **Regel 3 (Anomali):** Jämför inloggningstider; om inloggning sker utanför kontorstid, flagga som **MEDIUM**.
3.  **Rapportgenerering:** Sammanställ alla flaggade händelser i en sorterad lista och skriv till `final_security_report.txt` med en sammanfattning av totala risker.

---

### **3. CI/CD och GitHub Actions**

För att arbeta professionellt ska projektet följa principer för **Continuous Integration (CI)** och **Continuous Delivery (CD)**.

#### **CI-regler (Continuous Integration)**

- **Små Commits:** Varje ändring ska vara liten, tydlig och dokumenterad.
- **Pull Requests:** Ingen kod slås ihop med huvudgrenen (`main`) utan en Pull Request och granskning.
- **Automatiserade tester:** Varje gång kod skickas till GitHub ska automatiska kontroller köras för att hitta fel tidigt.

#### **GitHub Actions-instruktioner**

Skapa en konfigurationsfil i mappen `.github/workflows/verify-scripts.yml`. Denna ska innehålla instruktioner för att:

1.  **Checka ut koden:** Hämta den senaste versionen av repot till en virtuell miljö (t.ex. `ubuntu-latest`).
2.  **Syntaxkontroll (Bash):** Köra ett verktyg som `shellcheck` på Bash-skriptet för att upptäcka vanliga misstag.
3.  **Syntaxkontroll (Python):** Köra `pylint` eller en enkel python-exekvering för att verifiera att det inte finns syntaxfel.
4.  **Strukturvalidering:** Kontrollera att alla obligatoriska filer (t.ex. `README.md` och mappen `data/`) existerar i repot.

#### **CD-regler (Continuous Delivery)**

- **Definition of Done:** Ett skript är inte "klart" förrän det är testat, dokumenterat i en `README` och har genomgått CI-kontrollerna.
- **Driftsättning:** I detta scenario innebär CD att den testade koden levereras till en "release"-gren där den är redo att köras i en produktionsmiljö.
