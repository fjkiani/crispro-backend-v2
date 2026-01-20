"""
Checkpoint Management Module

Unified checkpoint save/load/resume functionality.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime


def find_largest_checkpoint(output_dir: Path) -> Tuple[Optional[Path], Optional[Dict[str, Any]], int]:
    """
    Find the largest checkpoint file and load it.
    
    Args:
        output_dir: Directory to search for checkpoints
    
    Returns:
        Tuple of (checkpoint_file, checkpoint_data, patient_count)
        Returns (None, None, 0) if no checkpoint found
    """
    checkpoints = list(output_dir.glob("checkpoint_*patients.json"))
    if not checkpoints:
        return None, None, 0
    
    # Extract patient count from filename and find largest
    largest_checkpoint = None
    largest_n = 0
    
    for cp in checkpoints:
        try:
            # Extract number from "checkpoint_Npatients.json"
            n_str = cp.stem.replace("checkpoint_", "").replace("patients", "")
            n = int(n_str)
            if n > largest_n:
                largest_n = n
                largest_checkpoint = cp
        except (ValueError, AttributeError):
            continue
    
    if largest_checkpoint and largest_checkpoint.exists():
        try:
            with open(largest_checkpoint, 'r') as f:
                checkpoint_data = json.load(f)
                return largest_checkpoint, checkpoint_data, largest_n
        except Exception as e:
            print(f"   ⚠️  Failed to load checkpoint {largest_checkpoint.name}: {e}")
    
    return None, None, 0


def load_checkpoint(checkpoint_file: Path) -> Optional[Dict[str, Any]]:
    """
    Load a specific checkpoint file.
    
    Args:
        checkpoint_file: Path to checkpoint file
    
    Returns:
        Checkpoint data dict, or None if load failed
    """
    if not checkpoint_file.exists():
        return None
    
    try:
        with open(checkpoint_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"   ❌ Checkpoint load failed: {e}")
        return None


def save_checkpoint(
    checkpoint_file: Path,
    predictions: list,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Save checkpoint with predictions and metadata.
    
    Args:
        checkpoint_file: Path to save checkpoint
        predictions: List of prediction results
        metadata: Optional metadata dict
    
    Returns:
        True if save succeeded, False otherwise
    """
    try:
        total_successful = sum(1 for p in predictions if "error" not in p)
        total_errors = len(predictions) - total_successful
        
        checkpoint_data = {
            "predictions": predictions,
            "n_patients": len(predictions),
            "timestamp": datetime.now().isoformat(),
            "successful": total_successful,
            "errors": total_errors,
        }
        
        if metadata:
            checkpoint_data.update(metadata)
        
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"   ❌ Checkpoint save failed: {e}")
        return False


