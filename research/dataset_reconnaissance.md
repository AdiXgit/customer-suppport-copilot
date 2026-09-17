# Dataset Reconnaissance — Detailed Notes

Companion to `docs/DATA.md` (structure/quality summary) and
`research/brand_selection.md` (scoring/decision). This file holds the
supporting evidence: topic sampling and real example conversations for
each seriously-considered brand.

Labels: **MEASURED** (computed), **OBSERVED** (seen while sampling),
**HYPOTHESIS** (plausible, unvalidated).

All analysis was run directly against `data/raw/twitter/twcs.csv` using
chunked/streaming pandas (already installed globally — no new packages
installed). The raw file was not modified.

---

## Method

1. Loaded the full CSV once with memory-conscious dtypes (int64 tweet
   ids, string columns) to reconstruct reply chains (see `docs/DATA.md`
   §2 for the algorithm).
2. For each candidate brand, sliced only that brand's conversations
   (a small subset of the 798,197 total) rather than operating on the
   full 2.8M-row frame repeatedly.
3. Topic analysis: tokenized customer messages within each brand's
   conversations (lowercased, URLs/@mentions/punctuation stripped,
   stopwords removed), counted document-frequency of terms across a
   sample of up to 20,000 customer messages per brand.
4. Conversation-quality analysis: randomly sampled real 4–7 message
   conversations per brand and read them directly.

---

## Topic Analysis (MEASURED — top terms by document frequency)

### AppleSupport (sampled 20,000 / 131,764 customer messages)
`iphone, ios, phone, update, fix, apple, battery, app, screen, apps,
music, working` dominate. **OBSERVED**: spans many different Apple
products/services (iOS itself, Apple Music, hardware issues, App
Store) — broader than a single product.

### SpotifyCares (sampled 20,000 / 48,543 customer messages)
`spotify, account, premium, app, music, songs, playlist, family, album,
email, student, version` dominate. **OBSERVED**: single product
(the Spotify app/service), topically tight — account/login, premium
billing, family/student plans, playback/library bugs, content
licensing.

### Delta / AmericanAir / British_Airways (airlines)
`flight, service, gate, plane, seat, hours, delayed, airport, booking,
check-in` dominate across all three. **OBSERVED**: tightly clustered
around flight-operations topics (delays, cancellations, seating,
baggage, booking changes) — coherent domain, but skewed toward
operational disruptions where a generic bot reply has limited ability
to resolve the underlying problem (weather delay, overbooking) — it can
mostly acknowledge/redirect rather than fix.

### Uber_Support (sampled 20,000 / 72,154 customer messages)
`uber, driver, app, ride, account, charged, drivers, email, trip,
cancelled` dominate. **OBSERVED**: coherent domain (rides, drivers,
billing/charges, account, cancellations).

### AmazonHelp (sampled 20,000 / 203,598 customer messages)
`amazon, order, delivery, prime, service, delivered, package, refund,
account, product` dominate, but also `que` (Spanish "that/what")
appearing in the top-40 English-stopword-filtered list — a signal of
substantial non-English content. **OBSERVED**: much broader domain than
other candidates because Amazon sells literally every product category
— "order status," "delivery," "refund," "account," "Prime" recur, but
underneath those buckets sit near-unlimited product-specific
sub-issues.

### AskPlayStation (sampled 20,000 / 23,954 customer messages)
`account, error, psn, playstation, game, code, password, store, refund`
dominate. **OBSERVED**: coherent domain (account/login/PSN issues,
purchase/refund, game errors).

---

## DM-Redirect Rate (MEASURED)

Fraction of the *brand's own* tweets containing `dm` / `direct message`
/ `private message`, sorted ascending (lower = more of the resolution
is visible in the public dataset):

| Brand | DM-redirect % |
|---|---|
| AmazonHelp | 0.6% |
| ChipotleTweets | 0.8% |
| VerizonSupport | 11.7% |
| British_Airways | 14.0% |
| Delta | 16.5% |
| AmericanAir | 16.8% |
| SouthwestAir | 16.9% |
| XboxSupport | 20.9% |
| AskPlayStation | 26.6% |
| SpotifyCares | 30.8% |
| Uber_Support | 35.4% |
| sprintcare | 47.7% |
| Ask_Spectrum | 49.5% |
| AppleSupport | 52.5% |
| comcastcares | 71.5% |
| TMobileHelp | 81.8% |

**HYPOTHESIS validated qualitatively**: sampling actual AppleSupport
conversations (below) confirms that a large share of "resolutions" are
just "send us a DM" with no visible follow-through — the real fix never
appears in the dataset. Airlines and AmazonHelp, by contrast, more often
give a substantive visible answer (policy text, a link, a status
update) before or instead of redirecting to DM.

---

## Real Example Conversations (OBSERVED)

### SpotifyCares — visible, self-contained resolutions

```
Customer: As a [redacted] premium user for years, I'm extremely disappointed
          in how bad the Mac and PC desktop app is. @SpotifyCares
Customer: [...] I wish I could listen to podcasts on desktop
Brand:    Hey Christopher! Is there a specific issue you're running into?
          We'll be happy to lend a hand. Just let us know /TB
Brand:    Hey Sam, good news! You can find steps to listen to podcasts on
          your desktop application here: [link]. Hope this helps /TB
Customer: It's sputtering and refuses to load immediately. Now I can't even
          log in right away. Have to quit the app a few times.
Brand:    Got it, best thing to try here is a reinstall. Just follow the
          steps at [link]. Let us know how it goes /TB
```

```
Customer: [...] why was "Que Fue" by El Alfa removed from Spotify??????
Brand:    Hey, help's here! Can you tell us what country your account is
          set to? We'll check things out /CH
Customer: USA? It was listed before and all of a sudden it disappeared.
Brand:    Got it! Sometimes content gets temporarily removed because of
          licensing changes. Hopefully we'll have it available again in
          the US soon /CH
Customer: For one specific song?
Brand:    Yes, and this could also happen with other artists as well.
          Don't worry, we'll be passing on your feedback [...] /CH
```

**OBSERVED**: SpotifyCares resolutions are usually visible *in the
thread itself* — a diagnostic question, then a concrete answer (a help
link, a policy explanation, a fix). This is exactly the shape of
evidence a retrieval/RAG system needs.

### AppleSupport — frequent DM redirects, resolution often invisible

```
Customer: Why isn't my Apple Music working [emoji] @AppleSupport
Brand:    Let's see what's going on. Can you try to force close Music?
          If not, give it a shot: [link]
Customer: It didn't work so what next
Brand:    Does this persist after rebooting your iPhone as well? If so,
          let's follow up in DM. Tell us the version of iOS installed
          there. [link]
```

```
Customer: iPhone 6 doesn't always take pictures w/ios 11.0.3
Brand:    We'd like to know more about what is going on. Do you get an
          error when trying to take a photo? Let us know what happens.
Customer: No it acts like it took the photo but when you go to the
          pictures, it's not there.
Brand:    Got it. From here, send us a DM letting us know which country
          you're located in. We'll continue helping out from there.
```

**OBSERVED**: the conversation trails off right at the point where the
real diagnosis/fix would happen — it moves to DM and the public dataset
simply ends. This pattern repeats often enough (52.5% DM-redirect rate)
that AppleSupport's *visible* resolution corpus is meaningfully thinner
than its raw tweet volume suggests.

### Delta / AmericanAir — some visible resolutions, but often policy-deflection or apology, not fix

```
Customer: [...] if I have a suitcase and a backpack for carry on, would I
          be able to carry on a poster tube as well?
Brand:    The limit for carry-on baggage is 2 items. One item for the
          overhead bin, one that would fit underneath the seat [...]
Customer: bummer :( thanks anyway
Brand:    You are very welcome. Have a great week.
```

```
Customer: [...] why is it that every time I select a seat at purchase..
          I get kicked off when it's oversold and put in the middle..
Brand:    We always want you to keep the seat you chose. There be times,
          due to schedule or equipment changes, that we'll need to
          change some seats.
Customer: This is the 3rd time this month I've gotten selected to get
          moved to a middle seat..
Brand:    Our apologies. We'll work hard to do better for you on your
          next flight. You can change your seat on the app or [link].
```

**OBSERVED**: airlines do give visible policy answers for
general/policy questions (baggage rules, seating policy) but for
account-specific disruptions (compensation, rebooking, delay refunds)
they consistently deflect to "DM your confirmation number" or a phone
line — similar failure mode to AppleSupport, just at a lower overall
rate (16.5–16.9% DM-redirect).

### AmazonHelp — visible resolutions, but multilingual and product-open-ended

```
Customer: (Spanish) [...] dice que mi pedido salió a las 9:37. 15:48 y a
          seguir esperando.
Brand:    (Spanish) Hola. Lamentamos este inconveniente, ¿podrías por
          favor decirnos cuál es la fecha de entrega de tu pedido [...]
Customer: ¡Ya me llegó! Gracias.
Brand:    ¡Nos alegra saber que ya recibiste tu pedido! [...]
```

```
Customer: (Japanese) [payment method issue with Amazon] [...]
Brand:    (Japanese) [apology + link to customer service contact]
Customer: (Japanese) 解決しました！案内ありがとうございました！ ("Resolved!
          Thanks for the guidance!")
Brand:    (Japanese) [thanks for confirming]
```

**OBSERVED**: AmazonHelp conversations are often resolved visibly (a
diagnostic question, then a concrete follow-up, with an explicit
"resolved!" confirmation from the customer in some cases — a genuinely
useful signal for what a "resolution" looks like). But a meaningful
share of the sampled conversations are in French, Spanish, or Japanese,
and the topic space (order status, delivery, refunds, payment, account,
and an open-ended long tail of specific-product complaints) is far
broader than a single-product brand like Spotify.

---

## Non-English Content Estimate (MEASURED, lower bound)

ASCII-ratio heuristic (customer messages with <90% ASCII characters,
sampled up to 15,000 per brand). Undercounts European languages that
are mostly-Latin script; treat as a lower bound, not a language-ID
result.

| Brand | Est. non-English % |
|---|---|
| AmazonHelp | 5.2% |
| AppleSupport | 1.0% |
| SouthwestAir | 0.7% |
| SpotifyCares | 0.6% |
| Delta | 0.4% |
| TMobileHelp | 0.4% |
| AmericanAir | 0.3% |
| Uber_Support | 0.3% |
| British_Airways | 0.2% |
| AskPlayStation | 0.1% |

AmazonHelp stands out as meaningfully more multilingual than every
other serious candidate, consistent with the example conversations
above.

---

## Summary Takeaways Feeding Brand Selection

- **SpotifyCares**: tight single-product topic space, highest
  "conversation ends with a brand message" rate (94.0%), moderate
  DM-redirect (30.8%), resolutions usually visible and self-contained,
  nearly all English. Best combination of coherence + usable evidence.
- **AppleSupport**: largest tech-support volume, but broader
  multi-product topic space and the highest DM-redirect rate among
  strong candidates (52.5%) — a lot of its apparent "resolution
  richness" is not actually visible in the data.
- **Delta / AmericanAir / British_Airways**: low DM-redirect, decent
  volume, coherent domain, but skewed toward operational-disruption
  issues that are often escalation-worthy rather than confidently
  auto-resolvable — good for demonstrating escalation policy, weaker
  for demonstrating grounded auto-resolution.
- **AmazonHelp**: highest raw volume by far, low DM-redirect, but the
  broadest and most open-ended topic space of any candidate plus
  measurably more multilingual content — harder to compress into 6–12
  coherent intents without either dropping non-English data or
  accepting a much fuzzier taxonomy.

Full scoring and final recommendation: see `research/brand_selection.md`.
