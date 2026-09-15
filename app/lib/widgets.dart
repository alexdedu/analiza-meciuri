import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';

/// Bara segmentata 1 / X / 2. Latimea fiecarui segment = probabilitatea lui.
class ProbabilityBar extends StatelessWidget {
  const ProbabilityBar({
    super.key,
    required this.home,
    required this.draw,
    required this.away,
    this.height = 10,
  });

  final double home;
  final double draw;
  final double away;
  final double height;

  @override
  Widget build(BuildContext context) {
    final total = home + draw + away;
    if (total <= 0) return const SizedBox.shrink();
    return ClipRRect(
      borderRadius: BorderRadius.circular(height / 2),
      child: SizedBox(
        height: height,
        child: Row(
          children: [
            Expanded(flex: (home * 1000).round(), child: Container(color: AppColors.homeWin)),
            Expanded(flex: (draw * 1000).round(), child: Container(color: AppColors.draw)),
            Expanded(flex: (away * 1000).round(), child: Container(color: AppColors.awayWin)),
          ],
        ),
      ),
    );
  }
}

/// O linie de tip "eticheta ---- valoare%", cu bara proprie.
class ProbabilityRow extends StatelessWidget {
  const ProbabilityRow({
    super.key,
    required this.label,
    required this.probability,
    required this.color,
    this.trailing,
  });

  final String label;
  final double probability;
  final Color color;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          SizedBox(
            width: 108,
            child: Text(label,
                style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                overflow: TextOverflow.ellipsis),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: probability.clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: AppColors.surfaceHigh,
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 44,
            child: Text('${(probability * 100).toStringAsFixed(0)}%',
                textAlign: TextAlign.right,
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

/// Forma recenta ca sir de bulinute colorate: V verde, E gri, I rosu.
class FormStrip extends StatelessWidget {
  const FormStrip({super.key, required this.form});

  final List<String> form;

  @override
  Widget build(BuildContext context) {
    if (form.isEmpty) {
      return const Text('fara istoric', style: TextStyle(fontSize: 12, color: AppColors.textSecondary));
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: form.map((r) {
        final color = switch (r) {
          'V' => AppColors.positive,
          'E' => AppColors.draw,
          _ => AppColors.negative,
        };
        return Container(
          margin: const EdgeInsets.only(right: 4),
          width: 20,
          height: 20,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.18),
            borderRadius: BorderRadius.circular(5),
            border: Border.all(color: color.withValues(alpha: 0.5)),
          ),
          child: Text(r,
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: color)),
        );
      }).toList(),
    );
  }
}

class ConfidenceBadge extends StatelessWidget {
  const ConfidenceBadge({super.key, required this.confidence, this.compact = false});

  final Confidence confidence;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final color = switch (confidence) {
      Confidence.ridicata => AppColors.positive,
      Confidence.medie => AppColors.warning,
      Confidence.scazuta => AppColors.negative,
    };
    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 6 : 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        confidence.label,
        style: TextStyle(fontSize: compact ? 10 : 11, fontWeight: FontWeight.w600, color: color),
      ),
    );
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.title, required this.child, this.subtitle});

  final String title;
  final String? subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            if (subtitle != null) ...[
              const SizedBox(height: 3),
              Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
            ],
            const SizedBox(height: 14),
            child,
          ],
        ),
      ),
    );
  }
}
