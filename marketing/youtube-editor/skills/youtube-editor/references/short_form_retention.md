# Short-form retention: what the edit can and cannot do

The rules `viral_planner.py` applies and `retention_audit.py` scores, with the evidence behind
each one. 🟢 platform documentation or primary data · 🟡 third-party measurement or widely
reproduced practice · 🔴 folklore (named so it is not repeated as fact).

## 1. What actually drives views

- 🟢 YouTube Shorts analytics reports **"viewed vs. swiped away"**, the share of people who chose
  to watch rather than scroll past. That decision happens in the first moments, before any clever
  edit later in the video can matter.
- 🟢 Short-form feeds recommend what people watch through and rewatch. Retention is the lever an
  editor controls. Topic, idea and the first sentence are levers the *creator* controls, and they
  decide more than any edit. `retention_audit.py` says this in every report: a high score means
  the pacing will not lose people; it does not make a weak idea spread.
- 🟢 YouTube counts a Shorts view each time it starts or replays (with "engaged views" reported
  separately). A clean loop, ending hard on the last word, turns an accidental replay into a view.
- 🔴 "Attention spans are 8 seconds, shorter than a goldfish." The figure has no traceable study
  behind it. Do not cite it to a client; the swipe-away metric is the real argument.

## 2. The hook (first 1–3 seconds)

| Rule | Implementation | Evidence |
|---|---|---|
| First word on frame 1 | lead-in silence cut to < 0.05 s | 🟡 editor practice; dead air is the most common swipe trigger |
| Something moves in the first second | flash + impact sound, title card, punch-in | 🟡 practice; TikTok's creative guidance asks for an attention-grabbing opening in the first seconds 🟢 |
| The promise on screen as text | hook title card (yellow block, heavy font) | 🟡 a 2019 Verizon Media / Publicis survey reported 69% watch with sound off in public and 80% more likely to finish with captions; survey data, not a feed experiment |
| Say the payoff, not the preamble | the agent rewrites the hook text from the first sentence; asks for `--hook` when the first sentence is a greeting | 🟡 practice |

## 3. Pacing: pattern interrupts

- 🟡 Short-form editors change *something* on screen every 1.5–3 s: a jump cut, a framing change,
  a punch-in, text. No controlled public study pins an exact number; the planner's limits (4 s
  clean, 2.5 s punchy, 1.6 s insane) are practice, and the audit labels them that way.
- Jump cuts remove pauses over 0.14–0.40 s (by intensity) but keep 0.04–0.10 s each side, so a
  word's attack and release are never clipped. The precision engine snaps every cut to a frame and
  keeps it out of words.
- Framing alternates wide/tight per sentence (1.10–1.28×). Alternating hides the jump cut: the
  eye reads a deliberate camera change instead of a skip.
- 🔴 "Cut every second, no matter what." Over-cutting a calm explainer reads as anxious and costs
  trust. Pick the intensity for the content, not the platform.

## 4. Emphasis and shocks

- Punch-ins on numbers and power words ("never", "free", "three"): the word the viewer must
  remember gets a visual beat and a pop.
- Shocks (flash, shake, black-and-white hit, glitch, impact sounds) are punctuation. One on the
  hook, one at a turn in the story, one on the CTA lands. Twelve in thirty seconds becomes
  wallpaper the brain stops seeing. The planner caps sound effects at about one per 1.2 s
  (0.8 s for insane), and the audit fails more than one per second.
- 🟡 A shock that promises something the video does not deliver costs more than it earns: viewers
  leave and the comments say why. Match intensity to content. Insane suits hype and
  entertainment; on a serious or emotional topic it reads as noise.

## 5. Captions

- 🟡 Word-by-word "karaoke" captions (current word highlighted and popping) are the dominant
  short-form style. They keep the eye on the lower third and double as the hook text for muted
  viewers. Two lines at most, 14 characters per line, never ending a line on a connecting word.
- 🟢 Captions are an accessibility requirement for deaf and hard-of-hearing viewers, independent
  of any algorithm.

## 6. Sound

- 🟡 A music bed 20–24 dB under the voice, ducked while speaking, fills the gaps that jump cuts
  leave without competing with the words.
- Sound effects are synthesized in code (whoosh, boom, bass drop, pop, click, ding, riser, camera),
  so they are royalty-free and identical on every machine. Licensed music is the user's
  responsibility; the tools never fetch audio.
- Loudness: the whole mix is normalised to −14 LUFS and the encoded file is re-measured (see
  `youtube_delivery_spec.md`). Sound effects are levelled against the voice *after*
  normalisation, so a boom hits the same on a quiet phone recording as on a studio one.

## 7. Length and ending

- 🟢 YouTube Shorts accepts uploads up to 3 minutes. 🟡 15–60 s is the practical range for a
  single idea; the audit flags anything shorter or longer, it does not refuse it.
- Shorts end hard on the last word, with no fade, so the loop is seamless. Long-form keeps a short
  fade-out.
- One clear call to action, said once, near the end. The planner frames it tightest and adds a
  ding.

## Sources

1. YouTube Help, "Measure your Shorts performance" (viewed vs. swiped away; engaged views).
2. YouTube Help, "Upload YouTube Shorts" (answer 12779649): length limit and format.
3. TikTok for Business, "Creative best practices" (hook in the opening seconds, text on screen,
   vertical full-screen, sound on).
4. Meta for Business, "Best practices for Reels" (vertical 9:16, audio, on-screen text).
5. Verizon Media & Publicis Media (2019), consumer survey on sound-off viewing and captions.
6. W3C WCAG 2.2, Success Criterion 1.2.2 Captions (Prerecorded).
7. Murch, W. *In the Blink of an Eye* (2nd ed.), Silman-James, 2001: the cut serves emotion first.
