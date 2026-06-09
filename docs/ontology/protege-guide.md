# Protégé Guide — Trekku Ontology Screenshots

**Student:** Goh Kian Xiang
**Ontology file:** `docs/ontology/trekku.owl`
**Namespace:** `http://trekku.um.edu.my/ontology#`

---

## 1. Prerequisites

### 1.1 Download Protégé Desktop

1. Go to **https://protege.stanford.edu/** and download **Protégé Desktop 5.6.x** (the "Desktop" build, not the Web version).
2. Choose the installer that matches your OS (Windows .zip or .exe).
3. Java requirement: Protégé 5.6 bundles its own JRE. If you use the "no JVM" build, install **Java 11 or later** first. Verify by running `java -version` in a terminal — you need `11.x` or higher.

### 1.2 Open the ontology file

1. Launch Protégé.
2. On the welcome screen click **Open a local file**, or go to **File → Open**.
3. Navigate to `C:\Users\gohki\Trekku\docs\ontology\trekku.owl`.
4. Click **Open**. Protégé will load the file and show the class hierarchy in the **Entities** tab.
5. Confirm the active ontology IRI at the top reads `http://trekku.um.edu.my/ontology`.

---

## 2. Enabling the Reasoner (Openllet / Pellet)

> **Why not HermiT?** HermiT does **not** support SWRL *built-in* atoms (e.g. `swrlb:greaterThan`), so it throws `built-in atoms are not supported yet` when it hits the `OverBudgetItinerary` rule. Use **Openllet** (the maintained Pellet fork), which supports DL-safe SWRL rules **and** the defined-class classification — one reasoner does everything.

1. Install Openllet once: **File → Check for plugins…** → tick **"Openllet Reasoner"** (sometimes listed as "Pellet") → **Install** → restart Protégé and reopen `trekku.owl`.
2. In the menu bar go to **Reasoner → Openllet** to select it as the active reasoner.
   - Openllet supports OWL 2 DL (needed for the defined hotel subclasses) and SWRL built-ins (needed for the budget rule).
3. Go to **Reasoner → Start reasoner** (or press `Ctrl+R`).
4. Wait for the progress bar to finish — this usually takes a few seconds.
5. Once complete you will see:
   - **Yellow-highlighted** class names in the class hierarchy — these are classes that now have inferred instances or inferred subclass relationships.
   - A banner at the bottom of the screen confirms "Reasoner Active".
6. To view inferred axioms: in the **Class hierarchy** panel, click the **"Inferred"** radio button (top of the panel, next to "Asserted") to switch to the inferred view. Inferred class memberships for individuals will appear here.

---

## 3. Enabling the SWRL Tab

The `OverBudgetItinerary` SWRL rule is already serialized inside `trekku.owl`. To view it:

1. Go to **Window → Tabs → SWRLTab** in the menu bar.
2. A new "SWRL" tab will appear in the tab row.
3. Click it to open the SWRL rule editor — you should see the rule:
   ```
   Itinerary(?i) ^ basedOnTrip(?i, ?t) ^ budget(?t, ?b)
   ^ itineraryHasFlight(?i, ?f) ^ price(?f, ?p)
   ^ swrlb:greaterThan(?p, ?b)
   -> OverBudgetItinerary(?i)
   ```
4. With the **Openllet** reasoner active (Section 2), this rule actually *executes*: any itinerary whose flight `price` exceeds the trip `budget` is inferred to be an `OverBudgetItinerary`. (By default the seed data is under budget so nothing fires — see Screenshot 6 for how to make it fire.) A screenshot of the rule text plus the inferred result is ideal for the report.

---

## 4. The Six Screenshots — Checklist

Capture the screenshots in order. Maximize the Protégé window before each one and expand all relevant tree nodes.

---

### Screenshot 1 — Asserted Class Hierarchy

**Suggested filename:** `fig1-class-hierarchy.png`

**Steps:**

1. Click the **Entities** tab (top row of tabs).
2. Inside Entities, click the **Classes** sub-tab.
3. Make sure the hierarchy panel at the left shows **"Asserted"** (radio button at the top of the panel).
4. In the hierarchy, expand `owl:Thing → TravelEntity`. You should see:
   - `TravelEntity`
     - `Hotel`
       - `BudgetHotel`
       - `MidRangeHotel`
       - `LuxuryHotel`
     - `Attraction`
     - `Flight`
     - `Location`, `Itinerary`, `ItineraryDay`, `TripParams`, `AgentSession`, `TacitFeedback`, `RatingSnapshot`
5. Capture the screen with the full tree visible.

**Figure caption:** *Fig 1. Asserted OWL class hierarchy of the Trekku ontology showing `TravelEntity` and its disjoint subclasses.*

---

### Screenshot 2 — Object Properties Tab

**Suggested filename:** `fig2-object-properties.png`

**Steps:**

1. Click the **Entities** tab.
2. Click the **Object properties** sub-tab (looks like a grey diamond icon).
3. Expand `owl:topObjectProperty` in the hierarchy panel.
4. You should see all nine object properties listed:
   - `hasLocation`, `includesDay`, `dayHasHotel`, `dayHasAttraction`,
   - `itineraryHasFlight`, `basedOnTrip`, `sessionProducedItinerary`,
   - `feedbackOn`, `snapshotOf`
5. Click on one property (e.g., `hasLocation`) to show its domain/range in the right panel.
6. Capture the screen.

**Figure caption:** *Fig 2. Object properties panel of the Trekku ontology with domain and range annotations for `hasLocation`.*

---

### Screenshot 3 — Data Properties Tab

**Suggested filename:** `fig3-data-properties.png`

**Steps:**

1. Click the **Entities** tab.
2. Click the **Data properties** sub-tab (looks like a yellow diamond icon).
3. Expand `owl:topDataProperty`.
4. You should see data properties including:
   - `hasMinPrice`, `hasMaxPrice`, `price`, `budget`, `hasRating`, `popularityScore`, `signal`, `hasName`, etc.
5. Click on `hasMaxPrice` to show its range (`xsd:decimal`) and any restrictions in the right panel — this is the key property used by the defined hotel classes to auto-classify hotels into price tiers.
6. Capture the screen.

**Figure caption:** *Fig 3. Data properties panel showing `hasMaxPrice` — the property used by defined hotel subclasses to auto-classify individuals.*

---

### Screenshot 4 — OntoGraf Relationship Graph

**Suggested filename:** `fig4-ontograf.png`

**Steps:**

1. Go to **Window → Tabs → OntoGraf** in the menu bar.
2. A new "OntoGraf" tab will appear — click it.
3. The canvas starts empty. In the left-side class list, hold **Ctrl** and click to select:
   - `TravelEntity`, `Hotel`, `Attraction`, `Flight`,
   - `BudgetHotel`, `MidRangeHotel`, `LuxuryHotel`,
   - `Itinerary`, `Location`
4. Drag them onto the canvas, or right-click a class and choose **Add to graph**.
5. Right-click on `Hotel` → **Show subclasses** to draw the subclass edges automatically.
6. Click **Layout** (auto-layout button in the toolbar) to tidy the graph.
7. The result should show `TravelEntity` at the top with subclass arrows flowing down to `Hotel`, `Attraction`, `Flight`, and a further level showing the three hotel tiers.
8. Capture the screen.

**Figure caption:** *Fig 4. OntoGraf visualization of Trekku class relationships, showing the `TravelEntity` hierarchy and hotel tier subclasses.*

---

### Screenshot 4B — WebVOWL Diagram (recommended companion figure)

**Suggested filename:** `fig4b-webvowl.png`

OntoGraf proves the diagram was built in Protégé, but it can look cluttered. **WebVOWL** renders the same ontology as a clean, colour-coded, standardised VOWL graph that looks far more professional in a report. Capture both and use WebVOWL as the main overview figure.

**Steps:**

1. Open a browser and go to **https://service.tib.eu/webvowl/**.
2. Click the **Ontology** menu (top-right) → **Select ontology file** / **Upload**.
3. Choose `C:\Users\gohki\Trekku\docs\ontology\trekku.owl` and confirm. WebVOWL parses the file and draws the graph (this is fully offline-safe — your data is processed in the browser).
4. Drag nodes apart so `TravelEntity`, `Hotel`, `Attraction`, `Flight`, `Location`, `Itinerary`, etc. are readable. Use the sidebar sliders (e.g. *Gravity*, *Node distance*) to spread the layout.
5. Optional: in the **Filter** sidebar, toggle off "Datatype properties" first to show only the class/object-property structure for a cleaner overview, then capture a second image with them on.
6. Capture the graph. (WebVOWL can also **Export → SVG/PNG** via the Export menu for a crisp, vector image — prefer this over a screenshot if available.)

**Figure caption:** *Fig 4B. WebVOWL (VOWL notation) visualization of the Trekku ontology — classes as nodes, object properties as labelled directed edges.*

---

### Screenshot 5 — Inferred Class Hierarchy (The Money Shot)

**Suggested filename:** `fig5-inferred-classification.png`

**Steps:**

1. Confirm Openllet is running (menu shows **Reasoner → Stop reasoner** rather than **Start reasoner**; if not, press `Ctrl+R`).
2. Go to **Entities → Classes** sub-tab.
3. At the top of the class hierarchy panel, click the **"Inferred"** radio button to switch from Asserted to Inferred view.
4. Expand `owl:Thing → TravelEntity → Hotel → BudgetHotel` (and the other two tiers).
5. You should see the three seed hotel individuals listed under the correct defined class:
   - `HotelIndividual_Luxury` (Mandarin Oriental KL, `hasMaxPrice` 820) appears under `LuxuryHotel`
   - `HotelIndividual_MidRange` (Cititel Mid Valley, `hasMaxPrice` 350) appears under `MidRangeHotel`
   - `HotelIndividual_Budget` (OYO 89761 Hotel Aliff, `hasMaxPrice` 150) appears under `BudgetHotel`
   - These individuals were **only asserted** to be of type `Hotel` — the reasoner inferred the tier from `hasMaxPrice`.

   > **If individuals do not appear:** switch to the **Individuals** sub-tab instead (still in Entities). Select a hotel individual, look at its **"Types"** panel on the right — inferred types appear in yellow italics (e.g., *BudgetHotel*). Screenshot that panel with the yellow inferred type visible.

6. The yellow highlighting (Protégé default) makes it visually clear these are inferred, not asserted.
7. Capture the screen showing at least one hotel individual nested under its inferred tier.

**Figure caption:** *Fig 5. Openllet reasoner output — hotel individuals auto-classified into `BudgetHotel`, `MidRangeHotel`, and `LuxuryHotel` based on their `hasMaxPrice` value (inferred types shown in yellow).*

---

### Screenshot 6 — SWRL Rule Firing on an Itinerary Individual

**Suggested filename:** `fig6-overbudget-itinerary.png`

This figure demonstrates the `OverBudgetItinerary` SWRL rule. **By default the seed itinerary is under budget (flight MYR 189 < budget MYR 1500), so the rule does not fire.** To show it firing, temporarily push the flight price above the budget, capture, then revert.

**Steps:**

1. Click the **Entities** tab → **Individuals** sub-tab (person-silhouette icon).
2. Select the flight individual `AirAsiaFlight_PEN_KUL` → in **Data property assertions**, edit `price` from `189` to e.g. `2000` (above the `1500` budget). Save.
3. Re-run the reasoner (**Reasoner → Start reasoner**, or Synchronise / `Ctrl+R`).
4. In the individual list, select the itinerary individual `Itinerary_KL_3Day`.
5. In the right panel confirm:
   - **Object property assertions** — `basedOnTrip` → `TripParams_KL_3Day`, `itineraryHasFlight` → `AirAsiaFlight_PEN_KUL`.
   - **Types** — asserted `Itinerary`, plus in **yellow italics** the inferred type **`OverBudgetItinerary`** (the rule fired).
6. Capture the screen with the inferred `OverBudgetItinerary` type visible.
7. **Revert**: set the flight `price` back to `189` and re-run the reasoner so the committed file stays in its clean default state.

> **Simpler alternative (no edit):** if you prefer not to modify data, instead select a **hotel** individual (e.g. `HotelIndividual_Luxury`) and capture its **Types** panel showing asserted `Hotel` + inferred `LuxuryHotel` (yellow) and the `hasMaxPrice` assertion. Use this if you only need to show inference, not the SWRL rule.

**Figure caption:** *Fig 6. The `OverBudgetItinerary` SWRL rule firing — itinerary `Itinerary_KL_3Day` is inferred (yellow) as an `OverBudgetItinerary` because its flight price exceeds the trip budget.*

---

## 5. Tips for Clean Screenshots

| Tip | Detail |
|-----|--------|
| Maximize window | Full-screen Protégé before every capture — no partial panels. |
| Expand all tree nodes | Click the small triangle/arrow next to every parent node so no children are hidden off-screen. |
| Use the light theme | Protégé defaults to a light theme; do not switch to dark. Yellow inferred highlighting is only visible on a light background. |
| Crop to the relevant panel | Crop out the OS taskbar and browser chrome; keep only the Protégé window or the specific panel. |
| Zoom in if text is small | Use OS zoom (`Windows key + +`) temporarily for clarity. |

### Recommended filenames and placement

Drop all six images into `docs/ontology/` alongside `trekku.owl`:

```
docs/ontology/
  trekku.owl
  fig1-class-hierarchy.png
  fig2-object-properties.png
  fig3-data-properties.png
  fig4-ontograf.png
  fig4b-webvowl.png
  fig5-inferred-classification.png
  fig6-overbudget-itinerary.png
```

These filenames correspond to the `[Figure X]` placeholders used in `ontology-section.md` — replace each placeholder with the matching image using your document editor's Insert Image feature, or in Markdown:

```markdown
![Fig 1 – Asserted class hierarchy](fig1-class-hierarchy.png)
```

---

## 6. Troubleshooting

### Reasoner errors: "built-in atoms are not supported yet"

**Symptom:** `An error occurred during reasoning: A SWRL rule uses a built-in atom, but built-in atoms are not supported yet.` (`IllegalArgumentException` from `HermiT.structural.OWLNormalization`).

**Cause:** You are running **HermiT**, which cannot evaluate SWRL built-ins like `swrlb:greaterThan` used in the `OverBudgetItinerary` rule.

**Fix:** Switch to the **Openllet** reasoner (see Section 2): install via **File → Check for plugins…**, then **Reasoner → Openllet → Start reasoner**. Openllet runs both the defined-class classification and the SWRL rule.

---

### Reasoner reports an inconsistency

**Symptom:** After starting the reasoner, a red banner appears: "Ontology is inconsistent."

**Likely cause:** A hotel individual was manually asserted into two disjoint defined classes at the same time (e.g., both `BudgetHotel` and `LuxuryHotel`), or its `hasMaxPrice` value overlaps across boundaries due to a data-entry error.

**Fix:**
1. Note which individual is named in the inconsistency explanation (click "Explain" in the banner).
2. Go to **Entities → Individuals**, select that individual.
3. In the **Types** panel, remove any manually asserted defined-tier type (keep only `Hotel`).
4. Restart the reasoner.

---

### SWRLTab is not visible

**Symptom:** The SWRL tab does not appear after **Window → Tabs → SWRLTab**.

**Fix:** The SWRLTab plugin ships with Protégé 5.6 by default. If it is missing:
1. Go to **File → Check for plugins** and install "SWRLTab".
2. Restart Protégé.
3. If the menu item **Window → Tabs** is entirely absent, you may have a very minimal build — download the full Protégé 5.6.x bundle from https://protege.stanford.edu/.

---

### File won't open / blank screen after opening

**Symptom:** Protégé shows a blank or throws a parse error when opening `trekku.owl`.

**Likely cause:** Wrong Java version (< 11) if you used the no-JVM build; or a corrupted download of the ontology file.

**Fix:**
1. Run `java -version` in a terminal. If it shows 8 or lower, download Java 11+ from https://adoptium.net/ and set `JAVA_HOME`.
2. If Java is fine, re-download or re-generate `trekku.owl` — ensure the file starts with `<?xml version="1.0"?>` and contains the `rdf:RDF` root element (it is an RDF/XML file, not Turtle).
3. In Protégé, try **File → Open from URL** and paste the absolute file path as a `file:///` URI, e.g. `file:///C:/Users/gohki/Trekku/docs/ontology/trekku.owl`.

---

### Inferred hierarchy looks the same as asserted

**Symptom:** After switching to "Inferred" view, no individuals appear under the defined hotel subclasses.

**Likely cause:** The seed individuals either lack the `hasMaxPrice` data property assertion, or the defined-class restrictions were not authored with the correct OWL `hasValue`/`someValuesFrom` pattern.

**Fix:**
1. Select a hotel individual → check that `hasMaxPrice` appears in its **Data property assertions** panel with a numeric literal value.
2. Select `BudgetHotel` in the class hierarchy → inspect its **Equivalent classes** expression in the right panel — it should be an OWL restriction such as `Hotel and (hasMaxPrice some xsd:decimal[< 200])`.
3. If the restriction is missing or malformed, the ontology file may need to be regenerated.
