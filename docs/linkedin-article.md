# I turned a drawer of "dead" tablets into free second monitors — and open-sourced it

We all have the drawer.

An old Android tablet. A cracked-corner Kindle. A phone from two upgrades ago. Devices that still power on, with screens that still work perfectly — sitting in the dark because their browsers are too old to run anything modern.

Now hold that thought against two numbers:

📈 The world generated **62 million tonnes of e-waste in 2022**, and only about **22%** of it was formally, responsibly recycled. We're on track for **82 million tonnes a year by 2030.** *(UN / ITU Global E-waste Monitor 2024)*

🖥️ Meanwhile, a second screen remains one of the cheapest productivity upgrades money can buy — surveys have measured the boost at roughly **42%**, consistent across two decades of studies. *(Jon Peddie Research)*

So here's the quiet absurdity of it: **we are drowning in perfectly good screens, and buying brand-new ones anyway.**

That's the itch I built **Inka** to scratch.

---

## What Inka does

**Inka turns any device — even a decade-old tablet or a jailbroken Kindle — into a live second screen for your PC. And if you want, you can tap and type on that old screen to control the PC right back.**

It's a tiny, self-hosted app (Windows, macOS, Linux). No accounts. No cloud. No app store. You run it, open a web address on the old device, and your screen — or a single window, or a terminal — shows up, live.

- 📺 **Stream** your whole screen, one window, or a terminal.
- 🕹️ **Control** it back — tap to click, type, arrow keys — from the old device.
- 🪫 **Park an app off-screen** so it keeps streaming while it's out of your way.
- 📱 **Bring in Android too** — mirror and control a phone over ADB, or launch scrcpy.
- 🌓 **e-ink friendly** — grayscale, dithering, and change-only refresh so Kindles don't flash.

---

## The part I love most

The hardest devices to support are the oldest ones — a 2013 Android tablet's browser can't run the modern WebSocket streaming that tools like this rely on.

So Inka falls back to a **no-JavaScript page** and an **MJPEG stream** — a technique so old that *modern* Chrome actually removed support for it… but every ancient browser still has it. 

In other words: for once, **old is the advantage.** The device everyone wrote off is exactly the device this works best on.

You can even control the PC from that ancient browser with zero JavaScript, using a trick from the 1990s web (`<input type="image">` form posts). A tap becomes a click. It's not pretty under the hood — it just *works*, on hardware a decade past its "support" date.

---

## Why this matters (beyond the fun)

- ♻️ **Sustainability:** the greenest device is the one you already own. Reuse beats recycle every time.
- 💸 **Access:** not everyone can drop money on a second monitor. Almost everyone has an old tablet.
- 🧑‍💻 **Focus:** put your chat, your docs, your logs, or a long-running task on a screen that isn't stealing your main display.
- 👁️ **Comfort:** it started, honestly, because I wanted to read a terminal on a soft e-ink Kindle instead of a bright monitor. Turns out a lot of people want that.

---

## It's free and open

Inka is MIT-licensed and open source. Windows is fully tested; macOS and Linux are wired up and I'd love testers and PRs.

👉 **Code + download:** github.com/PrahaladaSumiranTechlabs/inka

If you've got a drawer like mine, pull one device out, give it a job, and tell me what you put on it. Let's make old screens useful again. ♻️

---

*Built with a lot of curiosity and a pile of hardware that refused to die. If this resonates, a ⭐ on the repo genuinely helps.*

#OpenSource #Sustainability #eWaste #Productivity #Python #DIY #Upcycling #DeveloperTools
