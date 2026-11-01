# Learning design and clear spoken explanations

Read before planning every lecture. This guide supplies the teaching method for both visual
levels; the entrypoint supplies platform, language, voice and rendering instructions.

Contents: homework intake · attempts · connections · later recall · spoken explanations · evidence

## 1. Ask for the homework and preserve the task

- Ask for the corresponding homework/problem set, including needed figures and any available
  solutions, before choosing retrieval questions. Bundle this with the visual-level question
  and branding when relevant. If the supplied materials already contain the exercises, use
  them and do not ask for the same material again. A question number alone is insufficient
  unless its actual statement is accessible.
- Read the notes while waiting, but leave exercise selection pending. Silence does not mean
  there is no homework. If the user explicitly has none or declines to provide it, proceed
  with clearly labelled author-written problems; never call those actual homework. For an
  unattended run without exercises or a previous waiver, prepare the lesson draft and report
  the missing input before finalizing the retrieval questions.
- Ingest homework into `WORK/homework/` so it cannot overwrite the lecture's `source.txt`,
  manifest or transcript. Read its diagrams and handwriting with the same care as the notes.
  Keep solutions separately identified. Do not infer unreadable values or missing figures.
- Record selected items in `WORK/learning-plan.md`: learning objective, original file/page,
  exercise/subpart ID, prerequisite knowledge, estimated attempt time, and where the solution
  appears. Keep the original givens, units, diagrams, constraints, subparts and reasoning
  demand. A faithful translation may change language, not the problem. Label any approved
  adaptation and retain the original source reference.
- Select actual questions that require choosing a method, connecting ideas, deriving,
  explaining, or solving multiple steps. Do not replace them with easier lookalikes or change
  the numbers to produce a quick plug-in question. A genuine standalone subpart is usable if
  its original context and dependencies are supplied. Keep dependent subparts together.
- Teach required concepts and identify prerequisites before the attempt. Preserve difficulty
  through the original task, not through unexplained notation or omitted information. Verify
  a worked solution independently; reconcile errors in supplied keys rather than copying them.

## 2. Make an attempt possible before revealing feedback

Use `\attemptq[15]{title}{question shown}{question spoken}{solution shown}{solution spoken}`
for a question and solution that each fit one frame. The title includes the real exercise ID.
It creates a narrated question, a still question page held for 15 seconds, then a separate
solution frame. The narrator explicitly asks the learner to pause, write a solution or reasoned
start, mark where they are stuck, and resume after trying. There is no countdown race.

The 15 seconds are a buffer to pause the player, not a homework time limit. An MP4 continues
if the viewer does not pause; it cannot detect work or enforce an answer. Give a realistic
suggested working time for each problem, often several minutes. Do not claim that a learner
answered or understood merely because the video reached its answer frame.

For longer exercises, use ordinary frames: question and required diagram → spoken pause
instruction → still `\wait` page → separate worked-solution frames. Keep the entire problem
available during the attempt, splitting the initial reading across frames if necessary and
pointing to the original problem sheet. Do not shrink a long problem to fit the macro.

Hide answers and solution-specific hints in the question image, narration and subtitle cues
until after the attempt interval. Give feedback on the method, decisive reasoning, common
error and a units/limiting-case check. A difficult problem can use a hint after the first attempt
followed by a second explicit pause before its complete solution. The first attempt must not
already contain the answer or a worked version of the exact same exercise.

Start the budget with roughly 1–2 substantial homework questions per 10 minutes, then adjust
to the material. Short predictions remain useful, but do not count them as the homework
retrieval questions. Include the spoken problems, worked solutions and embedded pauses in
the video duration. Report the additional suggested time working with the player paused.

## 3. Let ideas settle and connect

After a major derivation or demonstration, keep its completed diagram/equation visible and
stop motion. Briefly connect what changed physically, the principle explaining it, and the
conditions under which the result applies. Connect the result to the next task or an earlier
idea. Use a few clear sentences and a compact on-screen relation, not another dense summary.

Invite one specific explanation, such as “Why must more of the B-rich phase increase the
overall B content?” Hold the completed picture silently with `\wait<n>{6}` as a starting
point, and invite a longer manual pause when useful. Every hold needs an overlay on which
the completed visual remains present; a disappearing animation is not a reflection screen.
Budget these moments from the start. Split dense material into another chapter when needed.

## 4. Deliver a small recall exercise with every video

Write `WORK/recall.md` and `WORK/recall-answers.md` in the lecture's language. Link both in the
delivery message. Keep the question file free of solutions. Include three manageable prompts:

1. Explain the central mechanism or principle from memory, including its key condition.
2. Reconstruct a useful diagram, relationship or derivation outline from memory.
3. Reattempt one selected actual homework question or standalone subpart, with its source ID
   and all required givens. An author-written fallback must be labelled as such.

Suggest attempting them without notes the next day and again about a week later, then checking
the answer file and revisiting the relevant video segment. These intervals are adjustable
starting points. Keep the concept prompts short; state the homework item's own estimated time
instead of promising the whole exercise takes only a few minutes. Put hints, concise worked
answers, success criteria and verified timestamps (or exact frame titles) in the answer file.
If the learner is stuck, let them use the hint, attempt again, then study the feedback.

An immediate final recall prompt can introduce this routine. Keep it low stakes. Do not create
calendar events, reminders, messages, a background watcher or invented learner scores. Use
actual later responses to adjust recaps when the user provides them.

## 5. Write explanations for a listener

Plan the reasoning before polishing the wording. For each difficult idea, identify the
question the learner is trying to answer, the visible quantities, the rule connecting them,
and the inference the learner should be able to make. Then write speech that follows that
reasoning at the same time as the picture.

- **Name the object and action.** Say “the solid fraction increases” rather than “this
  increases” when several things could be meant. Use one stable name for each quantity.
  Distinguish easily confused concepts explicitly, such as composition versus phase fraction.
- **One new reasoning move at a time.** Use short clauses and break a long sentence into
  separate spoken beats when it introduces several relationships. Define a new term just
  before using it; give a brief prerequisite reminder when the step depends on it. Do not
  introduce several undefined symbols in a single breath.
- **Make the connection audible.** Say which assumption or law permits the step: “Because
  only two phases are present, their mass fractions add to one.” Use “because”, “therefore”,
  “first” or “now substitute” when they express a real relation. Do not invent a causal
  explanation for an algebraic identity, correlation or analogy.
- **Coordinate speech and evidence.** Point to the named region, hold the compared states
  together, and reveal the relevant term when it is explained. Keep key givens, symbol
  definitions and the current equation visible. Narrate what the relation means and why the
  next step follows; reading a long expression aloud by itself is insufficient.
- **Keep rigor, reduce verbal decoration.** Prefer concrete verbs and direct explanations.
  Avoid ornamental introductions, piled-up abstractions, rhetorical questions answered
  immediately, filler such as “so basically”, and “obviously” or “simply” where work is hidden.
  A conversational tone does not require slang. Use an analogy only when its mapping helps;
  return to the real system and state its relevant limit.
- **Check the listener's next inference.** Use a numerical example, comparison or limiting
  case when it resolves the likely confusion. Then let the learner predict or explain one
  consequence. Do not substitute reassuring phrases for the missing reasoning.

Example for a fixed temperature in a two-phase region where the solid is richer in B:

Compressed wording: “The phase fractions vary inversely with the respective tie-line arms.”

Spoken explanation, synchronized to the two endpoints and the overall-composition marker:
“The left endpoint gives the liquid composition. The right endpoint gives the solid
composition. Here the solid contains more B. At this temperature, both phase compositions
are fixed. To make an alloy with more B, we therefore need a larger solid fraction. Now move
the overall-composition marker toward the solid endpoint. The solid fraction must increase.”

Show the fraction formula after establishing that relation, connect each distance to its
term, and check an endpoint. The example is an authoring pattern, not a replacement for the
learner's actual homework.

Before rendering, read the difficult passages aloud or inspect them as a spoken sequence
against their slides. Can a learner identify what each noun refers to, why each step follows,
and where to look without rereading the previous sentence? Repair a failed connection before
changing the voice or globally slowing the lecture. When TTS is used for a preview, inspect
the actual audio; do not claim a listening check based only on text.

## 6. Evidence and scope of the design

The following research informs these authoring choices. The exact hold lengths, question
counts, wording and review intervals above are practical defaults to tune, not experimentally
established optima for these videos. Harder homework preserves the user's requested course
standard; difficulty alone does not guarantee better learning.

- **Short spoken segments:** Leahy & Sweller (2011), *Cognitive load theory, modality of
  presentation and the transient information effect*. Long spoken instructions performed
  differently from shortened ones in graph-learning experiments. This supports keeping
  essential information available and breaking up demanding speech.
  [Paper](https://doi.org/10.1002/acp.1787)
- **Visible and verbal structure:** Mautone & Mayer (2001), *Signaling as a cognitive guide in
  multimedia learning*. Signals identifying the organization of a science explanation
  improved transfer in three experiments. Use clear links between steps and matched visual
  cues. [Paper](https://doi.org/10.1037/0022-0663.93.2.377)
- **Conversational address:** Mayer, Fennell, Farmer & Campbell (2004), *A personalization
  effect in multimedia learning*. Conversational wording improved transfer, but not retention,
  in three narrated-animation experiments. It supports direct address, not a claim that
  casual language or attractive prose alone fixes learning.
  [Paper](https://doi.org/10.1037/0022-0663.96.2.389)
- **Retrieval during video:** Szpunar, Khan & Schacter (2013), *Interpolated memory tests reduce
  mind wandering and improve learning of online lectures*. Supports learner responses between
  lesson segments; it does not establish that a short answer reveal counts as retrieval.
  [Paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3631699/)
- **Review over time:** Cepeda et al. (2008), *Spacing effects in learning: A temporal ridgeline
  of optimal retention*. The useful gap depended on how long material needed to be retained.
  Use spaced review with adjustable intervals.
  [Paper](https://doi.org/10.1111/j.1467-9280.2008.02209.x)
