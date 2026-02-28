# Use Cases & Inspiration

This server was built for workout form analysis, but the approach — returning timestamped frame grids directly to an LLM, with a layered overview → section → precise inspection workflow — generalises to any domain where a human would normally scrub through a video manually. Below are ten domains where this architecture is immediately applicable.

---

## 1. Physical Therapy & Rehabilitation Monitoring

**Use case:** A patient records their prescribed exercises at home (knee bends, shoulder rotations, walking gait) and uploads the video for remote assessment by a physio or AI assistant. The LLM checks range of motion, symmetry, and compensation patterns without the patient needing to attend in person.

**Implementation advice:** Use `detect_pauses` to isolate the end-range positions (where ROM is measured), `compare_frames` to show the left vs right side of symmetric movements side by side, and `annotate_frame` to draw joint angle measurements for the therapist to review. `get_audio_transcript` can capture the patient's self-reported pain commentary during the exercise.

---

## 2. Sports Coaching — Technique Review

**Use case:** A swim coach, tennis coach, or golf instructor reviews athlete footage between sessions. The LLM identifies technical errors (early hip rotation, dropped elbow on entry stroke, loss of spine angle) across multiple reps and produces a timestamped summary report.

**Implementation advice:** `detect_motion_events` naturally segments individual strokes, swings, or reps. Use `get_motion_heatmap` to identify which body segments are moving most (useful for detecting compensation). `compare_frames` across multiple reps highlights consistency or drift between attempts. For multi-athlete session footage, `detect_scenes` can segment each athlete's turn.

---

## 3. Manufacturing & Assembly Line Quality Control

**Use case:** A production floor records assembly operations. The LLM reviews footage for process deviations — a step performed out of sequence, a component installed at the wrong orientation, or a torque operation that appears rushed compared to the standard cycle time.

**Implementation advice:** `detect_scenes` segments each unit's assembly cycle. `get_motion_timeline` reveals whether cycle times are consistent across units (compression = rushed, elongation = hesitation). `annotate_frame` can mark the specific component in question with a label for the quality report. Combine with `get_audio_transcript` on lines where operators call out checkpoints.

---

## 4. Surgical Training & Procedure Review

**Use case:** Surgical trainees record laparoscopic procedures for review by supervising surgeons. The LLM identifies instrument handling, tissue tension management, and phase transitions in the procedure, flagging moments for discussion without requiring the supervisor to watch the full recording.

**Implementation advice:** `detect_motion_events` maps instrument activity, `detect_pauses` identifies decision points where the surgeon pauses before a critical action. `get_video_section` lets the supervisor zoom into flagged moments. This domain benefits heavily from the lossless `get_precise_frame` PNG output where instrument position needs to be assessed precisely.

---

## 5. Wildlife & Nature Observation

**Use case:** Trail cameras and field researchers produce hours of footage per day. The LLM reviews footage to catalogue animal appearances, identify species, count individuals, and log behaviours (feeding, aggression, nursing) with timestamps — turning a manual review task that takes hours into an automated log.

**Implementation advice:** `detect_motion_events` handles the primary filtering — most trail camera footage is static until an animal enters frame. `get_video_overview` on each detected event provides quick identification context. `get_motion_heatmap` reveals movement paths across the frame (useful for understanding which part of the habitat is being used). Low sensitivity on `detect_motion_events` works well for small animals; high sensitivity for insects or slow-moving reptiles.

---

## 6. Real Estate & Property Inspection Walkthroughs

**Use case:** A property inspector or estate agent records a walkthrough video. The LLM reviews the footage, identifies rooms, flags visible defects (staining, cracks, damaged fittings), and produces a structured room-by-room report with timestamped evidence frames.

**Implementation advice:** `detect_scenes` naturally segments room transitions as the camera pans through doorways (high contrast cut). `get_video_overview` on each room scene gives broad context, then `get_precise_frame` on flagged moments captures evidence. `annotate_frame` with labels can mark defect locations within the frame for the formal report. The `compare_frames` tool is useful for showing before/after shots from repeat inspections of the same property.

---

## 7. Cooking & Recipe Instruction Verification

**Use case:** A food content creator or culinary school reviews recipe demonstration videos to verify that timings, techniques, and visual cues match the written recipe. The LLM checks whether the onions are truly golden before the next step is added, or whether dough consistency at the fold matches the description.

**Implementation advice:** `get_audio_transcript` is central here — spoken instructions can be correlated with visual state via word-level timestamps. `detect_pauses` finds the moments where the instructor holds up a completed stage for review (natural pause = "look at this"). `compare_frames` across different batches or instructors demonstrates consistency or technique variation. The motion timeline reveals pacing — whether steps are being rushed.

---

## 8. Dance & Choreography Analysis

**Use case:** A choreographer or dance school reviews student performances against a reference recording. The LLM compares timing, body position at key beats, and formation accuracy across multiple performers or takes — producing structured feedback without watching each recording individually.

**Implementation advice:** `detect_motion_events` segments phrase-level movements. `compare_frames` at beat-aligned timestamps (derived from `get_audio_transcript` if music with lyrics is present, or from known BPM) enables side-by-side student vs reference comparison. `get_motion_heatmap` reveals which body parts are most active per phrase — useful for identifying whether a student is dancing "from the arms" versus "from the core".

---

## 9. Security & Incident Review

**Use case:** A security team reviews CCTV or body-cam footage following an incident. The LLM produces a timestamped event log, identifies the individuals present during each activity window, and extracts key frames for reporting — replacing hours of manual review.

**Implementation advice:** `detect_motion_events` with low sensitivity catches all activity. `get_motion_timeline` gives the reviewer an instant overview of when events occur across a long recording. `detect_scenes` identifies camera cuts or feed switches in multi-camera compilations. `get_video_section` lets the reviewer zoom into flagged windows, and `get_precise_frame` extracts evidence-quality frames. Note: this use case should be implemented with appropriate access controls and privacy considerations.

---

## 10. Vehicle & Driving Behaviour Analysis

**Use case:** Fleet operators, driving instructors, or insurance telematics providers review dashcam footage to assess driver behaviour — identifying harsh braking events, unsafe following distances, lane discipline, and distraction moments.

**Implementation advice:** `get_motion_timeline` on dashcam footage reveals abrupt changes in scene motion (corresponding to sudden braking or swerving). `detect_motion_events` with a high sensitivity threshold flags rapid environmental changes. `get_video_section` on those windows allows detailed review. `detect_scenes` identifies cuts between different road segments or camera angles in compiled footage. For in-cab footage, `get_audio_transcript` can capture driver commentary, phone calls, or radio distractions.

---

## The Common Pattern

Across all ten domains, the same three-stage workflow applies:

1. **Triage** — `get_motion_timeline` or `detect_scenes` to identify where the interesting content is
2. **Investigate** — `detect_motion_events` / `detect_pauses` + `get_video_section` to zoom into relevant windows
3. **Document** — `get_precise_frame` + `annotate_frame` + `compare_frames` to produce evidence or reporting artefacts

The key insight is that returning **composited, timestamped frame grids directly to the LLM** — rather than saving files for a human to open — makes the LLM a genuine first-pass reviewer rather than just a file-processing orchestrator. The human only needs to engage when the LLM has already narrowed the field.
