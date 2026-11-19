"""DSP mathematical design, real-time generators, and audio processing engine."""

from .filter_design import (
    ISO_10_BANDS,
    ISO_20_BANDS,
    ISO_30_BANDS,
    clamp_freq,
    compute_band_metrics,
    compute_ideal_response,
    compute_impulse_response,
    compute_parallel_response,
    compute_series_response,
    compute_sos_response,
    design_filter,
    exact_third_octave_freq,
    from_cutoffs,
)
from .generators import GeneratorType, SignalGenerator
from .processor import (
    ChannelStripConfig,
    FilterDSPProcessor,
    GraphicEQConfig,
    NetworkConfig,
    ParametricEQConfig,
    SingleFilterConfig,
    StageConfig,
)

__all__ = [
    "ISO_10_BANDS",
    "ISO_20_BANDS",
    "ISO_30_BANDS",
    "ChannelStripConfig",
    "FilterDSPProcessor",
    "GeneratorType",
    "GraphicEQConfig",
    "NetworkConfig",
    "ParametricEQConfig",
    "SignalGenerator",
    "SingleFilterConfig",
    "StageConfig",
    "clamp_freq",
    "compute_band_metrics",
    "compute_ideal_response",
    "compute_impulse_response",
    "compute_parallel_response",
    "compute_series_response",
    "compute_sos_response",
    "design_filter",
    "exact_third_octave_freq",
    "from_cutoffs",
]
