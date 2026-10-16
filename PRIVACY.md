# Privacy Policy

**cufflink** · last updated 16 October 2026

## The short version

cufflink collects nothing, and sends nothing about you anywhere. There is no
account, no telemetry, no analytics, and no server for your data to reach.
Everything it hears or reads stays on your computer.

## What cufflink does with the text you read

When you select text and press the hotkey, cufflink copies that selection,
turns it into speech on your own computer, plays it, and forgets it. The text
is held in memory only while it is being read. Nothing is written to disk and
nothing is transmitted.

The speech synthesis runs locally, from a model file installed alongside the
application. It is not a cloud service. The machine can be disconnected from
the internet permanently and cufflink works exactly the same.

## Meeting notes, if you use them

cufflink has a meeting tracker, which you open yourself with `Ctrl+Alt+T`. It
opens recording nothing. Only while you have recording switched on
(`Ctrl+Alt+L`) does it listen to your microphone and to what your speakers
play, and turn both into text on your own computer. The audio itself is not
saved and not sent anywhere.

When the meeting ends, the text is saved as a file in your local application
data folder (`cufflink\meetings`). It stays there, on your computer, until you
delete it.

## What cufflink stores on your computer

- `settings.json`, under your local application data folder. It holds your own
  preferences — which voices you chose, speed, volume, and the voice
  treatments you mixed. It contains no personal information.
- The meeting notes described above, only if you record a meeting.
- The speech-recognition model for meeting notes, once it has been downloaded
  (see below).

None of it ever leaves your machine. Deleting the app's data removes it.

## Network access

cufflink opens a listening socket on `127.0.0.1:52719` so that other
applications *on the same computer* can send it text to read aloud. This
address is the loopback interface: it is reachable only from your own machine
and is not accessible from any network.

Reading aloud makes no outbound network connections.

Two downloads can happen, and both are files coming to you; nothing about you,
and no audio or text, is uploaded:

- **Installing from source.** The installer downloads the speech models once
  (about 500 MB) from their public release pages, and checks each file against
  a known checksum. The Microsoft Store package already contains them.
- **The first time you use the meeting tracker,** it downloads a larger
  speech-recognition model (about 484 MB) from Hugging Face, once, into your
  local application data folder. If you never use the meeting tracker, this
  never happens.

## Third parties

There are none. No advertising, no analytics providers, no crash reporting, no
payment processor.

## Children

cufflink collects no data from anyone, of any age.

## Changes

Any change to this policy will appear in this file, whose history is public in
the project repository.

## Contact

Ryan Reddy — https://reddy.world
Issues and questions: https://github.com/Ryan-Reddy/cufflink/issues
