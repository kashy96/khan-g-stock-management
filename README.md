# KHAN G Stationary — Stock Management ERP

A desktop stock management application (Python + tkinter) with an ERP-style
interface: dark sidebar navigation, dashboard cards and styled tables.

- **Products & variants** — each product (e.g. "Ballpoint Pen") can have any
  number of variants (Blue, Red, Large...), each with its own cost, sale
  price, quantity, low-stock alert level and **location**.
- **Managed locations with photos** — create your shelves/racks once on the
  Locations page, attach a photo of each one, then just pick the location
  from a dropdown when adding a variant. Photos are stored inside the
  database (auto-resized), so they are shared automatically in the LAN setup.
- **Stock IN / OUT** per variant, with profit calculated automatically.
- **Locations page** — click a location to see its photo and everything
  stored there; search any item to find which shelf it is on.
- **Reports** — daily / weekly / monthly / yearly / custom, grouped by
  product, variant or day, with CSV export.
- Databases created by previous versions are upgraded automatically on first
  run (v1: products become "Standard" variants; v2: typed location texts
  become proper location records).

## Quick start — no Python needed

A ready-to-run program is built at **`dist\KHAN_G_Stock.exe`**. Copy that one
file anywhere (a shop PC, a USB drive, a folder you'll share) and double-click
it — no Python, no installer, nothing else required.

On first run it creates `config.json` and a local database file
`khan_g_stock.db` right next to the .exe.

If you later change `main.py` or `db.py` (or ask Claude to), rebuild the
.exe by double-clicking **`build_exe.bat`** — it takes under a minute and
overwrites `dist\KHAN_G_Stock.exe` with the new version. This machine needs
Python + `pip install pyinstaller pillow` to build it, but the resulting
`.exe` itself does not — copy just the `.exe` to other computers.

## Running from source instead (for development)

Requires Python 3.10+ (tkinter and sqlite3 are included with the standard
Windows installer). Install the one required dependency:

```
pip install -r requirements.txt
```

(`requirements.txt` also lists `pymysql` and `pyinstaller` as commented-out
optional lines — uncomment/install them only if you need the MySQL/LAN setup
or want to rebuild the `.exe`, respectively.)

```
python main.py
```

This also creates `config.json` and `khan_g_stock.db` next to it automatically.

**Default login:** username `admin`, password `admin123`
→ Log in, open the **Users** tab, and change this password immediately
(select the admin user, type a new password in the Password box, click
"Reset Password of Selected").

## User roles

| | Admin | Staff |
|---|---|---|
| Stock in / out | ✔ | ✔ |
| View products, variants, locations & stock | ✔ | ✔ (no cost shown) |
| Add/edit/delete products & variants, set cost & price | ✔ | ✘ |
| Dashboard, reports, profit figures | ✔ | ✘ |
| Manage users | ✔ | ✘ |

Create staff accounts in the **Users** page.

## Daily use

1. **Locations page** — first create your shelves/racks (name, note, and a
   photo taken with your phone). Click **Choose Photo…**, then **Add**.
2. **Products page** — create the product (name + category) together with its
   first variant (variant name, cost, sale price, opening quantity, a
   location picked from the dropdown, low-stock alert). Select a product row
   and click **Add Variant** to add more colors/sizes/types.
3. **Stock In / Out page** — pick the variant (the list shows its location and
   current stock), enter quantity: **STOCK IN** when goods arrive, **STOCK
   OUT / SALE** when you sell. Profit = (sale price − cost) × quantity,
   recorded at the moment of sale.
4. **Locations page (finding things)** — click a location to see its photo
   and every item stored there; or type an item's name in the search box to
   see which locations hold it. Staff can use this page too.
5. **Reports page** — pick Today / This Week / This Month / custom dates, view
   totals (stock in, items sold, revenue, cost, profit) grouped by product,
   by variant, by day, or as a full transaction list. **Export CSV** opens in Excel.
6. **Dashboard** — stock value, today's sales/profit, low-stock alerts and
   this month's top sellers.

## Sharing between shop computers (network setup)

By default the app uses a local SQLite file (one PC). To share one live
database across several computers on your shop Wi-Fi/LAN, using the `.exe`
(no Python needed on any of the shop PCs):

1. **On the main PC**, install MariaDB (free): https://mariadb.org/download/
   During setup, set a root password and allow networking.
2. Open the MariaDB command prompt on the main PC and run
   (replace `StrongPassword123` with your own):

   ```sql
   CREATE DATABASE khan_g_stock;
   CREATE USER 'khang'@'%' IDENTIFIED BY 'StrongPassword123';
   GRANT ALL PRIVILEGES ON khan_g_stock.* TO 'khang'@'%';
   FLUSH PRIVILEGES;
   ```

3. Allow port 3306 through Windows Firewall on the main PC
   (Windows Security → Firewall → Advanced settings → Inbound Rules →
   New Rule → Port → TCP 3306 → Allow).
4. Find the main PC's IP address: run `ipconfig` → note the IPv4 address
   (e.g. `192.168.1.100`). Give the main PC a fixed/static IP in your router
   so it doesn't change.
5. Copy **`KHAN_G_Stock.exe`** to every shop PC (a USB drive or a shared
   folder is fine — it's one file).
6. Next to the `.exe` on each PC, create a text file named `config.json`
   with this content (edit the password to match what you set in step 2):

   ```json
   {
     "engine": "mysql",
     "sqlite_file": "khan_g_stock.db",
     "mysql": {
       "host": "192.168.1.100",
       "port": 3306,
       "user": "khang",
       "password": "StrongPassword123",
       "database": "khan_g_stock"
     }
   }
   ```

   (If a `config.json` already exists there from an earlier single-PC run,
   just edit it instead of creating a new one.)

7. Double-click the `.exe` on each PC — they all now read and write the same
   live data. A sale rung up on one PC shows up on the others as soon as you
   switch pages there.

To go back to single-PC mode on a computer, edit its `config.json` back to
`"engine": "sqlite"`, or just delete `config.json` (the app recreates a
single-PC one).

*(Running from source with `python main.py` instead of the `.exe` works
exactly the same way — same `config.json`, same steps.)*

## Backups

- **SQLite mode (single PC):** click **⤓ Backup Database** on the Dashboard
  page (admin only) and choose where to save it — this is a safe live backup
  that includes all your location photos. Save it to a USB drive or a cloud
  folder (Google Drive, OneDrive) regularly. To restore, close the app, put
  the backup file back as `khan_g_stock.db` next to the `.exe`.
- **MySQL mode (shared network setup):** on the main PC run
  `mysqldump -u khang -p khan_g_stock > backup.sql` regularly (the Dashboard
  backup button shows this same reminder in that mode).

## Files

| File | Purpose |
|---|---|
| `dist\KHAN_G_Stock.exe` | The ready-to-run program — copy this to any shop PC |
| `main.py` | Source: the application (login + all screens) |
| `db.py` | Source: database layer (SQLite / MySQL) |
| `build_exe.bat` | Rebuilds the `.exe` after a source change |
| `config.json` | Settings — created next to wherever you run the app |
| `khan_g_stock.db` | Your data (SQLite mode) — back this up regularly! |
