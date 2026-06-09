# Play Console testers — how to use `play-testers.csv`

Google Play wants a **CSV of tester email addresses**, one per line, **no header
row**. Each address must be a **Google account** (Gmail or a Google-linked email),
or the person can't accept the test invite.

## Fill it in
1. Open `docs/play-testers.csv`.
2. Replace each `testerNN@gmail.com` with a real tester's Google email.
3. Keep **one email per line**, no commas, no quotes, no header. Add more lines
   if you have more than 12 testers.

## Why 12?
If your Play **developer account is personal/individual** (created after Nov
2023), Google requires a **closed test with ≥12 testers opted-in for ≥14 days**
before you can apply for production. That's why the template starts at 12 — aim
for 12–20 reliable people so a few dropouts don't sink the count. **Organisation**
accounts are exempt from this rule.

## Where to upload it
**Play Console → Test and release → Testing → (Internal or Closed testing) →
Testers tab → Create email list → Upload CSV** → pick `play-testers.csv` → name
the list (e.g. "EYEWAZ testers") → Save → tick the list for that track.

Then share the **opt-in / join link** Play generates with your testers. They open
it on their Android phone, tap "Become a tester", then install from Play.

## Tip
A **Google Group** is often easier than a raw list: add the group's address as a
single line in the CSV, and manage membership in the group. New testers then
don't need a new Play upload.
