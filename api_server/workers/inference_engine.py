# coding: utf-8
"""
InferenceEngine wrapper for audio source separation.

This module wraps the existing inference.py functionality for use in the API server,
adapting the folder-based processing to work with single files and providing
progress callbacks for task status updates.
"""

import os
import sys
import time
import librosa
import torch
import soundfile as sf
import numpy as np
import torch.nn as nn
from typing import Dict, Callable, Optional, List
from contextlib import contextmanager
from unittest.mock import patch

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from utils.audio_utils import normalize_audio, denormalize_audio
from utils.settings import get_model_from_config, parse_args_inference
from utils.model_utils import demix, prefer_target_instrument, apply_tta, load_start_checkpoint


class ProgressTracker:
    """
    Custom progress tracker that hooks into tqdm progress bars.
    
    This class intercepts tqdm progress bar updates and converts them
    to progress callbacks for the API server.
    """
    
    def __init__(self, callback: Optional[Callable[[float, str], None]] = None, 
                 base_progress: float = 35.0, max_progress: float = 70.0):
        """
        Initialize the progress tracker.
        
        Args:
            callback: Function to call with progress updates (progress, stage)
            base_progress: Starting progress percentage for this stage
            max_progress: Ending progress percentage for this stage
        """
        self.callback = callback
        self.base_progress = base_progress
        self.max_progress = max_progress
        self.total = 0
        self.current = 0
    
    def __call__(self, total=None, desc=None, leave=None):
        """
        Create a mock tqdm instance that tracks progress.
        
        Args:
            total: Total number of iterations
            desc: Description of the progress bar
            leave: Whether to leave the progress bar after completion
            
        Returns:
            Mock tqdm instance
        """
        self.total = total or 0
        self.current = 0
        self.desc = desc or "Processing"
        return self
    
    def update(self, n=1):
        """
        Update progress by n steps.
        
        Args:
            n: Number of steps to advance
        """
        self.current += n
        if self.total > 0 and self.callback:
            # Calculate progress percentage within the allocated range
            progress_ratio = min(self.current / self.total, 1.0)
            progress = self.base_progress + (self.max_progress - self.base_progress) * progress_ratio
            self.callback(progress, self.desc)
    
    def close(self):
        """Close the progress bar."""
        if self.callback:
            self.callback(self.max_progress, f"{self.desc} complete")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


@contextmanager
def progress_tracking_context(callback: Optional[Callable[[float, str], None]], 
                              base_progress: float, max_progress: float):
    """
    Context manager that patches tqdm to use our progress tracker.
    
    Args:
        callback: Progress callback function
        base_progress: Starting progress percentage
        max_progress: Ending progress percentage
        
    Yields:
        ProgressTracker instance
    """
    tracker = ProgressTracker(callback, base_progress, max_progress)
    
    # Patch tqdm in the model_utils module to use our tracker
    with patch('utils.model_utils.tqdm', tracker):
        yield tracker


class InferenceEngine:
    """
    Wrapper for the existing inference.py functionality.
    
    Adapts the folder-based proc_folder() function to work with single files
    and provides progress callback mechanism for API server integration.
    """
    
    def __init__(self, model_manager=None):
        """
        Initialize the InferenceEngine.
        
        Args:
            model_manager: Optional ModelManager instance for model loading/caching
        """
        self.model_manager = model_manager
    
    def separate_audio(
        self,
        task_id: str,
        input_path: str,
        output_dir: str,
        model_type: str,
        config_path: str,
        instruments: List[str],
        use_tta: bool,
        extract_instrumental: bool,
        output_format: str,
        pcm_type: str,
        device: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, str]:
        """
        Perform audio separation on a single file.
        
        This method wraps the existing proc_folder functionality, adapting it
        for single-file processing with progress callbacks.
        
        Args:
            task_id: Unique identifier for the task
            input_path: Path to the input audio file
            output_dir: Directory to store output files
            model_type: Model type identifier (e.g., 'mdx23c')
            config_path: Path to model configuration file
            instruments: List of instruments to separate
            use_tta: Whether to use test time augmentation
            extract_instrumental: Whether to extract instrumental track
            output_format: Output format ('wav' or 'flac')
            pcm_type: PCM type for output ('PCM_16' or 'PCM_24')
            device: Device to use for inference ('cpu', 'cuda:0', etc.)
            progress_callback: Optional callback function(progress: float, stage: str)
        
        Returns:
            Dictionary mapping instrument names to output file paths
            
        Raises:
            Exception: If audio processing fails
        """
        try:
            # Report initial progress
            if progress_callback:
                progress_callback(0.0, "Initializing")
            
            # Construct argument dictionary compatible with parse_args_inference()
            dict_args = {
                'model_type': model_type,
                'config_path': config_path,
                'start_check_point': '',  # Will be loaded from config
                'input_folder': os.path.dirname(input_path),  # Not used, but required
                'store_dir': output_dir,
                'device_ids': [int(device.split(':')[1])] if 'cuda' in device else 0,
                'extract_instrumental': extract_instrumental,
                'disable_detailed_pbar': True,  # We use our own progress tracking
                'force_cpu': device == 'cpu',
                'flac_file': output_format == 'flac',
                'pcm_type': pcm_type,
                'use_tta': use_tta,
                'draw_spectro': 0,  # Disable spectrogram generation
                'lora_checkpoint': ''
            }
            
            # Parse arguments
            args = parse_args_inference(dict_args)
            
            if progress_callback:
                progress_callback(5.0, "Loading model")
            
            # Load model and config
            torch.backends.cudnn.benchmark = True
            model, config = get_model_from_config(args.model_type, args.config_path)
            
            # Load checkpoint if specified in config
            if args.start_check_point:
                checkpoint = torch.load(args.start_check_point, weights_only=False, map_location='cpu')
                load_start_checkpoint(args, model, checkpoint, type_='inference')
            
            # Handle multi-GPU if needed
            if isinstance(args.device_ids, list) and len(args.device_ids) > 1 and not args.force_cpu:
                model = nn.DataParallel(model, device_ids=args.device_ids)
            
            model = model.to(device)
            model.eval()
            
            if progress_callback:
                progress_callback(15.0, "Model loaded")
            
            # Get sample rate from config
            sample_rate = getattr(config.audio, 'sample_rate', 44100)
            
            # Get instruments from config
            config_instruments = prefer_target_instrument(config)[:]
            
            if progress_callback:
                progress_callback(20.0, "Loading audio file")
            
            # Load audio file
            try:
                mix, sr = librosa.load(input_path, sr=sample_rate, mono=False)
            except Exception as e:
                raise Exception(f"Cannot read audio file: {input_path}. Error: {str(e)}")
            
            # Handle mono/stereo conversion
            if len(mix.shape) == 1:
                mix = np.expand_dims(mix, axis=0)
                if 'num_channels' in config.audio:
                    if config.audio['num_channels'] == 2:
                        mix = np.concatenate([mix, mix], axis=0)
            elif len(mix.shape) == 2 and mix.shape[0] == 2:
                if 'stereo' in config.model:
                    if not config.model['stereo']:
                        mix = np.mean(mix, axis=0, keepdims=True)
            
            mix_orig = mix.copy()
            
            if progress_callback:
                progress_callback(30.0, "Audio loaded")
            
            # Normalize if configured
            norm_params = None
            if 'normalize' in config.inference:
                if config.inference['normalize'] is True:
                    mix, norm_params = normalize_audio(mix)
            
            if progress_callback:
                progress_callback(35.0, "Processing audio")
            
            # Perform demixing with progress tracking
            with progress_tracking_context(progress_callback, 35.0, 70.0):
                waveforms_orig = demix(
                    config, 
                    model, 
                    mix, 
                    device, 
                    model_type=args.model_type, 
                    pbar=True  # Enable progress bar so our tracker can intercept it
                )
            
            if progress_callback:
                progress_callback(70.0, "Demixing complete")
            
            # Apply TTA if requested
            if args.use_tta:
                if progress_callback:
                    progress_callback(75.0, "Applying test time augmentation")
                waveforms_orig = apply_tta(config, model, mix, waveforms_orig, device, args.model_type)
            
            # Extract instrumental if requested
            if args.extract_instrumental:
                if progress_callback:
                    progress_callback(85.0, "Extracting instrumental")
                instr = 'vocals' if 'vocals' in config_instruments else config_instruments[0]
                waveforms_orig['instrumental'] = mix_orig - waveforms_orig[instr]
                if 'instrumental' not in config_instruments:
                    config_instruments.append('instrumental')
            
            if progress_callback:
                progress_callback(90.0, "Saving output files")
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Save output files
            output_files = {}
            codec = 'flac' if args.flac_file else 'wav'
            subtype = 'PCM_16' if args.flac_file and args.pcm_type == 'PCM_16' else 'FLOAT'
            
            for instr in config_instruments:
                if instr in waveforms_orig:
                    estimates = waveforms_orig[instr]
                    
                    # Denormalize if needed
                    if norm_params is not None:
                        if 'normalize' in config.inference:
                            if config.inference['normalize'] is True:
                                estimates = denormalize_audio(estimates, norm_params)
                    
                    # Save file
                    output_path = os.path.join(output_dir, f"{instr}.{codec}")
                    sf.write(output_path, estimates.T, sr, subtype=subtype)
                    output_files[instr] = output_path
            
            if progress_callback:
                progress_callback(100.0, "Complete")
            
            return output_files
            
        except Exception as e:
            # Convert any exception to a descriptive error
            error_msg = f"Audio separation failed: {str(e)}"
            if progress_callback:
                progress_callback(-1.0, f"Failed: {error_msg}")
            raise Exception(error_msg) from e
