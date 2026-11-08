from __future__ import annotations

import re
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from app.evaluation import recorder
from app.evaluation.recorder import (
    IO,
    Noise,
    Quit,
    RecorderError,
    Turn,
    assemble,
    collect_clips,
    duration_s,
    load_provenance,
    parse_script,
    pick_device,
    prepare_clip,
    write_provenance,
)
from tests.helpers import make_wav

SCRIPTS = Path(__file__).resolve().parents[2] / "data" / "scripts"
RATE = 48000


def tone(path: Path, lead=0.5, speech=1.0, tail=0.5, amp=6000) -> Path:
    """A clip with silence either side of a 'voice', like a take that was started and stopped by keypresses."""
    frames = b"\x00\x00" * int(RATE * lead)
    frames += b"".join(
        int(amp if (i // 60) % 2 else -amp).to_bytes(2, "little", signed=True) for i in range(int(RATE * speech))
    )
    frames += b"\x00\x00" * int(RATE * tail)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    return path


def stat(path: Path, key: str) -> float:
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "astats", "-f", "null", "-"], capture_output=True, text=True
    )
    return float(re.search(rf"{key}: (-?[\d.]+|-inf)", res.stderr).group(1).replace("-inf", "-200"))


# ---- reading the scripts -----------------------------------------------------------------------------------------


def test_every_real_script_parses_with_no_markers_left():
    total = 0
    for path in sorted(SCRIPTS.glob("call_*.md")):
        script = parse_script(path)
        spoken = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith(("AGENT:", "BORROWER:"))]
        assert len(script.turns) == len(spoken), path.name
        assert all("<<" not in t.text and t.text for t in script.turns), path.name
        assert script.turns[0].speaker == "agent" and script.header["language"] in ("Hinglish", "Marathi")
        assert [t.index for t in script.turns] == list(range(len(script.turns)))
        total += len(script.turns)
    assert total == 602  # 314 agent and 288 borrower lines in the 30 scripts


def test_a_marked_line_keeps_its_key_words_and_loses_only_the_marker():
    script = parse_script(SCRIPTS / "call_07.md")
    line = next(t for t in script.turns if "office mein sabko bata denge" in t.text)
    assert line.text.endswith("phir dekhte hain.") and "<<V5>>" not in line.text
    assert script.header["time"] == "21:40" and script.header["agent"] == "Rohit Patil"
    assert script.notes.startswith("Two violations.")


def test_marathi_lines_keep_the_latin_reading_aid_separately():
    script = parse_script(SCRIPTS / "call_05.md")
    first = script.turns[0]
    assert first.text.startswith("नमस्कार") and first.latin.startswith("Namaskar")  # shown to the reader, never spoken
    assert script.language == "marathi" and all(not t.text.startswith(">") for t in script.turns)


def test_a_file_with_no_dialogue_is_an_error(tmp_path):
    (tmp_path / "x.md").write_text("# x\n\n[Agent: A]\n")
    with pytest.raises(RecorderError, match="No AGENT or BORROWER lines"):
        parse_script(tmp_path / "x.md")


# ---- turning takes into one call ---------------------------------------------------------------------------------


def test_prepare_clip_cuts_the_silence_the_keypresses_leave(tmp_path):
    src = tone(tmp_path / "a.wav", lead=1.0, speech=0.6, tail=1.0)
    prepare_clip(src, tmp_path / "p.wav")
    assert 0.6 < duration_s(tmp_path / "p.wav") < 1.1  # the voice plus a short pad, not 2.6 s


def test_a_take_with_no_speech_is_refused_with_advice(tmp_path):
    silent = tmp_path / "s.wav"
    tone(silent, lead=1.0, speech=0.0, tail=0.0)
    with pytest.raises(RecorderError, match="no speech"):
        prepare_clip(silent, tmp_path / "p.wav")


def clips_for(tmp_path, speakers=("agent", "borrower", "agent")):
    out = []
    for i, who in enumerate(speakers):
        out.append((Turn(i, who, f"line {i}"), tone(tmp_path / f"c{i}.wav", speech=1.0 + i * 0.2)))
    return out


def test_assemble_joins_clips_with_pauses_into_one_mono_m4a(tmp_path):
    seconds = assemble(clips_for(tmp_path), tmp_path / "out" / "call.m4a", seed=1)
    speech = 1.0 + 1.2 + 1.4
    assert speech + 0.5 < seconds < speech + 3.0  # three clips, two pauses, a little padding
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,channels,sample_rate", "-of", "csv=p=0",
         str(tmp_path / "out" / "call.m4a")], capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    assert info == "aac,48000,1" or info == "aac,1,48000"  # ffprobe orders the fields as it likes


def test_the_pauses_are_repeatable_and_change_with_the_seed(tmp_path):
    clips = clips_for(tmp_path)
    a = assemble(clips, tmp_path / "a.m4a", seed=7)
    b = assemble(clips, tmp_path / "b.m4a", seed=7)
    c = assemble(clips, tmp_path / "c.m4a", seed=8)
    assert a == pytest.approx(b, abs=0.05) and abs(a - c) > 0.01


def test_a_turn_change_pauses_longer_than_continuing_to_speak(tmp_path):
    same = [(Turn(i, "agent", "x"), tone(tmp_path / f"s{i}.wav")) for i in range(6)]
    change = [(Turn(i, "agent" if i % 2 == 0 else "borrower", "x"), tone(tmp_path / f"s{i}.wav")) for i in range(6)]
    assert assemble(change, tmp_path / "ch.m4a", seed=3) > assemble(same, tmp_path / "sm.m4a", seed=3) + 0.5


def test_quiet_and_loud_takes_end_up_at_a_similar_level(tmp_path):
    quiet = tone(tmp_path / "q.wav", amp=800)
    loud = tone(tmp_path / "l.wav", amp=16000)
    prepare_clip(quiet, tmp_path / "pq.wav")
    prepare_clip(loud, tmp_path / "pl.wav")
    assert abs(stat(tmp_path / "pq.wav", "RMS level dB") - stat(tmp_path / "pl.wav", "RMS level dB")) < 3.0


def test_noise_raises_the_floor_between_words_and_leaves_the_call_length_alone(tmp_path):
    clips = clips_for(tmp_path)
    clean = tmp_path / "clean.m4a"
    noisy = tmp_path / "noisy.m4a"
    d1 = assemble(clips, clean, seed=1)
    d2 = assemble(clips, noisy, seed=1, noise=Noise(kind="brown", level=0.05))
    assert abs(d1 - d2) < 0.1
    assert stat(clean, "RMS through dB") < -70 and stat(noisy, "RMS through dB") > -55


def test_a_noise_file_is_looped_under_the_call(tmp_path):
    bed = make_wav(tmp_path / "bed.wav", seconds=1)  # shorter than the call
    clips = clips_for(tmp_path)
    out = tmp_path / "n.m4a"
    assemble(clips, out, noise=Noise(file=bed, level=0.03))
    assert duration_s(out) > 3.5 and stat(out, "RMS through dB") > -60


# ---- the session -------------------------------------------------------------------------------------------------


class Fake:
    """A scripted person and machine: records what was asked of them."""

    def __init__(self, answers, tmp_path):
        self.answers = list(answers)
        self.recorded: list[str] = []
        self.spoken: list[str] = []
        self.played: list[str] = []
        self.shown: list[str] = []
        self.asked: list[str] = []
        self.tmp = tmp_path

    def io(self) -> IO:
        def ask(prompt):
            self.asked.append(prompt)
            return self.answers.pop(0) if self.answers else ""

        def record(path):
            self.recorded.append(path.name)
            tone(path)

        def speak(text, path):
            self.spoken.append(text)
            tone(path, speech=0.8)

        return IO(ask, self.shown.append, record, speak, lambda p: self.played.append(p.name))


@pytest.fixture
def small_script(tmp_path):
    (tmp_path / "call_99.md").write_text(
        "# call_99\n\n[Agent: A | Borrower: B | Loan: L | Time: 11:00 | Language: Hinglish | Noise: Quiet]\n\n"
        "Recording notes: test.\n\nAGENT: Namaste.\nBORROWER: Haan ji.\nAGENT: Kab tak? <<V9>>\nBORROWER: Kal.\n",
        encoding="utf-8",
    )
    return parse_script(tmp_path / "call_99.md")


def test_the_session_records_agent_lines_and_speaks_borrower_lines(small_script, tmp_path):
    fake = Fake(["", "", "", ""], tmp_path)  # start, keep, start, keep
    clips = collect_clips(small_script, tmp_path / "takes", fake.io())
    assert [t.speaker for t, _ in clips] == ["agent", "borrower", "agent", "borrower"]
    assert fake.spoken == ["Haan ji.", "Kal."] and len(fake.recorded) == 2
    assert len(fake.played) == 2 and all(p.exists() for _, p in clips)
    assert any("Kab tak?" in s and "<<" not in s for s in fake.shown)  # the marker is never shown to the speaker


def test_redo_and_playback_work_and_a_redo_replaces_the_take(small_script, tmp_path):
    fake = Fake(["", "p", "r", "", "", "", ""], tmp_path)  # start, play, redo, start again, keep, start, keep
    collect_clips(small_script, tmp_path / "takes", fake.io())
    assert fake.recorded == ["turn_000_agent.wav", "turn_000_agent.wav", "turn_002_agent.wav"]
    assert fake.played.count("turn_000_agent.wav") == 1  # the one playback; borrower lines play their own clips


def test_quitting_keeps_takes_and_a_second_run_resumes_without_re_recording(small_script, tmp_path):
    takes = tmp_path / "takes"
    first = Fake(["", "", "q"], tmp_path)  # line 1 recorded and kept; at line 3 the person quits
    with pytest.raises(Quit):
        collect_clips(small_script, takes, first.io())
    assert (takes / "turn_000_agent.wav").exists() and not (takes / "turn_002_agent.wav").exists()

    second = Fake(["", "", "", ""], tmp_path)  # keep earlier take, then record line 3 and keep it
    collect_clips(small_script, takes, second.io())
    assert second.recorded == ["turn_002_agent.wav"]  # line 1 was not recorded again
    assert second.spoken == ["Kal."]  # the first borrower clip was reused; only the one not yet spoken is new


def test_fresh_ignores_earlier_takes(small_script, tmp_path):
    takes = tmp_path / "takes"
    collect_clips(small_script, takes, Fake(["", "", "", ""], tmp_path).io())
    again = Fake(["", "", "", ""], tmp_path)
    collect_clips(small_script, takes, again.io(), resume=False)
    assert len(again.recorded) == 2 and len(again.spoken) == 2


def test_the_marathi_reading_aid_is_shown_to_the_speaker(tmp_path):
    script = parse_script(SCRIPTS / "call_05.md")
    fake = Fake([], tmp_path)
    with pytest.raises(Quit):
        collect_clips(script, tmp_path / "t", IO(lambda p: "q", fake.shown.append, None, None, None))
    assert any("Namaskar" in s for s in fake.shown)


# ---- the command line --------------------------------------------------------------------------------------------


@pytest.fixture
def dirs(tmp_path, small_script):
    for d in ("audio", "meta", "takes"):
        (tmp_path / d).mkdir()
    return ["--scripts-dir", str(tmp_path), "--audio-dir", str(tmp_path / "audio"),
            "--meta-dir", str(tmp_path / "meta"), "--takes-dir", str(tmp_path / "takes")]  # fmt: skip


def test_end_to_end_writes_the_call_and_marks_it_synthetic(dirs, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(recorder, "have_voice", lambda v: True)
    fake = Fake([""] * 4, tmp_path)
    code = recorder.main(["call_99", "--voice", "Rishi", "--noise", "pink", *dirs], io=fake.io())
    out = capsys.readouterr().out
    assert code == 0 and (tmp_path / "audio" / "call_99.m4a").exists()
    assert "Notes for you (do NOT read these aloud)" in out and "synthetic-borrower call" in out
    meta = load_provenance(tmp_path / "meta")["call_99"]
    assert (
        meta["borrower"] == "synthetic"
        and meta["voice"] == "Rishi"
        and meta["noise"] == {"synthetic": "pink", "level": 0.04}
    )
    assert meta["turns"] == {"agent": 2, "borrower": 2}
    # it will not overwrite a finished call by accident
    assert recorder.main(["call_99", *dirs], io=fake.io()) == 1
    assert "already exists" in capsys.readouterr().err


def test_quitting_midway_says_how_to_carry_on(dirs, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(recorder, "have_voice", lambda v: True)
    code = recorder.main(["call_99", *dirs], io=Fake(["", "", "q"], tmp_path).io())
    assert code == 0 and "run the same command again" in capsys.readouterr().out
    assert not (tmp_path / "audio" / "call_99.m4a").exists()


def test_assemble_only_needs_every_line_recorded(dirs, tmp_path, capsys):
    assert recorder.main(["call_99", "--assemble-only", *dirs]) == 1
    assert "Only 0 of 4 lines have a take" in capsys.readouterr().err


def test_a_marathi_call_is_refused_because_there_is_no_marathi_voice(tmp_path, capsys):
    code = recorder.main(["call_05", "--audio-dir", str(tmp_path), "--scripts-dir", str(SCRIPTS)])
    assert code == 1 and "no Marathi voice" in capsys.readouterr().err


def test_a_missing_voice_is_reported(dirs, monkeypatch, capsys):
    monkeypatch.setattr(recorder, "have_voice", lambda v: False)
    assert recorder.main(["call_99", "--voice", "Nobody", *dirs]) == 1
    assert "'Nobody' is not installed" in capsys.readouterr().err


def test_dry_run_shows_the_lines_without_touching_anything(dirs, tmp_path, capsys):
    assert recorder.main(["call_99", "--dry-run", *dirs]) == 0
    out = capsys.readouterr().out
    assert "AGENT     Namaste." in out and "Kab tak?" in out and not list((tmp_path / "audio").iterdir())


def test_a_noisy_call_gets_a_hint_about_noise(tmp_path, capsys):
    code = recorder.main(["call_13", "--dry-run", "--scripts-dir", str(SCRIPTS), "--audio-dir", str(tmp_path)])
    assert code == 0 and "meant to be noisy (" in capsys.readouterr().out


def test_the_built_in_microphone_is_preferred_over_bluetooth_earbuds():
    devices = [(0, "realme Buds T310"), (1, "MacBook Air Microphone")]
    assert pick_device(devices) == (1, "MacBook Air Microphone")
    assert pick_device(devices, 0) == (0, "realme Buds T310")
    assert pick_device([(0, "USB Mic")]) == (0, "USB Mic")
    with pytest.raises(RecorderError, match="No audio device number 5"):
        pick_device(devices, 5)
    with pytest.raises(RecorderError, match="No microphone"):
        pick_device([])


# ---- provenance and the report -----------------------------------------------------------------------------------


def test_load_provenance_of_a_missing_folder_is_empty(tmp_path):
    assert load_provenance(tmp_path / "none") == {}


def test_provenance_round_trips(tmp_path, small_script):
    write_provenance(small_script, voice="Rishi", rate=160, noise=None, seconds=96.44, directory=tmp_path)
    got = load_provenance(tmp_path)["call_99"]
    assert got["duration_s"] == 96.4 and got["noise"] is None and got["voice_rate"] == 160


# ---- the real voice on this machine ------------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "darwin" or not recorder.have_voice("Rishi"), reason="needs the macOS voice Rishi")
def test_the_built_in_voice_really_speaks_a_hinglish_line(tmp_path):
    out = tmp_path / "v.wav"
    recorder.say_speaker("Rishi", 165)("Haan ji, boliye. Main kal tak kar dunga.", out)
    assert 1.5 < duration_s(out) < 8 and stat(out, "RMS level dB") > -45
