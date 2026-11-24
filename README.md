# Gold Claim Scanner - Android App

An Android application that captures your GPS location, searches local and remote SQLite databases of mining claims, and visualizes nearby active gold mining claims on an interactive OpenTopoMap.

## App Features Summary

- **Local SQLite Database Search**: Conducts lightning-fast spatial queries against `claims_slim.db` for active mining claims near any coordinate.
- **Automatic GitHub Database Updates**: Automatically checks `manifest.json` on app startup (`GoldClaimApp`), downloads `claims_slim.db.gz` if updated, decompresses via GZIP, updates the local database, and displays a `"Gold Claim Database Updated"` notification.
- **GPS Location Capture**: Captures precise device GPS coordinates to search for active claims.
- **Interactive OpenTopoMap Page (`MapActivity`)**: Displays the searched location (red pin) and the **10 closest active claim results** (gold pins) with `Lode` or `Placer` types and claim numbers.
- **Map Long-Press & "Search Here"**: Long-pressing anywhere on the map or clicking **"Search Here"** triggers a smooth pan animation and zooms to level **13** centered on the search location, dropping a red pin and showing the 10 closest claims.
- **Pin Label Long-Press**: Long-pressing any pin label (info window) on the map copies its GPS coordinates to the clipboard and prompts to open Google Maps.
- **Favorites & Bookmarks (Up to 8)**: Save up to 8 favorite locations, quick-access them on both home and map pages, copy coordinates, and launch Google Maps.
- **Styled Theme Buttons**: Custom styled gold map, home, and favorites buttons with fine borders (`1dp` stroke width).

---

## GitHub Database Updates & Weblinks

On app startup (`GoldClaimApp.onCreate()` $\rightarrow$ `MiningClaimsApi.checkForUpdates()`), the app makes a background HTTP GET request to check for the latest database version.

- **Base URL**: `https://github.com/smackxs/or_gold_claims/releases/download/latest-data/`
- **Manifest Weblink**: [https://github.com/smackxs/or_gold_claims/releases/download/latest-data/manifest.json](https://github.com/smackxs/or_gold_claims/releases/download/latest-data/manifest.json)
- **Database GZIP Weblink**: [https://github.com/smackxs/or_gold_claims/releases/download/latest-data/claims_slim.db.gz](https://github.com/smackxs/or_gold_claims/releases/download/latest-data/claims_slim.db.gz)

### Update Flow
1. Fetches `manifest.json` from GitHub.
2. Compares the remote `version` string with the locally stored version (`claims_db_prefs` SharedPreferences).
3. If a newer version is available, downloads `claims_slim.db.gz`, decompresses it via `GZIPInputStream`, replaces the local database file (`claims_slim.db`), saves the new version, and shows a **`Gold Claim Database Updated`** toast message at the top of the screen.

---

## Buttons and Function Calls Reference

| Button Name & ID | Location | Function / Action | Function Calls |
| :--- | :--- | :--- | :--- |
| **Check My Location** (`fab_capture_button`) | Home Page (Top Center) | Captures GPS coordinates and searches for nearby active claims. | `requestLocationPermissionAndGetLocation()` $\rightarrow$ `getCurrentLocation()` $\rightarrow$ `fetchClaims(...)` $\rightarrow$ `MiningClaimsApi.getClaims(...)` |
| **Gold Map Button** (`btn_goldmap`) | Home Page (Bottom Left) | Opens the interactive map page with current search claims. | `openMapPage(lat, lon, claims)` $\rightarrow$ starts `MapActivity` |
| **Favorites / Bookmarks** (`fab_test_button`) | Home Page (Bottom Right) | Toggles saved favorites list. Clicking a favorite loads its claims; long-clicking copies GPS & opens Google Maps. | `loadFavorites()`, `fetchClaims(...)`, `copyCoordsAndOpenGoogleMaps(...)` |
| **Search Here** (`btn_search_here`) | Map Page (Bottom Center) | Searches claims around the center of the current map view with a smooth pan and zoom level 13. | `performSearchAt(centerLat, centerLon, isLongPress = true)` $\rightarrow$ `MiningClaimsApi.getClaims(...)` |
| **Home Button** (`card_home_button`) | Map Page (Bottom Left) | Returns the user back to the home page. | `finish()` (closes `MapActivity`) |
| **Add Favorite** (`card_add_favorite`) | Map Page (Lower Right) | Saves the current map center location to favorites. Long-clicking toggles favorites list. | `showAddConfirmationDialog(...)`, `saveFavoriteWithUniqueName(...)` |
| **Pin Label / Info Window** (Long-Press) | Map Page (On any pin bubble) | Copies the pin's GPS coordinates to the clipboard and asks to open Google Maps. | `copyCoordsAndOpenGoogleMaps(lat, lon)` |

---

## Technical Specifications

- **Minimum SDK**: API Level 34 (Android 14+)
- **Target SDK**: API Level 35+
- **Language**: Kotlin
- **UI Framework**: Material Design 3
- **Mapping Library**: osmdroid (OpenStreetMap for Android) with OpenTopoMap tiles

## Permissions Required

- `ACCESS_FINE_LOCATION`: Precise GPS location access
- `ACCESS_COARSE_LOCATION`: Approximate location access
- `INTERNET`: GitHub database updates (`manifest.json` / `claims_slim.db.gz`)
- `ACCESS_NETWORK_STATE`: Network connectivity check

---

**Version**: 2.0  
**Target Platform**: Android 14+ (API 34+)
