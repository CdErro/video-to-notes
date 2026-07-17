import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import transcribe


class TranscribeTests(unittest.TestCase):
    def test_defaults_match_local_cpu_profile(self):
        with mock.patch("transcribe.os.cpu_count", return_value=12):
            config = transcribe.default_config()
        self.assertEqual("small", config.model)
        self.assertEqual("cpu", config.device)
        self.assertEqual("int8", config.compute_type)
        self.assertEqual(8, config.cpu_threads)
        self.assertTrue(config.vad_filter)

    def test_toml_configuration_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[whisper]\nmodel="base"\ncpu_threads=4\nvad_filter=false\n', encoding="utf-8"
            )
            config = transcribe.load_config(path)
        self.assertEqual("base", config.model)
        self.assertEqual(4, config.cpu_threads)
        self.assertFalse(config.vad_filter)

    def test_invalid_cli_style_override_is_rejected(self):
        values = {**transcribe.asdict(transcribe.default_config()), "model": "bad"}
        with self.assertRaisesRegex(transcribe.TranscriptionError, "model"):
            transcribe.validate_config(transcribe.TranscriptionConfig(**values))

    def test_invalid_compute_type_is_rejected(self):
        values = {**transcribe.asdict(transcribe.default_config()), "compute_type": 7}
        with self.assertRaisesRegex(transcribe.TranscriptionError, "compute_type"):
            transcribe.validate_config(transcribe.TranscriptionConfig(**values))

    def test_transcription_writes_srt_and_metadata(self):
        segment = types.SimpleNamespace(start=1.25, end=2.5, text=" 你好 ")
        info = types.SimpleNamespace(language="zh", language_probability=0.99)
        model = mock.Mock()
        model.transcribe.return_value = ([segment], info)
        module = types.SimpleNamespace(WhisperModel=mock.Mock(return_value=model))
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            sys.modules, {"faster_whisper": module}
        ):
            root = Path(directory)
            media = root / "audio.wav"
            media.touch()
            output = root / "raw.srt"
            metadata = transcribe.transcribe_media(
                media, output, transcribe.default_config(), "词典提示"
            )
            saved = json.loads((root / "transcription.json").read_text())
            srt = output.read_text(encoding="utf-8")

        self.assertIn("00:00:01,250 --> 00:00:02,500", srt)
        self.assertEqual("zh", metadata["language"])
        self.assertEqual("faster-whisper", saved["engine"])
        model.transcribe.assert_called_once_with(
            str(media), language=None, initial_prompt="词典提示", vad_filter=True, beam_size=5
        )

    def test_empty_transcript_fails_without_output(self):
        model = mock.Mock()
        model.transcribe.return_value = ([], types.SimpleNamespace(language="zh"))
        module = types.SimpleNamespace(WhisperModel=mock.Mock(return_value=model))
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            sys.modules, {"faster_whisper": module}
        ):
            root = Path(directory)
            media = root / "audio.wav"
            media.touch()
            with self.assertRaisesRegex(transcribe.TranscriptionError, "no speech"):
                transcribe.transcribe_media(media, root / "raw.srt", transcribe.default_config())

    def test_empty_segments_do_not_create_srt_index_gaps(self):
        segments = [
            types.SimpleNamespace(start=0, end=1, text="  "),
            types.SimpleNamespace(start=1, end=2, text="有效内容"),
        ]
        model = mock.Mock()
        model.transcribe.return_value = (
            segments, types.SimpleNamespace(language="zh", language_probability=1.0)
        )
        module = types.SimpleNamespace(WhisperModel=mock.Mock(return_value=model))
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            sys.modules, {"faster_whisper": module}
        ):
            root = Path(directory)
            media = root / "audio.wav"
            media.touch()
            output = root / "raw.srt"
            transcribe.transcribe_media(media, output, transcribe.default_config())
            srt = output.read_text(encoding="utf-8")

        self.assertTrue(srt.startswith("1\n"))


if __name__ == "__main__":
    unittest.main()
