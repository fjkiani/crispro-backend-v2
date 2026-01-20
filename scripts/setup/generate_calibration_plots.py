"""
Generate calibration plots and reliability metrics for MM predictions.
Publication-ready calibration analysis with confidence binning and ECE calculation.
"""
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class CalibrationMetrics:
    """Calibration metrics for publication."""
    ece: float  # Expected Calibration Error
    mce: float  # Maximum Calibration Error
    bin_accuracies: List[float]
    bin_confidences: List[float]
    bin_counts: List[int]

def load_ablation_results(results_dir: Path) -> Dict[str, Any]:
    """Load most recent ablation results."""
    results_files = list(results_dir.glob("ablation_results_*.json"))
    if not results_files:
        raise FileNotFoundError(f"No ablation results found in {results_dir}")
    
    latest_file = max(results_files, key=lambda p: p.stat().st_mtime)
    with open(latest_file) as f:
        return json.load(f)

def compute_calibration(predictions: List[Dict[str, Any]], n_bins: int = 10) -> CalibrationMetrics:
    """
    Compute calibration metrics using confidence binning.
    
    Args:
        predictions: List of dicts with 'confidence' and 'correct' keys
        n_bins: Number of bins for calibration curve
    
    Returns:
        CalibrationMetrics with ECE, MCE, and bin statistics
    """
    # Filter to only variants with expected drugs (exclude TP53)
    valid_preds = [p for p in predictions if p['correct'] is not None]
    
    if not valid_preds:
        return CalibrationMetrics(0.0, 0.0, [], [], [])
    
    # Extract confidences and correctness
    confidences = np.array([p['confidence'] for p in valid_preds])
    correctness = np.array([1.0 if p['correct'] else 0.0 for p in valid_preds])
    
    # Create bins
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_accuracies = []
    bin_confidences = []
    bin_counts = []
    
    ece = 0.0  # Expected Calibration Error
    mce = 0.0  # Maximum Calibration Error
    
    for i in range(n_bins):
        bin_mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
        if i == n_bins - 1:  # Include right edge in last bin
            bin_mask = (confidences >= bin_edges[i]) & (confidences <= bin_edges[i + 1])
        
        bin_count = np.sum(bin_mask)
        
        if bin_count > 0:
            bin_accuracy = np.mean(correctness[bin_mask])
            bin_confidence = np.mean(confidences[bin_mask])
            
            bin_accuracies.append(bin_accuracy)
            bin_confidences.append(bin_confidence)
            bin_counts.append(int(bin_count))
            
            # Update ECE and MCE
            calibration_error = abs(bin_accuracy - bin_confidence)
            ece += (bin_count / len(valid_preds)) * calibration_error
            mce = max(mce, calibration_error)
        else:
            bin_accuracies.append(0.0)
            bin_confidences.append((bin_edges[i] + bin_edges[i + 1]) / 2)
            bin_counts.append(0)
    
    return CalibrationMetrics(ece, mce, bin_accuracies, bin_confidences, bin_counts)

def plot_calibration_curve(
    metrics: CalibrationMetrics,
    mode: str,
    output_path: Path
):
    """Generate reliability diagram (calibration curve)."""
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # Perfect calibration line
    ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', linewidth=2)
    
    # Actual calibration
    valid_bins = [i for i, c in enumerate(metrics.bin_counts) if c > 0]
    if valid_bins:
        confs = [metrics.bin_confidences[i] for i in valid_bins]
        accs = [metrics.bin_accuracies[i] for i in valid_bins]
        counts = [metrics.bin_counts[i] for i in valid_bins]
        
        # Plot with marker sizes proportional to bin counts
        sizes = [c * 100 for c in counts]
        ax.scatter(confs, accs, s=sizes, alpha=0.6, label=f'{mode} Model', color='#2E86AB')
        ax.plot(confs, accs, '-o', alpha=0.3, color='#2E86AB')
    
    ax.set_xlabel('Confidence', fontsize=14, fontweight='bold')
    ax.set_ylabel('Accuracy', fontsize=14, fontweight='bold')
    ax.set_title(f'Reliability Diagram: {mode}\nECE={metrics.ece:.3f}, MCE={metrics.mce:.3f}', 
                 fontsize=16, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved calibration curve: {output_path}")

def plot_confidence_distribution(
    results: Dict[str, Any],
    output_path: Path
):
    """Plot confidence distributions across ablation modes."""
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.flatten()
    
    modes = ["S", "P", "E", "SP", "SE", "PE", "SPE"]
    
    for idx, mode in enumerate(modes):
        ax = axes[idx]
        
        # Extract confidences
        per_variant = results['per_variant_details'][mode]
        confidences = [v['confidence'] for v in per_variant]
        
        ax.hist(confidences, bins=15, alpha=0.7, color='#A23B72', edgecolor='black')
        ax.set_xlabel('Confidence', fontsize=10, fontweight='bold')
        ax.set_ylabel('Count', fontsize=10, fontweight='bold')
        ax.set_title(f'{mode} (μ={np.mean(confidences):.3f})', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0, 1])
    
    # Hide extra subplot
    axes[7].axis('off')
    
    plt.suptitle('Confidence Distributions Across Ablation Modes', 
                 fontsize=16, fontweight='bold', y=1.00)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved confidence distributions: {output_path}")

def plot_ablation_comparison(
    results: Dict[str, Any],
    output_path: Path
):
    """Bar chart comparing ablation modes."""
    modes = ["S", "P", "E", "SP", "SE", "PE", "SPE"]
    accuracies = [results['summary'][m]['pathway_accuracy'] * 100 for m in modes]
    confidences = [results['summary'][m]['avg_confidence'] * 100 for m in modes]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Accuracy comparison
    colors_acc = ['#F18F01' if a >= 70 else '#C73E1D' for a in accuracies]
    ax1.bar(modes, accuracies, color=colors_acc, alpha=0.8, edgecolor='black', linewidth=1.5)
    ax1.axhline(y=70, color='green', linestyle='--', linewidth=2, label='Publication Threshold')
    ax1.set_ylabel('Pathway Alignment Accuracy (%)', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Ablation Mode', fontsize=12, fontweight='bold')
    ax1.set_title('Pathway Alignment Accuracy by Component', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim([0, 110])
    
    # Confidence comparison
    ax2.bar(modes, confidences, color='#2E86AB', alpha=0.8, edgecolor='black', linewidth=1.5)
    ax2.set_ylabel('Average Confidence (%)', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Ablation Mode', fontsize=12, fontweight='bold')
    ax2.set_title('Average Confidence by Component', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim([0, 70])
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved ablation comparison: {output_path}")

def main():
    """Generate all calibration plots for publication."""
    print("="*60)
    print("MM CALIBRATION ANALYSIS - Publication Figures")
    print("="*60)
    
    # Load ablation results
    results_dir = Path(__file__).parent.parent / "results" / "mm_ablations"
    results = load_ablation_results(results_dir)
    
    print(f"\nLoaded ablation results from: {results_dir}")
    print(f"Modes analyzed: {', '.join(results['ablation_modes'])}")
    
    # Create output directory
    output_dir = Path(__file__).parent.parent / "results" / "mm_calibration"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print("Generating Calibration Curves")
    print(f"{'='*60}")
    
    # Generate calibration curves for key modes
    key_modes = ["SP", "SPE"]  # Focus on successful modes
    calibration_results = {}
    
    for mode in key_modes:
        per_variant = results['per_variant_details'][mode]
        metrics = compute_calibration(per_variant, n_bins=10)
        calibration_results[mode] = metrics
        
        output_file = output_dir / f"calibration_curve_{mode}.png"
        plot_calibration_curve(metrics, mode, output_file)
        
        print(f"\n{mode} Calibration Metrics:")
        print(f"  ECE: {metrics.ece:.4f}")
        print(f"  MCE: {metrics.mce:.4f}")
        print(f"  Non-empty bins: {sum(1 for c in metrics.bin_counts if c > 0)}/10")
    
    print(f"\n{'='*60}")
    print("Generating Additional Figures")
    print(f"{'='*60}\n")
    
    # Confidence distributions
    plot_confidence_distribution(results, output_dir / "confidence_distributions.png")
    
    # Ablation comparison
    plot_ablation_comparison(results, output_dir / "ablation_comparison.png")
    
    # Save calibration metrics
    metrics_file = output_dir / "calibration_metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump({
            mode: {
                'ece': metrics.ece,
                'mce': metrics.mce,
                'bin_accuracies': metrics.bin_accuracies,
                'bin_confidences': metrics.bin_confidences,
                'bin_counts': metrics.bin_counts,
            }
            for mode, metrics in calibration_results.items()
        }, f, indent=2)
    
    print(f"  ✓ Saved calibration metrics: {metrics_file}")
    
    print(f"\n{'='*60}")
    print("PUBLICATION FIGURES COMPLETE")
    print(f"{'='*60}")
    print(f"\nAll figures saved to: {output_dir}")
    print("\nFigures generated:")
    print("  1. calibration_curve_SP.png - Reliability diagram for S+P")
    print("  2. calibration_curve_SPE.png - Reliability diagram for full model")
    print("  3. confidence_distributions.png - Confidence histograms across modes")
    print("  4. ablation_comparison.png - Accuracy and confidence bar charts")
    print("\n✅ Ready for publication Figure 3 (Calibration) and Figure 4 (Ablations)")

if __name__ == "__main__":
    main()

