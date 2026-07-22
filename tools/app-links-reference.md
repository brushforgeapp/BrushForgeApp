# App links reference (Android + iOS)

The website half is live: `https://brushforgeapp.com/.well-known/assetlinks.json` (Android) and
`https://brushforgeapp.com/.well-known/apple-app-site-association` (iOS). This file documents the
app half. Nothing in the shipped apps changes until these snippets are added and released.

## Status

- [x] assetlinks.json hosted (contains the upload key certificate)
- [ ] Add the Play App Signing certificate to assetlinks.json
      (Play Console: Test and release > Setup > App integrity > App signing > "App signing key
      certificate" > SHA-256 fingerprint. Paste it as a second entry in
      sha256_cert_fingerprints. Without it, verification fails on devices, because Google
      re-signs releases with that key.)
- [x] apple-app-site-association hosted (appID QU42M6Y29T.com.basmahieu.TheBrushForge)
- [ ] Android: intent filter + routing (below), ship in a normal release
- [ ] iOS: Associated Domains entitlement (below), ship in a normal release
- [ ] Play Console: Grow users > Deep links > Add domain > brushforgeapp.com (after the release)

## Android: AndroidManifest.xml

Add inside the launcher activity's `<activity>` element:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" android:host="brushforgeapp.com" android:pathPrefix="/paints/" />
    <data android:scheme="https" android:host="brushforgeapp.com" android:pathPrefix="/convert/" />
</intent-filter>
```

Deliberately apex-only and path-scoped: marketing pages (home, support, privacy) stay in the
browser; only content that has an in-app equivalent opens the app. The www host is not declared
(it 301s to the apex, and declaring a host whose assetlinks fetch redirects would fail
verification).

## Android: routing sketch

URL shapes to handle (everything else: open the app home screen):

- `/paints/{brandSlug}/{paintSlug}.html`  > paint detail, or converter with source preselected
- `/convert/{a}-to-{b}.html`              > converter with source/target brands preselected
- `/convert/` and `/paints/`              > converter search

Slug mapping: `paintSlug` is the paint name lowercased with non-alphanumerics collapsed to
hyphens (site generator: tools/bfcatalog.py `slugify`), with the line name appended only when two
paints in a brand share a name. Brand slugs: citadel, vallejo, army-painter, ak-interactive,
two-thin-coats, scale75, pro-acryl (Monument Hobbies), kimera-kolors.

Pragmatic v1 (no new tables): parse brand from `brandSlug`, turn `paintSlug` hyphens into
spaces, run the existing catalog search restricted to that brand, open the top hit. Exact
mapping later if needed: the site publishes `assets/data/paints.min.json` with a `path` field
per paint that mirrors these URLs.

Kotlin sketch (adapt to the actual navigation setup):

```kotlin
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    val uri = intent.data ?: return
    if (uri.host != "brushforgeapp.com") return
    val seg = uri.pathSegments
    when {
        seg.size >= 3 && seg[0] == "paints" -> {
            val brand = brandFromSlug(seg[1])
            val query = seg[2].removeSuffix(".html").replace('-', ' ')
            openConverterSearch(query = query, brand = brand)
        }
        seg.size >= 2 && seg[0] == "convert" -> {
            val m = Regex("(.+)-to-(.+)\\.html").matchEntire(seg[1])
            openConverter(source = m?.groupValues?.get(1), target = m?.groupValues?.get(2))
        }
        else -> openHome()
    }
}
```

## Android: testing

```
adb shell pm verify-app-links --re-verify io.brushforge.brushforge_android_app
adb shell pm get-app-links io.brushforge.brushforge_android_app
adb shell am start -a android.intent.action.VIEW \
  -d "https://brushforgeapp.com/paints/citadel/mephiston-red.html"
```

Play Console check: Grow users > Deep links (the page shows per-URL "deep linked" status once
the release with the intent filter is live and the domain is added).

## iOS: Associated Domains

Xcode > TheBrushForge target > Signing & Capabilities > + Capability > Associated Domains, add:

```
applinks:brushforgeapp.com
```

Handle the URL in the app delegate / scene delegate (`NSUserActivity` with
`NSUserActivityTypeBrowsingWeb`), same routing logic as Android. Note: Apple fetches the
association file through its CDN when the app installs; after first setup, allow up to a day
before testing, and test from a real tap (Notes app link works), not the Safari address bar.

## Play Console notes

- The "Upgrade 2 custom scheme links" suggestion on the Deep links page refers to Firebase
  auth internal schemes (genericidp://, recaptcha://). Leave them as they are.
- The UTM install referrer on the website's store links is separate from deep links and keeps
  working regardless.
