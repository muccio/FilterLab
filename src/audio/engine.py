"""Real-time audio streaming engine (Internal Generator, Audio File, Live Microphone)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import sounddevice as sd

from src.dsp.generators import SignalGenerator
from src.dsp.processor import FilterDSPProcessor
from .file_loader import LoadedAudio, load_audio_file


class SourceMode(str, Enum):
    INTERNAL = "internal"
    FILE = "file"
    MIC = "mic"


@dataclass
class AudioDeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi_name: str = ""


def list_audio_devices() -> dict[str, Any]:
    """Query audio input/output devices safely (works even on headless CI systems)."""
    inputs: list[AudioDeviceInfo] = []
    outputs: list[AudioDeviceInfo] = []
    default_in: int | None = None
    default_out: int | None = None

    try:
        devs = sd.query_devices()
        hostapis = sd.query_hostapis()
        defaults = sd.default.device
        if isinstance(defaults, (list, tuple)) and len(defaults) >= 2:
            default_in = int(defaults[0]) if defaults[0] is not None and defaults[0] >= 0 else None
            default_out = int(defaults[1]) if defaults[1] is not None and defaults[1] >= 0 else None

        for idx, d in enumerate(devs):
            ha_idx = int(d.get("hostapi", 0))
            ha_name = ""
            if 0 <= ha_idx < len(hostapis):
                ha_name = str(hostapis[ha_idx].get("name", ""))
            info = AudioDeviceInfo(
                index=idx,
                name=str(d.get("name", f"Device {idx}")),
                max_input_channels=int(d.get("max_input_channels", 0)),
                max_output_channels=int(d.get("max_output_channels", 0)),
                default_samplerate=float(d.get("default_samplerate", 48000.0)),
                hostapi_name=ha_name,
            )
            if info.max_input_channels > 0:
                inputs.append(info)
            if info.max_output_channels > 0:
                outputs.append(info)
    except Exception:
        pass

    return {
        "inputs": inputs,
        "outputs": outputs,
        "default_in": default_in,
        "default_out": default_out,
    }


class AudioEngine:
    """Manages real-time PortAudio streams, lock-safe ring buffers, and source routing."""

    RING_SIZE = 4096

    def __init__(self, sample_rate: int = 48000, block_size: int = 1024) -> None:
        self.sample_rate: int = int(sample_rate)
        self.block_size: int = int(block_size)

        self.generator = SignalGenerator(sample_rate=float(self.sample_rate))
        self.processor = FilterDSPProcessor(sample_rate=float(self.sample_rate))

        self.source_mode: SourceMode = SourceMode.INTERNAL
        self.input_device: int | None = None
        self.output_device: int | None = None
        self.mic_gain_db: float = 0.0

        self._stream: sd.OutputStream | sd.Stream | None = None
        self._running: bool = False
        self.last_error: str = ""

        # File player state
        self._file_lock = threading.Lock()
        self._loaded_audio: LoadedAudio | None = None
        self._file_pos: int = 0
        self._file_playing: bool = False
        self._file_loop: bool = True

        # Pre-allocated visualization ring buffers
        self._vis_lock = threading.Lock()
        self._pre_ring = np.zeros(self.RING_SIZE, dtype=np.float32)
        self._post_ring = np.zeros(self.RING_SIZE, dtype=np.float32)
        self._ring_idx: int = 0
        self._in_peak_db: float = -60.0
        self._out_peak_l_db: float = -60.0
        self._out_peak_r_db: float = -60.0
        self._aux_peak_db: float = -60.0
        self._overload: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def loaded_audio(self) -> LoadedAudio | None:
        with self._file_lock:
            return self._loaded_audio

    def set_source_mode(self, mode: SourceMode | str) -> None:
        new_mode = SourceMode(mode)
        if new_mode != self.source_mode:
            was_running = self._running
            if was_running:
                self.stop()
            self.source_mode = new_mode
            self.processor.reset_states()
            if was_running:
                self.start()

    def set_devices(self, input_device: int | None, output_device: int | None) -> None:
        changed = (input_device != self.input_device) or (output_device != self.output_device)
        self.input_device = input_device
        self.output_device = output_device
        if changed and self._running:
            self.stop()
            self.start()

    def set_mic_gain_db(self, gain_db: float) -> None:
        self.mic_gain_db = max(-24.0, min(24.0, float(gain_db)))

    def load_file(self, path: str) -> LoadedAudio:
        loaded = load_audio_file(path, target_sr=self.sample_rate)
        with self._file_lock:
            self._loaded_audio = loaded
            self._file_pos = 0
            self._file_playing = True
        return loaded

    def file_play(self) -> None:
        with self._file_lock:
            if self._loaded_audio is not None:
                self._file_playing = True

    def file_pause(self) -> None:
        with self._file_lock:
            self._file_playing = False

    def file_stop(self) -> None:
        with self._file_lock:
            self._file_playing = False
            self._file_pos = 0

    def file_seek(self, ratio: float) -> None:
        r = max(0.0, min(1.0, float(ratio)))
        with self._file_lock:
            if self._loaded_audio is not None:
                total = self._loaded_audio.samples.shape[0]
                self._file_pos = min(max(0, int(r * total)), max(0, total - 1))

    def set_file_loop(self, loop: bool) -> None:
        with self._file_lock:
            self._file_loop = bool(loop)

    def _read_file_block(self, frames: int) -> np.ndarray:
        out = np.zeros((frames, 2), dtype=np.float32)
        with self._file_lock:
            audio = self._loaded_audio
            if audio is None or not self._file_playing or audio.samples.shape[0] == 0:
                return out
            total = audio.samples.shape[0]
            pos = self._file_pos
            written = 0
            while written < frames:
                remain = frames - written
                avail = total - pos
                take = min(remain, avail)
                if take > 0:
                    out[written : written + take] = audio.samples[pos : pos + take]
                    written += take
                    pos += take
                if pos >= total:
                    if self._file_loop:
                        pos = 0
                    else:
                        self._file_playing = False
                        pos = total
                        break
            self._file_pos = pos
        return out

    def _push_visual_telemetry(self, telemetry: dict[str, Any]) -> None:
        pre = telemetry["pre_block_mono"]
        post = telemetry["post_block_mono"]
        n = min(len(pre), self.RING_SIZE)
        # Never block the real-time audio callback thread waiting on GUI snapshots
        if not self._vis_lock.acquire(blocking=False):
            return
        try:
            idx = self._ring_idx
            first = min(n, self.RING_SIZE - idx)
            self._pre_ring[idx : idx + first] = pre[:first]
            self._post_ring[idx : idx + first] = post[:first]
            if first < n:
                rem = n - first
                self._pre_ring[:rem] = pre[first : first + rem]
                self._post_ring[:rem] = post[first : first + rem]
            self._ring_idx = (idx + n) % self.RING_SIZE

            # Smooth meter decay while preserving fast peaks
            self._in_peak_db = max(telemetry["in_peak_db"], self._in_peak_db - 2.5)
            self._out_peak_l_db = max(telemetry["out_peak_l_db"], self._out_peak_l_db - 2.5)
            self._out_peak_r_db = max(telemetry["out_peak_r_db"], self._out_peak_r_db - 2.5)
            self._aux_peak_db = max(telemetry["aux_peak_db"], self._aux_peak_db - 2.5)
            self._overload = bool(telemetry["overload"])
        finally:
            self._vis_lock.release()

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        _ = (time_info, status)
        try:
            if self.source_mode == SourceMode.INTERNAL:
                in_block = self.generator.generate(frames)
            elif self.source_mode == SourceMode.FILE:
                in_block = self._read_file_block(frames)
            else:
                in_block = np.zeros((frames, 2), dtype=np.float32)
            out_block, telemetry = self.processor.process_block(in_block)
            outdata[:] = out_block
            self._push_visual_telemetry(telemetry)
        except Exception:
            outdata.fill(0.0)

    def _duplex_callback(
        self, indata: np.ndarray, outdata: np.ndarray, frames: int, time_info: Any, status: Any
    ) -> None:
        _ = (time_info, status)
        try:
            gain = 10.0 ** (self.mic_gain_db / 20.0)
            if indata.shape[1] == 1:
                mono = indata[:, 0] * gain
                in_block = np.column_stack((mono, mono)).astype(np.float32)
            else:
                in_block = (indata[:, :2] * gain).astype(np.float32)
            out_block, telemetry = self.processor.process_block(in_block)
            outdata[:] = out_block
            self._push_visual_telemetry(telemetry)
        except Exception:
            outdata.fill(0.0)

    def _apply_sample_rate(self, sr: int) -> None:
        if sr != self.sample_rate:
            self.sample_rate = int(sr)
            self.generator.set_sample_rate(float(sr))
            self.processor.set_sample_rate(float(sr))
            with self._file_lock:
                if self._loaded_audio is not None and self._loaded_audio.sample_rate != sr:
                    try:
                        self._loaded_audio = load_audio_file(self._loaded_audio.path, target_sr=sr)
                        self._file_pos = 0
                    except Exception:
                        pass

    def start(self) -> bool:
        """Start real-time audio stream. Returns True on success, False with last_error set."""
        if self._running:
            return True
        self.last_error = ""
        self.processor.reset_states()

        candidates_sr = [self.sample_rate]
        try:
            if self.output_device is not None:
                dev_info = sd.query_devices(self.output_device)
            else:
                dev_info = sd.query_devices(kind="output")
            def_sr = int(round(float(dev_info.get("default_samplerate", 48000.0))))
            if def_sr not in candidates_sr:
                candidates_sr.append(def_sr)
        except Exception:
            pass
        if 44100 not in candidates_sr:
            candidates_sr.append(44100)

        last_exc: Exception | None = None
        for sr in candidates_sr:
            try:
                self._apply_sample_rate(sr)
                if self.source_mode == SourceMode.MIC:
                    in_ch = 1
                    try:
                        in_dev = (
                            sd.query_devices(self.input_device)
                            if self.input_device is not None
                            else sd.query_devices(kind="input")
                        )
                        in_ch = 2 if int(in_dev.get("max_input_channels", 1)) >= 2 else 1
                    except Exception:
                        in_ch = 1

                    device_arg = (self.input_device, self.output_device)
                    if self.input_device is None and self.output_device is None:
                        device_arg = None

                    stream = sd.Stream(
                        samplerate=sr,
                        blocksize=min(512, self.block_size),
                        latency="low",
                        device=device_arg,
                        channels=(in_ch, 2),
                        dtype="float32",
                        callback=self._duplex_callback,
                    )
                else:
                    # Only OutputStream is opened -> never triggers macOS mic permissions!
                    stream = sd.OutputStream(
                        samplerate=sr,
                        blocksize=self.block_size,
                        latency="high",
                        device=self.output_device,
                        channels=2,
                        dtype="float32",
                        callback=self._output_callback,
                    )
                stream.start()
                self._stream = stream
                self._running = True
                self.last_error = ""
                return True
            except Exception as exc:
                last_exc = exc

        if self.source_mode == SourceMode.MIC:
            self.last_error = (
                f"Impossibile aprire il microfono / stream audio ({last_exc}). "
                "Verifica i permessi del microfono nelle impostazioni di sistema."
            )
        else:
            self.last_error = f"Impossibile avviare lo stream audio di uscita: {last_exc}"
        self._running = False
        self._stream = None
        return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._running = False

    def get_visual_snapshot(self, include_waves: bool = True) -> dict[str, Any]:
        """Thread-safe snapshot of ring buffers, meters, and playback state for UI."""
        with self._vis_lock:
            if include_waves:
                idx = self._ring_idx
                pre = np.concatenate((self._pre_ring[idx:], self._pre_ring[:idx])).copy()
                post = np.concatenate((self._post_ring[idx:], self._post_ring[:idx])).copy()
            else:
                pre = np.empty(0, dtype=np.float32)
                post = np.empty(0, dtype=np.float32)
            in_db = self._in_peak_db
            out_l_db = self._out_peak_l_db
            out_r_db = self._out_peak_r_db
            aux_db = self._aux_peak_db
            overload = self._overload

        with self._file_lock:
            file_ratio = 0.0
            file_dur = 0.0
            file_playing = self._file_playing
            if self._loaded_audio is not None and self._loaded_audio.samples.shape[0] > 0:
                file_ratio = self._file_pos / float(self._loaded_audio.samples.shape[0])
                file_dur = self._loaded_audio.duration_s

        return {
            "pre_samples": pre,
            "post_samples": post,
            "in_peak_db": in_db,
            "out_peak_l_db": out_l_db,
            "out_peak_r_db": out_r_db,
            "aux_peak_db": aux_db,
            "overload": overload,
            "sample_rate": self.sample_rate,
            "file_pos_ratio": file_ratio,
            "file_duration_s": file_dur,
            "file_playing": file_playing,
            "running": self._running,
            "last_error": self.last_error,
        }
