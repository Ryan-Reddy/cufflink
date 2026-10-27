# Putting cufflink on the Microsoft Store

The reason to bother: **Microsoft signs the package.** That is the whole
SmartScreen problem gone — no "Windows protected your PC", no *More info →
Run anyway*, no certificate of your own at roughly €300 a year that would not
buy instant reputation anyway. Someone installs it the same way they install
anything else, and your name is on it.

```powershell
winget install Microsoft.WindowsSDK.10.0.22621   # once
copy packaging\identity.example.json packaging\identity.json
# fill it in from Partner Center, then:
.\package.ps1                 # -> dist\cufflink.msix, ready to upload
.\package.ps1 -SelfSign       # signed with a test cert, installable here
```

## 1. The developer account — done

An **individual** account at
[partner.microsoft.com/dashboard](https://partner.microsoft.com/dashboard), so
your own name is on the listing.

## 2. Reserve the name — done, and it is why this is called cufflink

**Murmur was already taken.** The reserved name is what the Store displays and
what the package's DisplayName must equal character for character, so the app
took a name it could actually ship under rather than a decorated version of one
it could not.

Reserved: **cufflink** — https://apps.microsoft.com/detail/9P1NW9ZKC2NP

If you ever reserve another name for the same product, only `displayName` in
`packaging\identity.json` has to change; the manifest reads it from there.

Reserving gives you the two identity strings. They go in
`packaging\identity.json`:

| from Partner Center | into identity.json |
|---|---|
| Package/Identity/Name | `name` |
| Package/Identity/Publisher (the `CN=…`) | `publisher` |

Your *display* name is already in the manifest as `PublisherDisplayName` and
says **Ryan Reddy**. That's the line under the app.

## 3. Build and upload

`.\package.ps1` produces `dist\cufflink.msix`. Upload it unsigned; Microsoft
signs it.

To try the package on this PC first, with Developer Mode on (Settings →
System → For developers), register the staged folder; no certificate needed:

    .\package.ps1
    Add-AppxPackage -Register build\msix\AppxManifest.xml

Remove it again with `Get-AppxPackage RyanReddy.cufflink | Remove-AppxPackage`.
`-SelfSign` is the other way: it signs the .msix with a test certificate and
prints the commands that trust it.

The manifest gives the app a `cufflink.exe` execution alias. The Claude Code
hook points at it (`%LOCALAPPDATA%\Microsoft\WindowsApps\cufflink.exe`)
rather than at the install folder, whose name changes with every version.

## 4. The two things certification will ask about

**`runFullTrust` is a restricted capability.** cufflink is a PyInstaller desktop
app, not a UWP one, and full trust is what lets it run at all. The
justification goes on the submission's **Submission options** page, under
**Restricted capabilities**
([Submission options](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/manage-submission-options)).
Say something close to this:

> cufflink is a desktop application packaged with the Desktop Bridge. It needs
> full trust to register system-wide hotkeys, read the current selection via
> the clipboard, and run the speech models locally. It installs no service
> and no driver. Reading aloud makes no network connections; the optional
> meeting tracker downloads one speech-recognition model, once, on first use.

Keep that true. The voice and the meeting tracker's first model ship in the
package and the text-in port is bound to `127.0.0.1`; the one connection
outward is the first-use download of `small` (below).

The manifest does not declare `internetClient`, and that is **not** what keeps
cufflink offline: capabilities like it apply to apps that run in an
AppContainer, and a `runFullTrust` desktop app does not
([App capability declarations](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/app-capability-declarations)).
What keeps it offline is the code.

**The licence.** cufflink is GPL-3.0. The Store listing has an **Additional
license terms** field
([Store listings](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info));
put the GPL there, with the link to
[LICENSE](https://github.com/Ryan-Reddy/cufflink/blob/main/LICENSE).

## 5. The listing — the part that is actually your name getting out

The package is engineering; the listing is the shopfront. Things that matter
more than they sound:

- **Screenshots.** At least one, 1366×768 or larger
  ([screenshot rules](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images)).
  Three are in `assets/store/screenshots/`, 1920×1080, captured from the
  Store build running on Windows: the pill mid-read with a word lit, the
  voices window, and the meeting tracker following a recording. Microsoft
  asks for no marketing text on the image, so the headlines are the captions
  (up to 200 characters each):
  - `01-reading.png`: *Select anything. Press a key.*
  - `02-voices.png`: *The voice is yours to build*
  - `03-meeting.png`: *Meetings: who said what*

  `assets/store/` has the tiles.
- **Short description** (one line, shown in search results). Something like:
  *"Select text anywhere in Windows and hear it read aloud, entirely on your
  own machine."*
- **Say what it downloads.** The download is about 560 MB (758 MB once
  installed), and the meeting tracker fetches a further 484 MB (`whisper-small`) the first time it is
  used, into `%LOCALAPPDATA%\cufflink`. Reading aloud never needs it. Put a
  line like this in the description, and the same in **Additional system
  requirements** if the form offers it, so nobody meets half a gigabyte they
  were not told about:
  *"Everything you need to read aloud is in the download. The optional meeting
  tracker downloads one more speech model (about 484 MB) the first time you
  use it; nothing is ever uploaded."*
- **The offline angle.** Say "no account, no network, nothing leaves your
  machine" high up.
- **Link out.** The listing takes a website and a support contact. Point them
  at [cufflink.reddy.world](https://cufflink.reddy.world) and the GitHub repo — that is how a
  Store listing turns into people knowing who made it, rather than a download
  that ends there.
- **Category:** Productivity. **Age rating:** the questionnaire takes a
  minute; cufflink has no user content, no ads and no data collection, so it
  comes out as everyone.

## 6. The privacy policy

Partner Center wants a URL even for an app that collects nothing. There is one:

    https://cufflink.reddy.world/privacy/

That page is built from [PRIVACY.md](PRIVACY.md) on every deploy, so the two
cannot disagree. It is short because the honest version is short — no account,
no telemetry, nothing uploaded, one settings file, and the meeting notes you
choose to keep. Worth reading before you paste it, so
that if certification asks, the answer is yours rather than a link you trusted.

## 7. What to expect

A rejection names what failed; fix that and resubmit rather than starting
over.

The package is about 560 MB: the Kokoro voice is 338 MB of it and
`whisper-base`, the meeting tracker's first model, another 145 MB. The alternative — a small download that fetches the
model on first run — would break the one promise the app is making, so it
stays in the package.

## Updating

Bump `version` in `packaging\identity.json` (the Store refuses anything not
higher than the last upload, and the fourth number must stay `0`), run
`.\package.ps1`, upload. Updates go out to everyone who installed it, which is
the other thing the Store buys you.
