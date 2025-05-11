**Designing the Dashboard**

The user's goal is creating a practical, user-friendly dashboard for their Streamlit app. I'll suggest a clean layout with tabs like Crawl Listings, Listings Database, Analysis, Alerts, Metrics, and Settings. Each tab should have tailored requirements, such as interactive filters, charts (e.g., price vs. competition), yield data, and histograms. I’ll recommend adding visual elements like dynamic tables and ensuring data integration with Grafana for better visualization. Lastly, it’s important to focus on functionality without unnecessary details.

**Objective**
Turn the Streamlit dashboard into the control‑center for your whole pipeline—scan, judge, buy. Everything a flip decision needs is one click away.

---

### 1. Layout — Five High‑Leverage Tabs

| Tab                | Why It Exists                                   | Core Components                                                                                                              |
| ------------------ | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Scan**           | Run eBay queries and inspect raw listings.      | • Query box + limit slider<br>• Progress bar<br>• Results table with: title, grade, price, link, “Send to Analysis” button   |
| **Deals**          | Surface *only* listings flagged as undervalued. | • Filter chips (player, set, grade, % below comp)<br>• Heat‑map table (green = deep discount)<br>• “Buy Now” external link   |
| **Database**       | Explore everything stored.                      | • Counts (cards, comps, alerts) as KPI tiles<br>• DataFrame with sort/search<br>• Bulk actions (delete, re‑analyze)          |
| **Comps & Charts** | Visual proof behind each decision.              | • Line chart 90‑day sales vs listing price<br>• Boxplot of price distribution<br>• Velocity gauge (# sales/30 days)          |
| **System Health**  | Make sure the bot isn’t blind.                  | • Last crawl time, success %, API 429s (Prometheus metrics) <br>• Cron schedule status<br>• Log viewer (tail last 100 lines) |

---

### 2. Key Interactions

* **One‑click analysis:** any row in *Scan* passes its JSON to `analyzer.analyze_listing` and opens *Deals* with pre‑filtered view.
* **Threshold tuning:** sidebar sliders for `undervalue_threshold`, `historical_days`; updates materialized views live.
* **Drill‑down:** clicking a row in *Deals* opens modal with:

  * Listing photo (from eBay API)
  * Stat block (median, average, min, max)
  * Price‑vs‑comp bar
* **Bulk crawl presets:** saved queries (e.g., *“PSA 10 Griffey UD 1989”*) run hourly; editable in UI, stored in a YAML.

---

### 3. Visual Elements That Matter

* **Color‑coded discounts** — 40‑60 % = yellow, < 40 % = red flag.
* **Sparkline per card** — show 30‑day price trend inline.
* **API quota dial** — real‑time % of daily eBay calls used.
* **True‑positive hit rate tracker** — pulls from `alerts` vs resale outcome; target ≥ 75 % .

---

### 4. Data Plumbing

```
dashboard.py
│
├─ @st.cache_data get_db_session()
├─ scan_query() → collector.adapters.ebay.search()
├─ push_to_db() → database.models.Card
├─ analyze(card_id) → analyzer.analyze_listing()
└─ grafana_client.py → Prometheus / Grafana JSON
```

Use cached sessions for DB and API to cut latency. Async crawl with `asyncio.gather` so UI stays snappy.

---

### 5. Settings Pane

* eBay keys (pull from `.env`, display last four chars only)
* Crawl schedule cron editor
* Email / Pushbullet target address
* Toggle “Include shipping in comps”

---

### 6. Next Steps

1. **Implement `analyze` CLI logic inside `cli.py` then wire to UI.**
2. **Write simple `db.query_cards()` helper** for the *Database* tab.
3. **Expose Prometheus metrics via `/metrics`; embed in System Health.**
4. **Add materialized view refresh on slider change (Postgres `REFRESH MATERIALIZED VIEW`).**
5. **Ship; refine thresholds after first 10 flips.**

Get these in, and the dashboard moves from “nice toy” to an actionable trading terminal.
